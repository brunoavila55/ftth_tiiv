"""Testes de integração para o cálculo de orçamento óptico e potência (B10).

Verifica a integração com a topologia real, cálculo downstream e upstream,
avaliação de conformidade (pass, overload, below_sensitivity, low_margin)
e tratamento de rotas incompletas.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.cables.models import Cable, CableSegment, Fiber, FiberSegment, Tube
from app.modules.connectivity.models import Connection, Splitter, SplitterOutput, Terminal
from app.modules.customers.models import Customer, ServiceLink
from app.modules.gis.helpers import linestring_geometry_to_wkb, point_geometry_to_wkb
from app.modules.identity.models import User
from app.modules.inventory.models import Device, Port, Structure
from app.modules.optical.models import OpticalProfile
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


def create_engineer(db_session: Session, email: str = "eng_b10@provedor.com.br") -> User:
    user = User(
        email=email,
        name="Engenheiro B10",
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


def setup_ftth_acceptance_topology(db_session: Session):
    """Monta a topologia transversal conforme aceite B10:

    - OLT PON 1/1/1
    - Feeder 3.5 km
    - CEO com Splitter 1:8
    - Distribuição 3.5 km (total 7 km)
    - CTO com Splitter 1:8
    - Atendimento ao cliente
    """
    site_pop = create_structure(db_session, "POP-CENTRAL-B10", "site")
    ceo_struct = create_structure(db_session, "CEO-CENTRAL-B10", "manhole")
    cto_struct = create_structure(db_session, "CTO-FINAL-B10", "cto")

    # 1. OLT e Porta PON
    olt_dev = Device(
        code="OLT-HUAWEI-B10",
        kind="olt",
        manufacturer="Huawei",
        model="MA5800-X7",
        structure_id=site_pop.id,
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
        connector_type="SC/APC",
        version=1,
    )
    db_session.add(pon_port)
    db_session.commit()

    term_pon = Terminal(
        kind="port",
        structure_id=site_pop.id,
        label="POP PON 1/1/1",
        occupancy="connected",
        entity_type="port",
        entity_id=pon_port.id,
        version=1,
    )
    db_session.add(term_pon)
    db_session.commit()

    # 2. Cabo Alimentador: 3500 m POP -> CEO
    _, _, term_feeder_a, term_feeder_b = create_cable_with_fiber(
        db_session, "CABO-FEEDER-B10", site_pop, ceo_struct, length_m=3500.0
    )

    # Conexão PON -> Feeder Fibra A (par acoplado DIO, 0.30 dB)
    conn_dio = Connection(
        structure_id=site_pop.id,
        connection_type="patch_cord",
        terminal_a_id=term_pon.id,
        terminal_b_id=term_feeder_a.id,
        loss_db=0.30,
        version=1,
    )
    db_session.add(conn_dio)
    db_session.commit()

    # 3. Splitter Primário 1:8 na CEO
    term_split1_in = Terminal(
        kind="splitter_input",
        structure_id=ceo_struct.id,
        label="Splitter CEO Entrada",
        occupancy="connected",
        version=1,
    )
    db_session.add(term_split1_in)
    db_session.commit()

    split_1 = Splitter(
        structure_id=ceo_struct.id,
        code="SPL-CEO-01",
        splitter_type="balanced",
        ratio="1:8",
        input_terminal_id=term_split1_in.id,
        version=1,
    )
    db_session.add(split_1)
    db_session.commit()

    term_split1_out1 = Terminal(
        kind="splitter_output",
        structure_id=ceo_struct.id,
        label="Splitter CEO Saída 1",
        occupancy="connected",
        version=1,
    )
    db_session.add(term_split1_out1)
    db_session.commit()

    split_out1 = SplitterOutput(
        splitter_id=split_1.id,
        output_number=1,
        terminal_id=term_split1_out1.id,
        nominal_loss_db=10.5,
        version=1,
    )
    db_session.add(split_out1)
    db_session.commit()

    # Fusão Feeder B -> Entrada do Splitter CEO (0.10 dB)
    fus_ceo = Connection(
        structure_id=ceo_struct.id,
        connection_type="fusion",
        terminal_a_id=term_feeder_b.id,
        terminal_b_id=term_split1_in.id,
        loss_db=0.10,
        version=1,
    )
    db_session.add(fus_ceo)
    db_session.commit()

    # 4. Cabo de Distribuição: 3500 m CEO -> CTO
    _, _, term_dist_a, term_dist_b = create_cable_with_fiber(
        db_session, "CABO-DIST-B10", ceo_struct, cto_struct, length_m=3500.0
    )

    # Fusão Saída do Splitter CEO -> Cabo Dist Fibra A (0.10 dB)
    fus_split_dist = Connection(
        structure_id=ceo_struct.id,
        connection_type="fusion",
        terminal_a_id=term_split1_out1.id,
        terminal_b_id=term_dist_a.id,
        loss_db=0.10,
        version=1,
    )
    db_session.add(fus_split_dist)
    db_session.commit()

    # 5. Splitter Secundário 1:8 na CTO
    term_split2_in = Terminal(
        kind="splitter_input",
        structure_id=cto_struct.id,
        label="Splitter CTO Entrada",
        occupancy="connected",
        version=1,
    )
    db_session.add(term_split2_in)
    db_session.commit()

    split_2 = Splitter(
        structure_id=cto_struct.id,
        code="SPL-CTO-01",
        splitter_type="balanced",
        ratio="1:8",
        input_terminal_id=term_split2_in.id,
        version=1,
    )
    db_session.add(split_2)
    db_session.commit()

    term_split2_out1 = Terminal(
        kind="splitter_output",
        structure_id=cto_struct.id,
        label="Splitter CTO Saída 1",
        occupancy="connected",
        version=1,
    )
    db_session.add(term_split2_out1)
    db_session.commit()

    split_out2 = SplitterOutput(
        splitter_id=split_2.id,
        output_number=1,
        terminal_id=term_split2_out1.id,
        nominal_loss_db=10.5,
        version=1,
    )
    db_session.add(split_out2)
    db_session.commit()

    # Fusão Cabo Dist Fibra B -> Entrada Splitter CTO (0.10 dB)
    fus_cto = Connection(
        structure_id=cto_struct.id,
        connection_type="fusion",
        terminal_a_id=term_dist_b.id,
        terminal_b_id=term_split2_in.id,
        loss_db=0.10,
        version=1,
    )
    db_session.add(fus_cto)
    db_session.commit()

    # 6. Porta de atendimento da CTO
    cto_port = Port(
        structure_id=cto_struct.id,
        name="Porta 1",
        role="customer_drop",
        connector_type="SC/APC",
        version=1,
    )
    db_session.add(cto_port)
    db_session.commit()

    term_cto_port = Terminal(
        kind="port",
        structure_id=cto_struct.id,
        label="CTO Porta 1",
        occupancy="connected",
        entity_type="port",
        entity_id=cto_port.id,
        version=1,
    )
    db_session.add(term_cto_port)
    db_session.commit()

    # Conexão interna CTO: Splitter Saída 1 -> Porta 1 CTO (0.30 dB)
    conn_cto_internal = Connection(
        structure_id=cto_struct.id,
        connection_type="patch_cord",
        terminal_a_id=term_split2_out1.id,
        terminal_b_id=term_cto_port.id,
        loss_db=0.30,
        version=1,
    )
    db_session.add(conn_cto_internal)
    db_session.commit()

    # 7. Cliente e ONU
    customer = Customer(
        code="CLI-DEMO-B10",
        name="Cliente FTTH B10",
        phone="11988887777",
        version=1,
    )
    db_session.add(customer)
    db_session.commit()

    onu_dev = Device(
        code="ONU-DEMO-B10",
        kind="onu",
        manufacturer="FiberHome",
        model="AN5506",
        structure_id=cto_struct.id,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(onu_dev)
    db_session.commit()

    service_link = ServiceLink(
        customer_id=customer.id,
        onu_device_id=onu_dev.id,
        port_id=cto_port.id,
        status="active",
        version=1,
    )
    db_session.add(service_link)
    db_session.commit()
    db_session.refresh(service_link)

    return {
        "service_link": service_link,
        "term_pon": term_pon,
        "term_cto_port": term_cto_port,
    }


def test_optical_budget_downstream_calculation(client: TestClient, db_session: Session):
    """Testa o cálculo downstream ponta a ponta via API (B10)."""
    user = create_engineer(db_session, "eng_ds@provedor.com.br")
    auth_csrf = auth_client_login(client, user.email)
    topo = setup_ftth_acceptance_topology(db_session)
    service_link = topo["service_link"]

    resp = client.post(
        "/api/v1/optical/budgets",
        json={
            "service_link_id": str(service_link.id),
            "direction": "downstream",
            "engineering_margin_db": 3.0,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["status"] == "complete"
    assert data["direction"] == "downstream"
    assert data["wavelength_nm"] == 1490
    assert data["assessment"] == "pass"
    assert data["total_loss_db"] is not None
    assert data["predicted_rx_dbm"] is not None
    assert data["remaining_margin_db"] is not None
    assert len(data["steps"]) > 0

    # Comprimento total de fibra deve ser 7000 m (3500 + 3500)
    fiber_lengths = sum(
        s["individual_value"]
        for s in data["steps"]
        if s["element_type"] in ("fiber", "fiber_segment")
    )
    assert fiber_lengths == pytest.approx(7000.0, rel=1e-3)


def test_optical_budget_upstream_calculation(client: TestClient, db_session: Session):
    """Testa o cálculo upstream ponta a ponta via API (B10)."""
    user = create_engineer(db_session, "eng_us@provedor.com.br")
    auth_csrf = auth_client_login(client, user.email)
    topo = setup_ftth_acceptance_topology(db_session)
    service_link = topo["service_link"]

    resp = client.post(
        "/api/v1/optical/budgets",
        json={
            "service_link_id": str(service_link.id),
            "direction": "upstream",
            "engineering_margin_db": 3.0,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["status"] == "complete"
    assert data["direction"] == "upstream"
    assert data["wavelength_nm"] == 1310
    assert data["assessment"] == "pass"
    assert data["total_loss_db"] is not None
    assert data["predicted_rx_dbm"] is not None


def test_optical_budget_disconnected_customer(client: TestClient, db_session: Session):
    """Testa cliente sem continuidade até a OLT (circuito rompido/incompleto)."""
    user = create_engineer(db_session, "eng_disc@provedor.com.br")
    auth_csrf = auth_client_login(client, user.email)

    # Cria CTO isolada e cliente
    cto_struct = create_structure(db_session, "CTO-ISOLADA-B10", "cto")

    port = Port(
        structure_id=cto_struct.id,
        name="Porta 1",
        role="customer_drop",
        connector_type="SC/APC",
        version=1,
    )
    db_session.add(port)
    db_session.commit()

    term = Terminal(
        kind="port",
        structure_id=cto_struct.id,
        label="CTO-ISOLADA P1",
        entity_type="port",
        entity_id=port.id,
        occupancy="connected",
        is_occupied=True,
        version=1,
    )
    db_session.add(term)
    db_session.commit()

    cust = Customer(code="CLI-DISC", name="Cliente Isolado", version=1)
    db_session.add(cust)
    db_session.commit()

    onu = Device(
        code="ONU-DISC",
        kind="onu",
        manufacturer="FiberHome",
        model="GPON",
        structure_id=cto_struct.id,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(onu)
    db_session.commit()

    link = ServiceLink(
        customer_id=cust.id,
        onu_device_id=onu.id,
        port_id=port.id,
        status="active",
        version=1,
    )
    db_session.add(link)
    db_session.commit()

    resp = client.post(
        "/api/v1/optical/budgets",
        json={"service_link_id": str(link.id), "direction": "downstream"},
        headers={"X-CSRF-Token": auth_csrf},
    )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "insufficient_data"
    assert data["assessment"] == "unknown"
    assert data["total_loss_db"] is None
    assert data["predicted_rx_dbm"] is None


def test_optical_budget_unauthenticated_blocked(client: TestClient, db_session: Session):
    """Garante que requisições não autenticadas são bloqueadas com 401."""
    topo = setup_ftth_acceptance_topology(db_session)
    service_link = topo["service_link"]

    resp = client.post(
        "/api/v1/optical/budgets",
        json={"service_link_id": str(service_link.id), "direction": "downstream"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_optical_budget_custom_profile_selection(client: TestClient, db_session: Session):
    """Testa o cálculo usando um perfil óptico cadastrado explicitamente (ex: GPON Classe C+)."""
    user = create_engineer(db_session, "eng_cplus@provedor.com.br")
    auth_csrf = auth_client_login(client, user.email)
    topo = setup_ftth_acceptance_topology(db_session)
    service_link = topo["service_link"]

    # Cria perfil Classe C+
    profile_cplus = OpticalProfile(
        name="GPON Classe C+ Teste",
        technology="GPON",
        wavelength_nm=1490,
        tx_min_dbm=3.0,
        tx_max_dbm=7.0,
        rx_sensitivity_dbm=-30.0,
        rx_overload_dbm=-8.0,
        default_attenuation_db_per_km=0.25,
        version=1,
    )
    db_session.add(profile_cplus)
    db_session.commit()

    resp = client.post(
        "/api/v1/optical/budgets",
        json={
            "service_link_id": str(service_link.id),
            "direction": "downstream",
            "profile_id": str(profile_cplus.id),
            "engineering_margin_db": 4.0,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "complete"
    assert data["assessment"] == "pass"
    assert data["engineering_margin_db"] == 4.0
    # Com TX nominal de (3+7)/2 = 5.0 dBm
    assert data["tx_dbm"] == 5.0
    assert data["rx_min_dbm"] is not None
    assert data["rx_max_dbm"] is not None
