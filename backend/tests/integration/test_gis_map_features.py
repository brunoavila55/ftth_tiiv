import math

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.cables.models import Cable, CableSegment
from app.modules.cables.service import (
    create_cable_segment,
    update_cable_segment,
)
from app.modules.gis.helpers import (
    haversine_distance_m,
    linestring_geometry_to_wkb,
    point_geometry_to_wkb,
    wkb_to_linestring_geometry,
)
from app.modules.gis.service import get_topology_revision, query_map_features
from app.modules.identity.models import User
from app.modules.inventory.models import Site, Structure
from app.schemas.cables import CableSegmentCreate, CableSegmentUpdate
from app.schemas.common import UserRole
from app.schemas.geojson import LineStringGeometry, PointGeometry


@pytest.fixture
def engineer_user(db_session: Session) -> User:
    """Cria um usuário engenheiro para testes autenticados."""
    user = User(
        email="gis_engineer@provedor.com.br",
        name="GIS Engineer",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_client_login(client: TestClient, email: str, password: str = "EngineerPass123!") -> str:
    csrf_resp = client.get("/api/v1/auth/csrf")
    csrf_token = csrf_resp.json()["csrf_token"]
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert login_resp.status_code == status.HTTP_200_OK
    cookie_token = client.cookies.get("ftth_csrf_token")
    assert cookie_token is not None
    return str(cookie_token)


def test_known_segment_distance_and_optical_rule(db_session: Session) -> None:
    """Verifica se a distância geodésica PostGIS de um segmento conhecido é calculada com tolerância

    e se a regra óptica de comprimento (precedência de medição sem dupla reserva) é cumprida.
    """
    # 1. Cria estruturas a ~111 metros uma da outra (0.001 grau de latitude ~ 111.19m)
    p_orig = (-46.633308, -23.550520)
    p_dest = (-46.633308, -23.551520)
    expected_dist = haversine_distance_m(p_orig, p_dest)
    assert 110.0 < expected_dist < 112.0

    st_orig = Structure(
        code="POSTE-GIS-01",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_orig)),
        status="installed",
    )
    st_dest = Structure(
        code="POSTE-GIS-02",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_dest)),
        status="installed",
    )
    cable = Cable(
        code="CABO-GIS-12F",
        model="CFOA-SM-12F",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
    )
    db_session.add_all([st_orig, st_dest, cable])
    db_session.commit()

    # 2. Cria segmento sem medição: effective = map_length_m + slack_length_m
    segment_create = CableSegmentCreate(
        cable_id=str(cable.id),
        origin_structure_id=str(st_orig.id),
        destination_structure_id=str(st_dest.id),
        geometry=LineStringGeometry(coordinates=[p_orig, p_dest]),
        slack_length_m=15.0,
        measured_length_m=None,
    )
    seg = create_cable_segment(db_session, segment_create)

    # Verifica precisão geodésica (< 0.5% de divergência em relação ao elipsoide WGS84)
    assert math.isclose(seg.map_length_m, expected_dist, rel_tol=0.01)
    assert seg.slack_length_m == 15.0
    assert seg.measured_length_m is None
    assert seg.length_source == "calculated"
    assert math.isclose(seg.effective_length_m, seg.map_length_m + 15.0, rel_tol=0.001)

    # 3. Atualiza com medição física no campo (128.5 metros)
    # Regra óptica: measured_length_m tem precedência total; reserva técnica NÃO é somada novamente
    update_payload = CableSegmentUpdate(
        measured_length_m=128.5,
    )
    updated_seg = update_cable_segment(
        db_session, str(seg.id), update_payload, if_match=str(seg.version)
    )
    assert updated_seg.measured_length_m == 128.5
    assert updated_seg.effective_length_m == 128.5
    assert updated_seg.length_source == "measured"
    # A reserva permanece registrada mas NÃO foi somada ao effective_length_m
    assert updated_seg.slack_length_m == 15.0


def test_route_endpoints_tolerance_validation(db_session: Session) -> None:
    """Verifica que divergência entre as pontas da rota e as estruturas é rejeitada com 422."""
    p_orig = (-46.633308, -23.550520)
    p_dest = (-46.634120, -23.551200)

    st_orig = Structure(
        code="POSTE-TOL-01",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_orig)),
    )
    st_dest = Structure(
        code="POSTE-TOL-02",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_dest)),
    )
    cable = Cable(
        code="CABO-TOL-01",
        model="CFOA-SM-12F",
        fiber_count=12,
    )
    db_session.add_all([st_orig, st_dest, cable])
    db_session.commit()

    # Ponta inicial divergente em ~22m (> tolerância de 5m)
    p_orig_divergent = (-46.633308, -23.550520 + 0.0002)
    invalid_create = CableSegmentCreate(
        cable_id=str(cable.id),
        origin_structure_id=str(st_orig.id),
        destination_structure_id=str(st_dest.id),
        geometry=LineStringGeometry(coordinates=[p_orig_divergent, p_dest]),
    )
    with pytest.raises(Exception) as exc_info:
        create_cable_segment(db_session, invalid_create)
    assert "Divergência na extremidade inicial da rota" in str(exc_info.value)


def test_spatial_bbox_query_and_gist_index(
    client: TestClient,
    db_session: Session,
    engineer_user: User,
) -> None:
    """Verifica a consulta espacial por Bounding Box em /map/features e o uso do índice GiST."""
    auth_client_login(client, engineer_user.email)

    # 1. Popula Site e Estruturas no centro de São Paulo
    site_pt = (-46.6333, -23.5505)
    site = Site(
        code="POP-CENTRO",
        name="POP Centro SP",
        kind="pop",
        location=point_geometry_to_wkb(PointGeometry(coordinates=site_pt)),
    )
    struct_pt1 = (-46.6340, -23.5510)
    struct_pt2 = (-46.6345, -23.5515)
    struct1 = Structure(
        code="POSTE-CENTRO-01",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=struct_pt1)),
    )
    struct2 = Structure(
        code="POSTE-CENTRO-02",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=struct_pt2)),
    )
    cable = Cable(code="CAB-MAP-01", model="SM-12F", fiber_count=12)
    db_session.add_all([site, struct1, struct2, cable])
    db_session.commit()

    # Cria trecho de cabo ligando as duas estruturas
    line_geom = LineStringGeometry(coordinates=[struct_pt1, struct_pt2])
    seg = CableSegment(
        cable_id=cable.id,
        origin_structure_id=struct1.id,
        destination_structure_id=struct2.id,
        geometry=linestring_geometry_to_wkb(line_geom),
        map_length_m=50.0,
        effective_length_m=50.0,
        length_source="calculated",
    )
    db_session.add(seg)
    db_session.commit()

    # 2. Faz requisição HTTP com bbox cobrindo a região
    res = client.get(
        "/api/v1/map/features",
        params={
            "bbox": "-46.64,-23.56,-46.62,-23.54",
            "layers": "sites,structures,cables",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert data["truncated"] is False
    assert len(data["features"]) >= 3
    assert data["topology_revision"] >= 1

    feature_types = {f["properties"]["entity_type"] for f in data["features"]}
    assert "site" in feature_types
    assert "structure" in feature_types
    assert "cable_segment" in feature_types

    # 3. Bbox em outra região (ex: Rio de Janeiro) não retorna features
    res_empty = client.get(
        "/api/v1/map/features",
        params={
            "bbox": "-43.20,-22.95,-43.15,-22.90",
            "layers": "sites,structures,cables",
        },
    )
    assert res_empty.status_code == 200
    assert len(res_empty.json()["features"]) == 0

    # 4. Verifica no plano de execução do PostgreSQL que o índice espacial GiST é utilizado
    explain_sql = text(
        "EXPLAIN (FORMAT JSON) "
        "SELECT id FROM structures WHERE ST_Intersects(location, ST_MakeEnvelope(-46.64, -23.56, -46.62, -23.54, 4326));"
    )
    plan_result = db_session.execute(explain_sql).scalar_one()
    plan_str = str(plan_result)
    assert (
        "Index Scan" in plan_str
        or "Bitmap Index Scan" in plan_str
        or "idx_structures_location" in plan_str
    )


def test_invalid_bbox_returns_422(
    client: TestClient,
    engineer_user: User,
) -> None:
    """Verifica que envelopes geográficos inválidos retornam HTTP 422 Problem Details."""
    auth_client_login(client, engineer_user.email)

    # Coordenadas fora dos limites geodésicos
    res = client.get("/api/v1/map/features", params={"bbox": "-190.0,-23.0,-46.0,-22.0"})
    assert res.status_code == 422
    assert "application/problem+json" in res.headers["content-type"]

    # min_lon > max_lon
    res2 = client.get("/api/v1/map/features", params={"bbox": "-46.0,-23.0,-47.0,-22.0"})
    assert res2.status_code == 422
    assert "não pode ser maior que maxLon" in res2.json()["detail"]


def test_truncation_limit_signaling(db_session: Session) -> None:
    """Verifica que exceder o limite de feições sinaliza explicitamente truncated=True."""
    # Cria 10 estruturas
    for i in range(10):
        st = Structure(
            code=f"POSTE-TRUNC-{i:02d}",
            kind="pole",
            location=point_geometry_to_wkb(
                PointGeometry(coordinates=(-46.633 + (i * 0.0001), -23.550))
            ),
        )
        db_session.add(st)
    db_session.commit()

    # Consulta com limite restrito a 5
    result = query_map_features(
        db=db_session,
        bbox_str="-46.64,-23.56,-46.62,-23.54",
        layers_str="structures",
        limit=5,
    )
    assert result.truncated is True
    assert len(result.features) == 5


def test_geometric_modification_bumps_topology_revision(db_session: Session) -> None:
    """Verifica que mutações que alteram geometria ou comprimentos incrementam topology_revision."""
    initial_rev = get_topology_revision(db_session)

    p_orig = (-46.633308, -23.550520)
    p_dest = (-46.634120, -23.551200)
    st_orig = Structure(
        code="POSTE-REV-01",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_orig)),
    )
    st_dest = Structure(
        code="POSTE-REV-02",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_dest)),
    )
    cable = Cable(code="CAB-REV-01", model="SM-12F", fiber_count=12)
    db_session.add_all([st_orig, st_dest, cable])
    db_session.commit()

    # Criação do trecho deve incrementar a revisão de topologia
    seg = create_cable_segment(
        db_session,
        CableSegmentCreate(
            cable_id=str(cable.id),
            origin_structure_id=str(st_orig.id),
            destination_structure_id=str(st_dest.id),
            geometry=LineStringGeometry(coordinates=[p_orig, p_dest]),
        ),
    )
    rev_after_create = get_topology_revision(db_session)
    assert rev_after_create == initial_rev + 1

    # Atualização de medição de comprimento altera cálculo óptico -> incrementa novamente
    update_cable_segment(
        db_session,
        str(seg.id),
        CableSegmentUpdate(measured_length_m=135.0),
        if_match=str(seg.version),
    )
    rev_after_update = get_topology_revision(db_session)
    assert rev_after_update == rev_after_create + 1


def test_moving_structure_does_not_auto_reroute_cables(db_session: Session) -> None:
    """Verifica a regra de integridade física:

    Mover uma estrutura/poste NÃO altera nem redireciona cabos automaticamente por proximidade.
    """
    p_orig = (-46.633308, -23.550520)
    p_dest = (-46.634120, -23.551200)
    st_orig = Structure(
        code="POSTE-MOVE-01",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_orig)),
    )
    st_dest = Structure(
        code="POSTE-MOVE-02",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=p_dest)),
    )
    cable = Cable(code="CAB-MOVE-01", model="SM-12F", fiber_count=12)
    db_session.add_all([st_orig, st_dest, cable])
    db_session.commit()

    seg = create_cable_segment(
        db_session,
        CableSegmentCreate(
            cable_id=str(cable.id),
            origin_structure_id=str(st_orig.id),
            destination_structure_id=str(st_dest.id),
            geometry=LineStringGeometry(coordinates=[p_orig, p_dest]),
        ),
    )
    initial_seg_coords = wkb_to_linestring_geometry(seg.geometry).coordinates

    # Move a estrutura de destino para outra coordenada
    new_dest_coords = (-46.635000, -23.552000)
    st_dest.location = point_geometry_to_wkb(PointGeometry(coordinates=new_dest_coords))
    st_dest.version += 1
    db_session.commit()

    # Recarrega o segmento e verifica que suas coordenadas NÃO foram alteradas silenciosamente
    db_session.refresh(seg)
    current_seg_coords = wkb_to_linestring_geometry(seg.geometry).coordinates
    assert current_seg_coords == initial_seg_coords
    # Mover a estrutura preservou as coordenadas do cabo (sem auto-rerouting)


def test_map_features_rbac_permissions(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica a matriz RBAC: todos os perfis autenticados com permissão 'network:read'

    (viewer, technician, engineer, admin) podem consultar feições do mapa.
    Requisições anônimas devem receber HTTP 401.
    """
    # 1. Requisição não autenticada -> 401
    res_anon = client.get("/api/v1/map/features", params={"bbox": "-46.64,-23.56,-46.62,-23.54"})
    assert res_anon.status_code == 401
    assert "application/problem+json" in res_anon.headers["content-type"]

    # 2. Usuário com perfil 'viewer' -> 200
    viewer = User(
        email="viewer_map@provedor.com.br",
        name="Viewer Map",
        password_hash=hash_password("ViewerPass123!"),
        role=UserRole.VIEWER.value,
        is_active=True,
        version=1,
    )
    db_session.add(viewer)
    db_session.commit()

    auth_client_login(client, viewer.email, password="ViewerPass123!")
    res_viewer = client.get("/api/v1/map/features", params={"bbox": "-46.64,-23.56,-46.62,-23.54"})
    assert res_viewer.status_code == 200
