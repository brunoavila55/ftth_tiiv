"""Testes de integração para Busca Global, Painel de Indicadores e Relatórios (B15).

Cobre:
- Resumo consolidado do dashboard com contadores reais, faixas de ocupação de CTOs
  (0%, 1-50%, 51-99%, 100%) e alertas automáticos de inconsistências técnicas.
- Busca global textual com correspondência em sites, estruturas, cabos, dispositivos (código, modelo, serial)
  e clientes (com proteção estrita de RBAC para LGPD).
- Relatórios paginados e filtráveis de CTOs (/reports/ctos), cabos (/reports/cables)
  e inconsistências (/reports/inconsistencies).
- Restrições de autenticação e permissões RBAC (reports:read).
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.cables.models import Cable, Fiber, Tube
from app.modules.connectivity.models import Terminal, TerminalReservation
from app.modules.customers.models import Customer, ServiceLink
from app.modules.gis.helpers import point_geometry_to_wkb
from app.modules.identity.models import User
from app.modules.inventory.models import Device, Port, Site, Structure
from app.schemas.common import UserRole
from app.schemas.geojson import PointGeometry


def auth_client_login(client: TestClient, email: str, password: str = "AdminPass123!") -> str:
    csrf_resp = client.get("/api/v1/auth/csrf")
    assert csrf_resp.status_code == status.HTTP_200_OK
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


def create_user(db_session: Session, email: str, role: UserRole) -> User:
    user = User(
        email=email,
        name=f"User {role.value}",
        password_hash=hash_password("AdminPass123!"),
        role=role.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_site(db_session: Session, code: str = "SITE-CENTRAL", name: str = "Central SP") -> Site:
    site = Site(
        code=code,
        name=name,
        location=point_geometry_to_wkb(
            PointGeometry(type="Point", coordinates=(-46.633308, -23.550520))
        ),
        status="active",
        version=1,
    )
    db_session.add(site)
    db_session.commit()
    db_session.refresh(site)
    return site


def create_cto_with_ports(
    db_session: Session,
    code: str,
    site_id: uuid.UUID | None = None,
    port_count: int = 4,
    status: str = "installed",
) -> tuple[Structure, list[Port], list[Terminal]]:
    cto = Structure(
        code=code,
        kind="cto",
        location=point_geometry_to_wkb(
            PointGeometry(type="Point", coordinates=(-46.633308, -23.550520))
        ),
        capacity=port_count,
        site_id=site_id,
        status=status,
        condition="ok",
        version=1,
    )
    db_session.add(cto)
    db_session.commit()
    db_session.refresh(cto)

    ports: list[Port] = []
    terminals: list[Terminal] = []
    for i in range(1, port_count + 1):
        port = Port(
            structure_id=cto.id,
            name=f"P{i}",
            role="customer_drop",
            connector_type="SC/APC",
            version=1,
        )
        db_session.add(port)
        db_session.commit()
        db_session.refresh(port)
        ports.append(port)

        term = Terminal(
            kind="port",
            structure_id=cto.id,
            entity_type="port",
            entity_id=port.id,
            label=f"{cto.code}-P{i}",
            occupancy="free",
            is_occupied=False,
            version=1,
        )
        db_session.add(term)
        db_session.commit()
        db_session.refresh(term)
        terminals.append(term)

    return cto, ports, terminals


def test_dashboard_summary_with_real_buckets_and_alerts(
    client: TestClient, db_session: Session
) -> None:
    """Verifica contadores reais, distribuição nas 4 faixas de ocupação de CTOs e alertas técnicos."""
    site = create_site(db_session, code="SITE-DASH-01", name="POP Principal")

    # CTO 1: 4 portas, 0 ocupadas -> Bucket 0% (empty_0_pct)
    create_cto_with_ports(db_session, code="CTO-DASH-01", site_id=site.id, port_count=4)

    # CTO 2: 4 portas, 1 ocupada (25%) -> Bucket 1-50% (low_1_to_50_pct)
    _, p2_ports, p2_terms = create_cto_with_ports(
        db_session, code="CTO-DASH-02", site_id=site.id, port_count=4
    )
    # Marcar 1 porta como conectada via Terminal
    p2_terms[0].occupancy = "connected"
    db_session.commit()

    # CTO 3: 4 portas, 3 ocupadas (75%) -> Bucket 51-99% (high_51_to_99_pct)
    _, p3_ports, p3_terms = create_cto_with_ports(
        db_session, code="CTO-DASH-03", site_id=site.id, port_count=4
    )
    p3_terms[0].occupancy = "customer_connected"
    p3_terms[1].occupancy = "connected"
    # Port 3 ocupada por TerminalReservation
    res = TerminalReservation(
        terminal_id=p3_terms[2].id,
        reason="Reserva técnica",
        is_active=True,
    )
    db_session.add(res)
    db_session.commit()

    # CTO 4: 4 portas, 4 ocupadas (100%) -> Bucket 100% (full_100_pct)
    _, p4_ports, p4_terms = create_cto_with_ports(
        db_session, code="CTO-DASH-04", site_id=site.id, port_count=4
    )
    # Criar ONU para vincular ao ServiceLink
    onu = Device(
        code="ONU-DASH-01",
        site_id=site.id,
        kind="onu",
        manufacturer="Huawei",
        model="EG8145V5",
        status="active",
        version=1,
    )
    db_session.add(onu)
    db_session.commit()
    db_session.refresh(onu)

    # Cliente e link de serviço ativo na porta 0
    customer = Customer(
        code="CLI-DASH-01",
        name="Cliente Dashboard",
        phone="11999999999",
        email="cliente@dashboard.com",
        version=1,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    link = ServiceLink(
        customer_id=customer.id,
        onu_device_id=onu.id,
        port_id=p4_ports[0].id,
        status="active",
        version=1,
    )
    db_session.add(link)
    p4_terms[1].occupancy = "connected"
    p4_terms[2].occupancy = "customer_connected"
    p4_terms[3].occupancy = "connected"
    db_session.commit()

    # Cabo sem segmentos (para gerar alerta)
    cable = Cable(
        code="CAB-UNSEG-01",
        model="AS-80",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(cable)

    # Estrutura sem site_id (para gerar alerta)
    struct_no_site = Structure(
        code="POSTE-NO-SITE",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(type="Point", coordinates=(-46.63, -23.55))),
        capacity=0,
        site_id=None,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(struct_no_site)
    db_session.commit()
    db_session.refresh(struct_no_site)

    # Porta com anotação de defeito (para gerar alerta)
    damaged_port = Port(
        structure_id=struct_no_site.id,
        name="P-DANIFICADA",
        role="customer_drop",
        connector_type="SC/APC",
        notes="Conector quebrado no engate",
        version=1,
    )
    db_session.add(damaged_port)
    db_session.commit()

    # O painel exige sessão com reports:read (R03 / SEC-01)
    assert client.get("/api/v1/dashboard/summary").status_code == status.HTTP_401_UNAUTHORIZED
    create_user(db_session, "viewer_dashboard@provedor.com.br", UserRole.VIEWER)
    auth_client_login(client, "viewer_dashboard@provedor.com.br")

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total_sites"] == 1
    assert data["total_structures"] == 5  # 4 CTOs + 1 POSTE-NO-SITE
    assert data["total_cables"] == 1
    assert data["total_customers"] == 1
    assert data["total_active_service_links"] == 1

    buckets = data["ctos_occupancy"]
    assert buckets["empty_0_pct"] == 1
    assert buckets["low_1_to_50_pct"] == 1
    assert buckets["high_51_to_99_pct"] == 1
    assert buckets["full_100_pct"] == 1

    alerts = data["incomplete_documentation_alerts"]
    assert any("sem nenhum segmento" in a for a in alerts)
    assert any("sem POP / Site" in a for a in alerts)
    assert any("anotação de dano ou defeito" in a for a in alerts)


def test_global_search_across_entities_and_rbac(client: TestClient, db_session: Session) -> None:
    """Valida busca textual em sites, estruturas, cabos, dispositivos e clientes com RBAC."""
    site = create_site(db_session, code="SITE-ALPHA-01", name="POP Alpha Central")
    cto, _, _ = create_cto_with_ports(db_session, code="CTO-ALPHA-99", site_id=site.id)

    cable = Cable(
        code="CAB-ALPHA-12F",
        model="AS-120-ALPHA",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(cable)

    dev = Device(
        code="OLT-ALPHA-01",
        site_id=site.id,
        manufacturer="Huawei",
        model="MA5800-ALPHA",
        serial_number="HWTC-SN-9988-ALPHA",
        kind="olt",
        status="active",
        version=1,
    )
    db_session.add(dev)

    cust = Customer(
        code="CLI-ALPHA-001",
        name="Alpha Cliente Telecom",
        phone="11988887777",
        email="alpha@cliente.com.br",
        version=1,
    )
    db_session.add(cust)
    db_session.commit()

    # 1. Usuário anônimo: busca global exige autenticação (R03 / SEC-01)
    resp_anon = client.get("/api/v1/search?q=ALPHA")
    assert resp_anon.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Usuário VIEWER:
    # Não possui customers:read, portanto também não deve ver clientes
    create_user(db_session, "viewer_search@provedor.com.br", UserRole.VIEWER)
    auth_client_login(client, "viewer_search@provedor.com.br")

    resp_viewer = client.get("/api/v1/search?q=ALPHA")
    assert resp_viewer.status_code == status.HTTP_200_OK
    data_viewer = resp_viewer.json()
    entity_types_viewer = [g["entity_type"] for g in data_viewer["groups"]]
    assert "customer" not in entity_types_viewer

    # 3. Usuário ADMIN:
    # Possui customers:read, logo deve ver o grupo de clientes
    client.cookies.clear()
    create_user(db_session, "admin_search@provedor.com.br", UserRole.ADMIN)
    auth_client_login(client, "admin_search@provedor.com.br")

    resp_admin = client.get("/api/v1/search?q=ALPHA")
    assert resp_admin.status_code == status.HTTP_200_OK
    data_admin = resp_admin.json()
    entity_types_admin = [g["entity_type"] for g in data_admin["groups"]]
    assert "customer" in entity_types_admin

    cust_group = next(g for g in data_admin["groups"] if g["entity_type"] == "customer")
    assert any(c["code"] == "CLI-ALPHA-001" for c in cust_group["items"])

    # 4. Busca direta por serial_number do dispositivo
    resp_sn = client.get("/api/v1/search?q=9988-ALPHA")
    assert resp_sn.status_code == status.HTTP_200_OK
    data_sn = resp_sn.json()
    assert any(g["entity_type"] == "device" for g in data_sn["groups"])
    dev_group = next(g for g in data_sn["groups"] if g["entity_type"] == "device")
    assert dev_group["items"][0]["code"] == "OLT-ALPHA-01"


def test_reports_ctos_endpoint_pagination_and_filters(
    client: TestClient, db_session: Session
) -> None:
    """Testa endpoint /reports/ctos: autenticação, filtros por site e ocupação, e paginação."""
    # 1. Sem autenticação deve retornar 401
    unauth_resp = client.get("/api/v1/reports/ctos")
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Autenticar como operador com permissão reports:read (VIEWER é suficiente)
    create_user(db_session, "viewer_ctos@provedor.com.br", UserRole.VIEWER)
    auth_client_login(client, "viewer_ctos@provedor.com.br")

    site_a = create_site(db_session, code="SITE-A", name="Site A")
    site_b = create_site(db_session, code="SITE-B", name="Site B")

    # CTO 1 no Site A (0% ocupada)
    create_cto_with_ports(db_session, code="CTO-A-01", site_id=site_a.id, port_count=8)

    # CTO 2 no Site A (50% ocupada: 4/8)
    _, _, p2_terms = create_cto_with_ports(
        db_session, code="CTO-A-02", site_id=site_a.id, port_count=8
    )
    for i in range(4):
        p2_terms[i].occupancy = "connected"
    db_session.commit()

    # CTO 3 no Site B (100% ocupada: 8/8)
    _, _, p3_terms = create_cto_with_ports(
        db_session, code="CTO-B-01", site_id=site_b.id, port_count=8
    )
    for i in range(8):
        p3_terms[i].occupancy = "connected"
    db_session.commit()

    # Busca todas
    resp_all = client.get("/api/v1/reports/ctos?page=1&page_size=10")
    assert resp_all.status_code == status.HTTP_200_OK
    data_all = resp_all.json()
    assert data_all["total"] == 3
    assert len(data_all["items"]) == 3

    # Filtrar por site_id
    resp_site_a = client.get(f"/api/v1/reports/ctos?site_id={site_a.id}")
    assert resp_site_a.status_code == status.HTTP_200_OK
    data_site_a = resp_site_a.json()
    assert data_site_a["total"] == 2
    assert all(item["site_id"] == str(site_a.id) for item in data_site_a["items"])

    # Filtrar por faixa de ocupação (>= 50%)
    resp_occ = client.get("/api/v1/reports/ctos?min_occupancy_pct=50")
    assert resp_occ.status_code == status.HTTP_200_OK
    data_occ = resp_occ.json()
    assert data_occ["total"] == 2
    assert all(item["occupancy_pct"] >= 50.0 for item in data_occ["items"])

    # UUID inválido retorna 422
    resp_invalid_site = client.get("/api/v1/reports/ctos?site_id=not-a-uuid")
    assert resp_invalid_site.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_reports_cables_endpoint_and_usage(client: TestClient, db_session: Session) -> None:
    """Testa endpoint /reports/cables: autenticação, cálculo de fibras e filtros."""
    # 1. Sem autenticação -> 401
    unauth_resp = client.get("/api/v1/reports/cables")
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED

    create_user(db_session, "technician_cables@provedor.com.br", UserRole.TECHNICIAN)
    auth_client_login(client, "technician_cables@provedor.com.br")

    # Criar cabo com tubos e fibras
    cable = Cable(
        code="CAB-TRUNK-01",
        model="AS-24F",
        fiber_count=4,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(cable)
    db_session.commit()

    tube = Tube(cable_id=cable.id, number=1, color_name="Verde", version=1)
    db_session.add(tube)
    db_session.commit()

    fibers = []
    for f_idx in range(1, 5):
        fiber = Fiber(
            cable_id=cable.id,
            tube_id=tube.id,
            global_number=f_idx,
            tube_position=f_idx,
            color_name="Verde",
            version=1,
        )
        db_session.add(fiber)
        fibers.append(fiber)
    db_session.commit()

    site = create_site(db_session, code="SITE-CAB-01", name="POP Cabos")

    # Criar terminais de fibra
    # Fibra 1: conectada
    t1 = Terminal(
        kind="fiber_endpoint",
        site_id=site.id,
        entity_type="fiber",
        entity_id=fibers[0].id,
        label="F1",
        occupancy="connected",
        is_occupied=True,
        version=1,
    )
    # Fibra 2: reservada
    t2 = Terminal(
        kind="fiber_endpoint",
        site_id=site.id,
        entity_type="fiber",
        entity_id=fibers[1].id,
        label="F2",
        occupancy="reserved",
        is_occupied=True,
        version=1,
    )
    # Fibra 3: danificada
    t3 = Terminal(
        kind="fiber_endpoint",
        site_id=site.id,
        entity_type="fiber",
        entity_id=fibers[2].id,
        label="F3",
        occupancy="damaged",
        is_occupied=True,
        version=1,
    )
    # Fibra 4: livre (free)
    t4 = Terminal(
        kind="fiber_endpoint",
        site_id=site.id,
        entity_type="fiber",
        entity_id=fibers[3].id,
        label="F4",
        occupancy="free",
        is_occupied=False,
        version=1,
    )
    db_session.add_all([t1, t2, t3, t4])
    db_session.commit()

    # Cabo 2 vazio
    cable2 = Cable(
        code="CAB-EMPTY-01",
        model="AS-12F",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(cable2)
    db_session.commit()

    resp = client.get("/api/v1/reports/cables?page=1&page_size=10")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 2

    cable_item = next(c for c in data["items"] if c["code"] == "CAB-TRUNK-01")
    assert cable_item["total_fibers"] == 4
    assert cable_item["connected_fibers"] == 1
    assert cable_item["reserved_fibers"] == 1
    assert cable_item["damaged_fibers"] == 1
    assert cable_item["free_fibers"] == 1
    # usage_pct: (1 + 1) / 4 * 100 = 50.0%
    assert cable_item["usage_pct"] == 50.0

    # Filtro por min_usage_pct
    resp_filtered = client.get("/api/v1/reports/cables?min_usage_pct=40")
    assert resp_filtered.status_code == status.HTTP_200_OK
    assert resp_filtered.json()["total"] == 1
    assert resp_filtered.json()["items"][0]["code"] == "CAB-TRUNK-01"


def test_reports_inconsistencies_endpoint(client: TestClient, db_session: Session) -> None:
    """Testa endpoint /reports/inconsistencies identificando anomalias na malha óptica."""
    # 1. Sem autenticação -> 401
    unauth_resp = client.get("/api/v1/reports/inconsistencies")
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED

    create_user(db_session, "engineer_incons@provedor.com.br", UserRole.ENGINEER)
    auth_client_login(client, "engineer_incons@provedor.com.br")

    # Criar anomalias:
    # A. Cabo sem segmentos
    cable = Cable(
        code="CAB-NO-SEG",
        model="AS-12F",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(cable)

    # B. Estrutura sem site pai
    struct = Structure(
        code="POSTE-SOLTO",
        kind="pole",
        location=point_geometry_to_wkb(PointGeometry(type="Point", coordinates=(-46.63, -23.55))),
        capacity=0,
        site_id=None,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(struct)
    db_session.commit()
    db_session.refresh(struct)

    # C. Porta física danificada
    port = Port(
        structure_id=struct.id,
        name="P-DEFEITO",
        role="customer_drop",
        connector_type="SC/APC",
        notes="Porta com defeito óptico e ferrolho quebrado",
        version=1,
    )
    db_session.add(port)
    db_session.commit()

    resp = client.get("/api/v1/reports/inconsistencies")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 3

    inc_types = [item["inconsistency_type"] for item in data["items"]]
    assert "cable_without_segments" in inc_types
    assert "structure_without_site" in inc_types
    assert "damaged_port" in inc_types
