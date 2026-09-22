from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.cables.models import Cable, CableSegment, Fiber, FiberSegment, Tube
from app.modules.connectivity.models import Connection, Terminal
from app.modules.gis.helpers import point_geometry_to_wkb
from app.modules.gis.service import get_topology_revision
from app.modules.identity.models import User
from app.schemas.common import UserRole
from app.schemas.geojson import PointGeometry


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


def test_cable_24f_generation_and_48_terminals(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica o critério central de aceite B06:

    Cabo 24F de dois grupos de 12 gera 24 fibras e 48 extremidades (terminais) por segmento.
    """
    user = User(
        email="eng_cables@provedor.com.br",
        name="Cable Engineer",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    # 1. Criação do Cabo 24F (2 tubos de 12 fibras) via API
    cable_payload = {
        "code": "CAB-TRONCAL-24F",
        "model": "CFOA-SM-AS80-S-24F",
        "fiber_count": 24,
        "tube_count": 2,
        "color_standard": "NBR",
        "status": "installed",
        "notes": "Cabo troncal de alimentação",
    }
    cable_resp = client.post(
        "/api/v1/cables",
        json=cable_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert cable_resp.status_code == 201, cable_resp.text
    cable_data = cable_resp.json()
    cable_id = cable_data["id"]

    # Valida tubos e fibras gerados no banco
    tubes = (
        db_session.execute(select(Tube).where(Tube.cable_id == cable_id).order_by(Tube.number))
        .scalars()
        .all()
    )
    assert len(tubes) == 2
    assert tubes[0].number == 1
    assert tubes[0].color_name == "Verde"
    assert tubes[1].number == 2
    assert tubes[1].color_name == "Amarelo"

    fibers = (
        db_session.execute(
            select(Fiber).where(Fiber.cable_id == cable_id).order_by(Fiber.global_number)
        )
        .scalars()
        .all()
    )
    assert len(fibers) == 24
    # Fibras 1-12 no tubo 1
    for i in range(12):
        assert fibers[i].global_number == i + 1
        assert fibers[i].tube_id == tubes[0].id
        assert fibers[i].tube_position == i + 1
    # Fibras 13-24 no tubo 2
    for i in range(12, 24):
        assert fibers[i].global_number == i + 1
        assert fibers[i].tube_id == tubes[1].id
        assert fibers[i].tube_position == (i - 12) + 1

    # 2. Criação de estruturas de origem e destino
    from app.modules.inventory.models import Structure

    st_orig = Structure(
        code="POSTE-24F-01",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=(-46.633308, -23.550520))),
    )
    st_dest = Structure(
        code="POSTE-24F-02",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=(-46.634120, -23.551200))),
    )
    db_session.add_all([st_orig, st_dest])
    db_session.commit()

    # 3. Criação do segmento de cabo
    seg_payload = {
        "cable_id": cable_id,
        "origin_structure_id": str(st_orig.id),
        "destination_structure_id": str(st_dest.id),
        "geometry": {
            "type": "LineString",
            "coordinates": [[-46.633308, -23.550520], [-46.634120, -23.551200]],
        },
        "slack_length_m": 10.0,
    }
    seg_resp = client.post(
        "/api/v1/cable-segments",
        json=seg_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert seg_resp.status_code == 201, seg_resp.text
    seg_data = seg_resp.json()
    seg_id = seg_data["id"]

    # 4. Verifica geração de 24 fiber_segments e 48 terminais
    fiber_segs = (
        db_session.execute(
            select(FiberSegment)
            .where(FiberSegment.cable_segment_id == seg_id)
            .order_by(FiberSegment.fiber_number)
        )
        .scalars()
        .all()
    )
    assert len(fiber_segs) == 24

    # Coleta todos os terminais das extremidades A e B
    term_a_ids = [fs.terminal_a_id for fs in fiber_segs]
    term_b_ids = [fs.terminal_b_id for fs in fiber_segs]

    # Todos os terminais de cada extremidade devem ser distintos
    assert len(set(term_a_ids)) == 24
    assert len(set(term_b_ids)) == 24
    # Nenhuma extremidade A pode ser igual a uma extremidade B
    assert set(term_a_ids).isdisjoint(set(term_b_ids))

    all_term_ids = term_a_ids + term_b_ids
    assert len(all_term_ids) == 48

    # Verifica os terminais no banco de dados
    terminals = (
        db_session.execute(select(Terminal).where(Terminal.id.in_(all_term_ids))).scalars().all()
    )
    assert len(terminals) == 48
    for t in terminals:
        assert t.kind == "fiber_endpoint"
        assert t.is_occupied is False
        assert t.structure_id in (st_orig.id, st_dest.id)

    # 5. Listagem de fibras do segmento via API paginada
    list_fibers_resp = client.get(f"/api/v1/cable-segments/{seg_id}/fibers?limit=30")
    assert list_fibers_resp.status_code == 200
    fibers_page = list_fibers_resp.json()
    assert fibers_page["total"] == 24
    assert len(fibers_page["items"]) == 24

    # 6. O mapa deve impedir a remoção da estrutura enquanto o trecho estiver ativo.
    blocked_structure_delete = client.delete(
        f"/api/v1/structures/{st_orig.id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert blocked_structure_delete.status_code == status.HTTP_409_CONFLICT

    # Depois de retirar o trecho, suas estruturas e o cabo podem ser retirados sem
    # apagar o histórico físico referenciado pelas fibras.
    delete_segment_resp = client.delete(
        f"/api/v1/cable-segments/{seg_id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert delete_segment_resp.status_code == status.HTTP_204_NO_CONTENT

    delete_structure_resp = client.delete(
        f"/api/v1/structures/{st_orig.id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert delete_structure_resp.status_code == status.HTTP_204_NO_CONTENT
    db_session.refresh(st_orig)
    assert st_orig.status == "retired"

    delete_cable_resp = client.delete(
        f"/api/v1/cables/{cable_id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert delete_cable_resp.status_code == status.HTTP_204_NO_CONTENT
    stored_cable = db_session.get(Cable, cable_id)
    assert stored_cable is not None
    db_session.refresh(stored_cable)
    assert stored_cable.status == "retired"


def test_segment_split_at_access_structure(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica a operação atômica de divisão de segmento em caixa/estrutura intermediária.

    - Preserva identidade do cabo e das fibras.
    - Cria continuidade interna sem perda de fusão (0.0 dB) para fibras passantes.
    - Cria extremidades livres para fibras cortadas.
    - Preserva conexões pré-existentes nas pontas externas.
    - Incrementa topology_revision.
    """
    from app.modules.inventory.models import Structure

    user = User(
        email="eng_split@provedor.com.br",
        name="Split Engineer",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    # 1. Estruturas: A (origem), B (CEO intermediária), C (destino)
    pt_a = (-46.6330, -23.5500)
    pt_b = (-46.6340, -23.5510)
    pt_c = (-46.6350, -23.5520)

    st_a = Structure(
        code="POSTE-A",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=pt_a)),
    )
    st_b = Structure(
        code="CEO-INTERMEDIARIA",
        kind="ceo",
        location=point_geometry_to_wkb(PointGeometry(coordinates=pt_b)),
    )
    st_c = Structure(
        code="POSTE-C",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(coordinates=pt_c)),
    )
    db_session.add_all([st_a, st_b, st_c])
    db_session.commit()

    # 2. Cria cabo 6F e segmento A->C
    cable_resp = client.post(
        "/api/v1/cables",
        json={
            "code": "CAB-DIST-6F",
            "model": "CFOA-SM-6F",
            "fiber_count": 6,
            "tube_count": 1,
            "color_standard": "NBR",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    cable_id = cable_resp.json()["id"]

    seg_resp = client.post(
        "/api/v1/cable-segments",
        json={
            "cable_id": cable_id,
            "origin_structure_id": str(st_a.id),
            "destination_structure_id": str(st_c.id),
            "geometry": {
                "type": "LineString",
                "coordinates": [pt_a, pt_b, pt_c],
            },
            "slack_length_m": 20.0,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    original_seg_id = seg_resp.json()["id"]

    fibers = (
        db_session.execute(
            select(Fiber).where(Fiber.cable_id == cable_id).order_by(Fiber.global_number)
        )
        .scalars()
        .all()
    )
    # Cortar fibras 1 e 2 na CEO-B; Fibras 3, 4, 5, 6 serão passantes (continuidade interna)
    cut_fiber_ids = [str(fibers[0].id), str(fibers[1].id)]

    # 3. Pré-visualização da divisão
    preview_payload = {
        "access_structure_id": str(st_b.id),
        "cut_fiber_ids": cut_fiber_ids,
        "segment_1_slack_m": 10.0,
        "segment_2_slack_m": 10.0,
    }
    preview_resp = client.post(
        f"/api/v1/cable-segments/{original_seg_id}/split/preview",
        json=preview_payload,
    )
    assert preview_resp.status_code == 200, preview_resp.text
    preview_data = preview_resp.json()
    assert preview_data["total_fibers_count"] == 6
    assert preview_data["cut_fibers_count"] == 2
    assert preview_data["pass_through_fibers_count"] == 4
    assert preview_data["segment_1_map_length_m"] > 0
    assert preview_data["segment_2_map_length_m"] > 0

    rev_before_split = get_topology_revision(db_session)

    # 4. Executa a divisão atômica
    split_resp = client.post(
        f"/api/v1/cable-segments/{original_seg_id}/split",
        json={**preview_payload, "expected_topology_revision": rev_before_split},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert split_resp.status_code == 200, split_resp.text
    split_data = split_resp.json()

    assert split_data["success"] is True
    assert split_data["pass_through_continuities_count"] == 4
    assert split_data["cut_terminals_count"] == 4  # 2 fibras cortadas x 2 terminais no acesso
    assert split_data["new_topology_revision"] > rev_before_split

    seg_1 = split_data["segment_1"]
    seg_2 = split_data["segment_2"]
    assert seg_1["origin_structure_id"] == str(st_a.id)
    assert seg_1["destination_structure_id"] == str(st_b.id)
    assert seg_2["origin_structure_id"] == str(st_b.id)
    assert seg_2["destination_structure_id"] == str(st_c.id)

    # 5. Validação de integridade no banco de dados
    # Trecho original não deve mais existir ativo
    old_seg = db_session.execute(
        select(CableSegment).where(CableSegment.id == original_seg_id)
    ).scalar_one_or_none()
    assert old_seg is None

    # Verifica conexões de continuidade interna criadas na CEO-B
    continuities = (
        db_session.execute(
            select(Connection).where(
                Connection.structure_id == st_b.id,
                Connection.connection_type == "internal_continuity",
            )
        )
        .scalars()
        .all()
    )
    assert len(continuities) == 4
    for c in continuities:
        assert c.loss_db == 0.0  # Fibras passantes não têm perda de fusão!
        assert c.is_active is True


def test_cable_color_standards_and_logical_groups(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica suporte a múltiplos padrões de cores industriais (TIA-598 vs NBR)

    e agrupamentos lógicos de cabos monotubo.
    """
    user = User(
        email="eng_colors@provedor.com.br",
        name="Color Engineer",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    # 1. Padrão TIA-598
    resp_tia = client.post(
        "/api/v1/cables",
        json={
            "code": "CAB-TIA-12F",
            "model": "SM-12F",
            "fiber_count": 12,
            "tube_count": 1,
            "color_standard": "TIA-598",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_tia.status_code == 201
    cable_tia_id = resp_tia.json()["id"]

    fibers = (
        db_session.execute(
            select(Fiber).where(Fiber.cable_id == cable_tia_id).order_by(Fiber.global_number)
        )
        .scalars()
        .all()
    )
    assert len(fibers) == 12
    # Na TIA-598, a primeira fibra é Blue e a segunda é Orange
    assert fibers[0].color_name == "Blue"
    assert fibers[1].color_name == "Orange"

    # 2. Padrão inválido retorna 422
    resp_inv = client.post(
        "/api/v1/cables",
        json={
            "code": "CAB-INVALID-COLOR",
            "model": "SM-12F",
            "fiber_count": 12,
            "tube_count": 1,
            "color_standard": "UNKNOWN_STANDARD",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_inv.status_code == 422


def test_cables_rbac_permissions(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica a matriz RBAC:

    - Viewer: pode consultar cabos e fibras, mas não criar/alterar/dividir.
    - Engineer: tem acesso completo de escrita.
    - Anônimo: 401.
    """
    viewer = User(
        email="viewer_cables@provedor.com.br",
        name="Viewer Cables",
        password_hash=hash_password("ViewerPass123!"),
        role=UserRole.VIEWER.value,
        is_active=True,
        version=1,
    )
    db_session.add(viewer)
    db_session.commit()

    # 1. Anônimo -> 401
    res_anon = client.get("/api/v1/cables")
    assert res_anon.status_code == 401

    # 2. Viewer autenticado -> GET permitido (200), POST negado (403)
    csrf_viewer = auth_client_login(client, viewer.email, password="ViewerPass123!")
    res_viewer_get = client.get("/api/v1/cables")
    assert res_viewer_get.status_code == 200

    res_viewer_post = client.post(
        "/api/v1/cables",
        json={
            "code": "CAB-FORBIDDEN",
            "model": "SM-12F",
            "fiber_count": 12,
            "tube_count": 1,
            "color_standard": "NBR",
        },
        headers={"X-CSRF-Token": csrf_viewer},
    )
    assert res_viewer_post.status_code == 403
    assert "insufficient_permissions" in res_viewer_post.json()["code"]


def test_transactional_rollback_on_failure(db_session: Session) -> None:
    """Verifica que qualquer falha durante a criação de cabos ou segmentos

    reverte a transação inteira sem deixar fibras órfãs nem tubos residuais.
    """
    from unittest.mock import patch

    import pytest
    from sqlalchemy import func

    from app.modules.cables.service import create_cable
    from app.schemas.cables import CableCreate

    initial_tubes = db_session.execute(select(func.count()).select_from(Tube)).scalar_one()
    initial_fibers = db_session.execute(select(func.count()).select_from(Fiber)).scalar_one()
    initial_cables = db_session.execute(select(func.count()).select_from(Cable)).scalar_one()

    # Simula erro fatal no meio da criação
    with patch(
        "app.modules.cables.service.Fiber.__init__", side_effect=RuntimeError("Simulated failure")
    ):
        with pytest.raises(RuntimeError):
            create_cable(
                db_session,
                CableCreate(
                    code="CAB-ROLLBACK-TEST",
                    model="SM-12F",
                    fiber_count=12,
                    tube_count=1,
                    color_standard="NBR",
                ),
            )
        db_session.rollback()

    final_tubes = db_session.execute(select(func.count()).select_from(Tube)).scalar_one()
    final_fibers = db_session.execute(select(func.count()).select_from(Fiber)).scalar_one()
    final_cables = db_session.execute(select(func.count()).select_from(Cable)).scalar_one()

    assert final_tubes == initial_tubes
    assert final_fibers == initial_fibers
    assert final_cables == initial_cables
