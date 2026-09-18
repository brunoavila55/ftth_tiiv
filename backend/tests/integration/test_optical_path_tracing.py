import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.cables.models import Cable, CableSegment, Fiber, FiberSegment, Tube
from app.modules.connectivity.models import (
    Connection,
    InternalEdge,
    Splitter,
    SplitterOutput,
    Terminal,
)
from app.modules.gis.helpers import linestring_geometry_to_wkb, point_geometry_to_wkb
from app.modules.identity.models import User
from app.modules.inventory.models import Device, Port, Structure
from app.schemas.common import UserRole
from app.schemas.geojson import LineStringGeometry, PointGeometry


def auth_client_login(client: TestClient, email: str, password: str = "AdminPass123!") -> str:
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


def create_test_user(db_session: Session, email: str = "engineer_b09@provedor.com.br") -> User:
    user = User(
        email=email,
        name="Engenheiro B09",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_structure(db_session: Session, code: str, kind: str) -> Structure:
    struct = Structure(
        code=code,
        kind=kind,
        location=point_geometry_to_wkb(
            PointGeometry(type="Point", coordinates=(-46.633308, -23.550520))
        ),
        capacity=16,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(struct)
    db_session.commit()
    db_session.refresh(struct)
    return struct


def create_cable_with_fiber(
    db_session: Session,
    code: str,
    struct_a: Structure,
    struct_b: Structure,
    length_m: float = 1000.0,
) -> tuple[CableSegment, FiberSegment, Terminal, Terminal]:
    cable = Cable(
        code=code,
        model="CFOA-SM-AS-12F",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(cable)
    db_session.commit()

    tube = Tube(
        cable_id=cable.id,
        number=1,
        color_name="Verde",
        version=1,
    )
    db_session.add(tube)
    db_session.commit()

    fiber = Fiber(
        cable_id=cable.id,
        tube_id=tube.id,
        global_number=1,
        tube_position=1,
        color_name="Verde",
        version=1,
    )
    db_session.add(fiber)
    db_session.commit()

    cseg = CableSegment(
        cable_id=cable.id,
        origin_structure_id=struct_a.id,
        destination_structure_id=struct_b.id,
        geometry=linestring_geometry_to_wkb(
            LineStringGeometry(
                type="LineString",
                coordinates=[(-46.633308, -23.550520), (-46.634000, -23.551000)],
            )
        ),
        map_length_m=length_m,
        effective_length_m=length_m,
        status="installed",
        version=1,
    )
    db_session.add(cseg)
    db_session.commit()

    term_a = Terminal(
        kind="fiber",
        structure_id=struct_a.id,
        label=f"{struct_a.code} - {code} FO #1",
        occupancy="connected",
        entity_type="fiber_segment",
        version=1,
    )
    term_b = Terminal(
        kind="fiber",
        structure_id=struct_b.id,
        label=f"{struct_b.code} - {code} FO #1",
        occupancy="connected",
        entity_type="fiber_segment",
        version=1,
    )
    db_session.add_all([term_a, term_b])
    db_session.commit()

    fseg = FiberSegment(
        cable_segment_id=cseg.id,
        fiber_id=fiber.id,
        fiber_number=1,
        terminal_a_id=term_a.id,
        terminal_b_id=term_b.id,
        occupancy="connected",
        version=1,
    )
    db_session.add(fseg)
    db_session.commit()

    term_a.entity_id = fseg.id
    term_b.entity_id = fseg.id
    db_session.commit()

    return cseg, fseg, term_a, term_b


def test_optical_trace_linear_network_downstream_and_upstream(
    client: TestClient,
    db_session: Session,
) -> None:
    """Fixture de rede linear: OLT PON -> Fusão -> Cabo (1000m) -> Fusão -> Porta Drop ONU."""
    user = create_test_user(db_session, "user_trace_linear@provedor.com.br")
    auth_client_login(client, user.email)

    site_olt = create_structure(db_session, "SITE-CENTRAL-01", "site")
    cto_client = create_structure(db_session, "CTO-FINAL-01", "cto")

    # 1. Porta PON da OLT
    olt_dev = Device(
        code="OLT-HUAWEI-01",
        kind="olt",
        manufacturer="Huawei",
        model="MA5800-X7",
        structure_id=site_olt.id,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(olt_dev)
    db_session.commit()

    pon_port = Port(
        device_id=olt_dev.id,
        name="PON 1/1/1",
        role="pon",
        connector_type="SC/UPC",
        version=1,
    )
    db_session.add(pon_port)
    db_session.commit()

    term_pon = Terminal(
        kind="port",
        structure_id=site_olt.id,
        label=f"{site_olt.code} - {pon_port.name}",
        occupancy="connected",
        entity_type="port",
        entity_id=pon_port.id,
        version=1,
    )
    db_session.add(term_pon)
    db_session.commit()

    # 2. Porta ONU no cliente
    onu_dev = Device(
        code="ONU-CLIENTE-01",
        kind="onu",
        manufacturer="FiberHome",
        model="AN5506",
        structure_id=cto_client.id,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(onu_dev)
    db_session.commit()

    onu_port = Port(
        device_id=onu_dev.id,
        name="OPTICAL",
        role="customer_drop",
        connector_type="SC/APC",
        version=1,
    )
    db_session.add(onu_port)
    db_session.commit()

    term_onu = Terminal(
        kind="port",
        structure_id=cto_client.id,
        label=f"{cto_client.code} - {onu_port.name}",
        occupancy="connected",
        entity_type="port",
        entity_id=onu_port.id,
        version=1,
    )
    db_session.add(term_onu)
    db_session.commit()

    # 3. Cabo de 2000 metros ligando Central à CTO
    _, _, term_cable_a, term_cable_b = create_cable_with_fiber(
        db_session, "CAB-TRONCAL-01", site_olt, cto_client, length_m=2000.0
    )

    # 4. Fusões: PON -> Cabo A (0.1 dB) e Cabo B -> ONU (0.1 dB)
    conn_a = Connection(
        structure_id=site_olt.id,
        terminal_a_id=term_pon.id,
        terminal_b_id=term_cable_a.id,
        connection_type="fusion",
        loss_db=0.1,
        is_active=True,
        version=1,
    )
    conn_b = Connection(
        structure_id=cto_client.id,
        terminal_a_id=term_cable_b.id,
        terminal_b_id=term_onu.id,
        connection_type="fusion",
        loss_db=0.1,
        is_active=True,
        version=1,
    )
    db_session.add_all([conn_a, conn_b])
    db_session.commit()

    # ==========================================================================
    # TESTE 1: RASTREAMENTO DOWNSTREAM (PON -> ONU)
    # ==========================================================================
    trace_down_req = {
        "start_terminal_id": str(term_pon.id),
        "direction": "downstream",
        "max_results": 50,
    }
    resp_down = client.post(
        "/api/v1/topology/trace",
        json=trace_down_req,
    )
    assert resp_down.status_code == status.HTTP_200_OK, resp_down.text
    data_down = resp_down.json()
    assert data_down["status"] == "complete"
    assert len(data_down["paths"]) == 1

    path_down = data_down["paths"][0]
    assert path_down["origin_terminal_id"] == str(term_pon.id)
    assert path_down["destination_terminal_id"] == str(term_onu.id)
    assert path_down["total_length_m"] == 2000.0
    # Perda: Fusão A (0.1) + Fibra 2km*0.25 (0.5) + Fusão B (0.1) = 0.7 dB
    assert path_down["total_loss_db"] == 0.7
    assert len(path_down["steps"]) == 3
    assert path_down["steps"][0]["element_type"] == "fusion"
    assert path_down["steps"][1]["element_type"] == "fiber_segment"
    assert path_down["steps"][2]["element_type"] == "fusion"

    # ==========================================================================
    # TESTE 2: RASTREAMENTO UPSTREAM (ONU -> PON)
    # ==========================================================================
    trace_up_req = {
        "start_terminal_id": str(term_onu.id),
        "direction": "upstream",
        "max_results": 50,
    }
    resp_up = client.post(
        "/api/v1/topology/trace",
        json=trace_up_req,
    )
    assert resp_up.status_code == status.HTTP_200_OK, resp_up.text
    data_up = resp_up.json()
    assert data_up["status"] == "complete"
    assert len(data_up["paths"]) == 1

    path_up = data_up["paths"][0]
    assert path_up["origin_terminal_id"] == str(term_onu.id)
    assert path_up["destination_terminal_id"] == str(term_pon.id)
    assert path_up["total_length_m"] == 2000.0
    assert path_up["total_loss_db"] == 0.7


def test_optical_trace_splitter_cascade_and_sister_outputs(
    client: TestClient,
    db_session: Session,
) -> None:
    """Valida cascata de splitters (1:2 -> 1:4) e regra estrita: caminhos não transitam entre saídas irmãs."""
    user = create_test_user(db_session, "user_trace_splitters@provedor.com.br")
    auth_client_login(client, user.email)

    struct = create_structure(db_session, "CEO-SPLITTER-01", "ceo")

    # Splitter 1: Entrada e 2 Saídas (1:2)
    term_in_1 = Terminal(
        kind="splitter_input", structure_id=struct.id, label="SPL-01 IN", version=1
    )
    term_out_1_1 = Terminal(
        kind="splitter_output", structure_id=struct.id, label="SPL-01 OUT 1", version=1
    )
    term_out_1_2 = Terminal(
        kind="splitter_output", structure_id=struct.id, label="SPL-01 OUT 2", version=1
    )
    db_session.add_all([term_in_1, term_out_1_1, term_out_1_2])
    db_session.commit()

    spl_1 = Splitter(
        structure_id=struct.id,
        code="SPL-01",
        splitter_type="balanced",
        ratio="1:2",
        input_terminal_id=term_in_1.id,
        version=1,
    )
    db_session.add(spl_1)
    db_session.commit()

    out_1_1 = SplitterOutput(
        splitter_id=spl_1.id,
        output_number=1,
        terminal_id=term_out_1_1.id,
        nominal_loss_db=3.5,
        version=1,
    )
    out_1_2 = SplitterOutput(
        splitter_id=spl_1.id,
        output_number=2,
        terminal_id=term_out_1_2.id,
        nominal_loss_db=3.5,
        version=1,
    )
    db_session.add_all([out_1_1, out_1_2])
    db_session.commit()

    # Splitter 2: Entrada ligada à saída 1 do Splitter 1, e 4 Saídas (1:4)
    term_in_2 = Terminal(
        kind="splitter_input", structure_id=struct.id, label="SPL-02 IN", version=1
    )
    term_out_2_1 = Terminal(
        kind="splitter_output", structure_id=struct.id, label="SPL-02 OUT 1", version=1
    )
    term_out_2_2 = Terminal(
        kind="splitter_output", structure_id=struct.id, label="SPL-02 OUT 2", version=1
    )
    term_out_2_3 = Terminal(
        kind="splitter_output", structure_id=struct.id, label="SPL-02 OUT 3", version=1
    )
    term_out_2_4 = Terminal(
        kind="splitter_output", structure_id=struct.id, label="SPL-02 OUT 4", version=1
    )
    db_session.add_all([term_in_2, term_out_2_1, term_out_2_2, term_out_2_3, term_out_2_4])
    db_session.commit()

    spl_2 = Splitter(
        structure_id=struct.id,
        code="SPL-02",
        splitter_type="balanced",
        ratio="1:4",
        input_terminal_id=term_in_2.id,
        version=1,
    )
    db_session.add(spl_2)
    db_session.commit()

    for idx, t in enumerate([term_out_2_1, term_out_2_2, term_out_2_3, term_out_2_4], 1):
        so = SplitterOutput(
            splitter_id=spl_2.id,
            output_number=idx,
            terminal_id=t.id,
            nominal_loss_db=7.2,
            version=1,
        )
        db_session.add(so)
    db_session.commit()

    # Conexão interna patch entre Saída 1 do Splitter 1 e Entrada do Splitter 2
    conn_cascade = Connection(
        structure_id=struct.id,
        terminal_a_id=term_out_1_1.id,
        terminal_b_id=term_in_2.id,
        connection_type="patch_cord",
        loss_db=0.2,
        is_active=True,
        version=1,
    )
    db_session.add(conn_cascade)
    db_session.commit()

    # 1. Rastreamento Downstream a partir da entrada do Splitter 1
    trace_req = {
        "start_terminal_id": str(term_in_1.id),
        "direction": "downstream",
        "max_results": 50,
    }
    resp = client.post("/api/v1/topology/trace", json=trace_req)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    # Deve gerar 5 caminhos:
    # - 1 caminho para a saída 2 do Splitter 1 (SPL-01 OUT 2)
    # - 4 caminhos para as saídas 1..4 do Splitter 2 (cascata SPL-01 -> SPL-02)
    assert len(data["paths"]) == 5

    # Caminho cascata para Splitter 2 saída 1:
    cascade_paths = [
        p for p in data["paths"] if p["destination_terminal_id"] == str(term_out_2_1.id)
    ]
    assert len(cascade_paths) == 1
    p_casc = cascade_paths[0]
    # Perda: SPL-01 (3.5) + Patch (0.2) + SPL-02 (7.2) = 10.9 dB
    assert p_casc["total_loss_db"] == 10.9

    # 2. Teste da regra: "caminhos não transitam entre saídas irmãs"
    # Rastreando Upstream da Saída 1 do Splitter 2:
    trace_up = client.post(
        "/api/v1/topology/trace",
        json={"start_terminal_id": str(term_out_2_1.id), "direction": "upstream"},
    )
    assert trace_up.status_code == status.HTTP_200_OK
    data_up = trace_up.json()
    assert len(data_up["paths"]) == 1
    # O caminho deve ir para SPL-02 IN -> Patch -> SPL-01 OUT 1 -> SPL-01 IN!
    # NUNCA para SPL-02 OUT 2, OUT 3 ou OUT 4!
    dest_id = data_up["paths"][0]["destination_terminal_id"]
    assert dest_id == str(term_in_1.id)
    visited_dests = [step["output_terminal_id"] for step in data_up["paths"][0]["steps"]]
    assert str(term_out_2_2.id) not in visited_dests
    assert str(term_out_2_3.id) not in visited_dests


def test_optical_trace_continuity_without_cut(
    client: TestClient,
    db_session: Session,
) -> None:
    """Valida continuidade sem corte (InternalEdge pass-through)."""
    user = create_test_user(db_session, "user_trace_pass@provedor.com.br")
    auth_client_login(client, user.email)

    struct_a = create_structure(db_session, "SITE-A", "site")
    struct_ceo = create_structure(db_session, "CEO-PASS", "ceo")
    struct_b = create_structure(db_session, "SITE-B", "site")

    # Cabo 1: A -> CEO (1000m)
    _, _, term_a1, term_ceo_in = create_cable_with_fiber(
        db_session, "CAB-01", struct_a, struct_ceo, length_m=1000.0
    )
    # Cabo 2: CEO -> B (1500m)
    _, _, term_ceo_out, term_b2 = create_cable_with_fiber(
        db_session, "CAB-02", struct_ceo, struct_b, length_m=1500.0
    )

    # Continuidade sem corte na CEO (0.0 dB)
    edge_pass = InternalEdge(
        terminal_a_id=term_ceo_in.id,
        terminal_b_id=term_ceo_out.id,
        edge_type="fiber_continuity",
        entity_type="fiber_segment",
        entity_id=uuid.uuid4(),
        loss_db=0.0,
        is_bidirectional=True,
        version=1,
    )
    db_session.add(edge_pass)
    db_session.commit()

    resp = client.post(
        "/api/v1/topology/trace",
        json={"start_terminal_id": str(term_a1.id), "direction": "downstream"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data["paths"]) == 1
    path = data["paths"][0]
    assert path["destination_terminal_id"] == str(term_b2.id)
    assert path["total_length_m"] == 2500.0


def test_optical_trace_cycle_detection(
    client: TestClient,
    db_session: Session,
) -> None:
    """Valida detecção de ciclo inválido no grafo com encerramento seguro e status cycle_detected."""
    user = create_test_user(db_session, "user_trace_cycle@provedor.com.br")
    auth_client_login(client, user.email)

    struct = create_structure(db_session, "CEO-CYCLE", "ceo")

    term_1 = Terminal(kind="port", structure_id=struct.id, label="T1", version=1)
    term_2 = Terminal(kind="port", structure_id=struct.id, label="T2", version=1)
    term_3 = Terminal(kind="port", structure_id=struct.id, label="T3", version=1)
    db_session.add_all([term_1, term_2, term_3])
    db_session.commit()

    # Cria anel fechado: T1 -> T2 -> T3 -> T1
    conn_12 = Connection(
        structure_id=struct.id,
        terminal_a_id=term_1.id,
        terminal_b_id=term_2.id,
        connection_type="patch_cord",
        loss_db=0.1,
        is_active=True,
        version=1,
    )
    conn_23 = Connection(
        structure_id=struct.id,
        terminal_a_id=term_2.id,
        terminal_b_id=term_3.id,
        connection_type="patch_cord",
        loss_db=0.1,
        is_active=True,
        version=1,
    )
    conn_31 = Connection(
        structure_id=struct.id,
        terminal_a_id=term_3.id,
        terminal_b_id=term_1.id,
        connection_type="patch_cord",
        loss_db=0.1,
        is_active=True,
        version=1,
    )
    db_session.add_all([conn_12, conn_23, conn_31])
    db_session.commit()

    resp = client.post(
        "/api/v1/topology/trace",
        json={"start_terminal_id": str(term_1.id), "direction": "downstream"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "cycle_detected"
    assert any("Ciclo óptico detectado" in w for w in data["warnings"])


def test_optical_trace_open_end_incomplete(
    client: TestClient,
    db_session: Session,
) -> None:
    """Valida detecção de ponta aberta (desconexão) com retorno de status incomplete e lista de unresolved_terminals."""
    user = create_test_user(db_session, "user_trace_open@provedor.com.br")
    auth_client_login(client, user.email)

    struct_a = create_structure(db_session, "SITE-ORIGIN", "site")
    struct_b = create_structure(db_session, "CEO-ORPHAN", "ceo")

    # Cabo que termina no nada (sem fusão, sem ONU, sem porta)
    _, _, term_start, term_orphan = create_cable_with_fiber(
        db_session, "CAB-ORPHAN", struct_a, struct_b, length_m=500.0
    )

    resp = client.post(
        "/api/v1/topology/trace",
        json={"start_terminal_id": str(term_start.id), "direction": "downstream"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "incomplete"
    assert str(term_orphan.id) in data["unresolved_terminals"]
    assert any("Ponta aberta detectada" in w for w in data["warnings"])
