import uuid
from datetime import UTC, datetime

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.customers.models import Customer, ServiceLink
from app.modules.gis.helpers import point_geometry_to_wkb
from app.modules.identity.models import User
from app.modules.inventory.models import Device, Port, Structure
from app.schemas.common import UserRole
from app.schemas.geojson import PointGeometry


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


def create_test_user(db_session: Session, email: str = "admin_b08@provedor.com.br") -> User:
    user = User(
        email=email,
        name="Admin B08",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_test_cto(db_session: Session, code: str = "CTO-B08-01") -> Structure:
    struct = Structure(
        code=code,
        kind="cto",
        location=point_geometry_to_wkb(
            PointGeometry(type="Point", coordinates=(-46.633308, -23.550520))
        ),
        capacity=8,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(struct)
    db_session.commit()
    db_session.refresh(struct)
    return struct


def create_test_ports(db_session: Session, structure: Structure, count: int = 8) -> list[Port]:
    ports = []
    for i in range(1, count + 1):
        port = Port(
            structure_id=structure.id,
            name=f"Porta {i}",
            role="customer_drop",
            connector_type="SC/APC",
            version=1,
        )
        db_session.add(port)
        ports.append(port)
    db_session.commit()
    for p in ports:
        db_session.refresh(p)
    return ports


def create_test_onu(db_session: Session, code: str, structure: Structure) -> Device:
    device = Device(
        code=code,
        kind="onu",
        manufacturer="FiberHome",
        model="AN5506-01-A",
        serial_number=f"SN-{code}",
        structure_id=structure.id,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


def test_customer_lifecycle_and_concurrency(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "user_cust@provedor.com.br")
    csrf_token = auth_client_login(client, user.email)

    # 1. Criação de cliente
    payload = {
        "code": "CLI-10001",
        "name": "João da Silva",
        "phone": "(11) 98765-4321",
        "email": "joao@email.com",
        "address": "Av. Paulista, 1000, Apto 51",
    }
    resp = client.post(
        "/api/v1/customers",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    cust_data = resp.json()
    cust_id = cust_data["id"]
    assert cust_data["code"] == "CLI-10001"
    assert cust_data["version"] == 1

    # 2. Tentativa de duplicar código -> 409 Conflict
    dup_resp = client.post(
        "/api/v1/customers",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT

    # 3. Busca por query 'q'
    search_resp = client.get(
        "/api/v1/customers?q=João",
    )
    assert search_resp.status_code == status.HTTP_200_OK
    assert search_resp.json()["total"] >= 1

    # 4. Atualização com If-Match correto
    update_resp = client.patch(
        f"/api/v1/customers/{cust_id}",
        json={"phone": "(11) 99999-8888"},
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["phone"] == "(11) 99999-8888"
    assert update_resp.json()["version"] == 2

    # 5. Tentativa com If-Match desatualizado -> 412 Precondition Failed
    stale_resp = client.patch(
        f"/api/v1/customers/{cust_id}",
        json={"name": "Outro Nome"},
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert stale_resp.status_code == status.HTTP_412_PRECONDITION_FAILED


def test_service_link_activation_and_concurrency_protection(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "user_links@provedor.com.br")
    csrf_token = auth_client_login(client, user.email)

    cto = create_test_cto(db_session, "CTO-SL-01")
    ports = create_test_ports(db_session, cto, 4)
    onu_1 = create_test_onu(db_session, "ONU-B08-01", cto)
    onu_2 = create_test_onu(db_session, "ONU-B08-02", cto)

    customer_1 = Customer(code="CLI-20001", name="Maria Souza", version=1)
    customer_2 = Customer(code="CLI-20002", name="Carlos Lima", version=1)
    db_session.add_all([customer_1, customer_2])
    db_session.commit()

    # 1. Ativa atendimento de customer_1 na porta 1 com onu_1
    link_payload = {
        "customer_id": str(customer_1.id),
        "onu_device_id": str(onu_1.id),
        "port_id": str(ports[0].id),
        "notes": "Instalação padrão 500 Mbps",
    }
    resp = client.post(
        "/api/v1/service-links",
        json=link_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    link_data = resp.json()
    link_id = link_data["id"]
    assert link_data["status"] == "active"
    assert link_data["version"] == 1

    # 2. Conflito: tentar ativar outro cliente (customer_2) na MESMA porta 1 -> 409 Conflict
    conflict_port = {
        "customer_id": str(customer_2.id),
        "onu_device_id": str(onu_2.id),
        "port_id": str(ports[0].id),
    }
    conf_port_resp = client.post(
        "/api/v1/service-links",
        json=conflict_port,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert conf_port_resp.status_code == status.HTTP_409_CONFLICT
    assert "já está associada a um atendimento ativo" in conf_port_resp.text

    # 3. Conflito: tentar ativar customer_2 na MESMA onu_1 em outra porta -> 409 Conflict
    conflict_onu = {
        "customer_id": str(customer_2.id),
        "onu_device_id": str(onu_1.id),
        "port_id": str(ports[1].id),
    }
    conf_onu_resp = client.post(
        "/api/v1/service-links",
        json=conflict_onu,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert conf_onu_resp.status_code == status.HTTP_409_CONFLICT
    assert "já está associado a outro atendimento ativo" in conf_onu_resp.text

    # 4. Tentar excluir customer_1 com atendimento ativo -> 409 Conflict
    del_cust_resp = client.delete(
        f"/api/v1/customers/{customer_1.id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert del_cust_resp.status_code == status.HTTP_409_CONFLICT
    assert "atendimento(s) óptico(s) ativo(s)" in del_cust_resp.text

    # 5. Desativar atendimento
    del_link_resp = client.delete(
        f"/api/v1/service-links/{link_id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert del_link_resp.status_code == status.HTTP_204_NO_CONTENT

    # Verifica que o service_link foi mantido no banco como deactivated (preservação de histórico)
    db_session.expire_all()
    link_db = db_session.get(ServiceLink, uuid.UUID(link_id))
    assert link_db is not None
    assert link_db.status == "deactivated"
    assert link_db.deactivated_at is not None

    # 6. Agora a porta 1 e onu_1 estão liberadas para novo atendimento!
    reuse_resp = client.post(
        "/api/v1/service-links",
        json=conflict_port,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert reuse_resp.status_code == status.HTTP_201_CREATED


def test_cto_occupancy_endpoint(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "user_occ@provedor.com.br")
    auth_client_login(client, user.email)

    cto = create_test_cto(db_session, "CTO-OCC-01")
    ports = create_test_ports(db_session, cto, 8)
    onu = create_test_onu(db_session, "ONU-OCC-01", cto)

    customer = Customer(code="CLI-30001", name="Empresa Teste", version=1)
    db_session.add(customer)
    db_session.commit()

    # Cria atendimento ativo na porta 0
    link = ServiceLink(
        customer_id=customer.id,
        onu_device_id=onu.id,
        port_id=ports[0].id,
        status="active",
        activated_at=datetime.now(UTC),
        version=1,
    )
    db_session.add(link)
    db_session.commit()

    resp = client.get(f"/api/v1/structures/{cto.id}/cto-occupancy")
    assert resp.status_code == status.HTTP_200_OK
    occ_data = resp.json()
    assert occ_data["total_ports"] == 8
    assert occ_data["occupied_ports"] == 1
    assert occ_data["free_ports"] == 7
    assert len(occ_data["ports"]) == 8


def test_cto_occupancy_acceptance_criteria_8_ports_3_connected_1_reserved_4_free(
    client: TestClient,
    db_session: Session,
) -> None:
    """Valida o critério de aceite F11: CTO de 8 portas com 3 conectadas e 1 reservada mostra 4 livres."""
    from app.modules.connectivity.models import Connection, Terminal, TerminalReservation

    user = create_test_user(db_session, "user_f11_accept@provedor.com.br")
    auth_client_login(client, user.email)

    cto = create_test_cto(db_session, "CTO-F11-01")
    ports = create_test_ports(db_session, cto, 8)

    # Cria terminais para as portas
    terminals = []
    for p in ports:
        t = Terminal(
            kind="port",
            structure_id=cto.id,
            label=f"{cto.code} - {p.name}",
            occupancy="free",
            entity_type="port",
            entity_id=p.id,
            version=1,
        )
        db_session.add(t)
        terminals.append(t)
    db_session.commit()

    # 1. Porta 0 e Porta 1 conectadas a clientes (2 conexões com cliente)
    onu1 = create_test_onu(db_session, "ONU-F11-01", cto)
    onu2 = create_test_onu(db_session, "ONU-F11-02", cto)
    cust1 = Customer(code="CLI-F11-01", name="Assinante 1", version=1)
    cust2 = Customer(code="CLI-F11-02", name="Assinante 2", version=1)
    db_session.add_all([cust1, cust2])
    db_session.commit()

    link1 = ServiceLink(
        customer_id=cust1.id,
        onu_device_id=onu1.id,
        port_id=ports[0].id,
        status="active",
        activated_at=datetime.now(UTC),
        version=1,
    )
    link2 = ServiceLink(
        customer_id=cust2.id,
        onu_device_id=onu2.id,
        port_id=ports[1].id,
        status="active",
        activated_at=datetime.now(UTC),
        version=1,
    )
    terminals[0].occupancy = "connected"
    terminals[1].occupancy = "connected"
    db_session.add_all([link1, link2, terminals[0], terminals[1]])
    db_session.commit()

    # 2. Porta 2 conectada sem cliente (3ª conexão)
    term_drop = Terminal(
        kind="fiber",
        structure_id=cto.id,
        label="Drop Cabo 01 - FO #1",
        occupancy="connected",
        version=1,
    )
    db_session.add(term_drop)
    db_session.commit()
    conn_no_client = Connection(
        structure_id=cto.id,
        terminal_a_id=terminals[2].id,
        terminal_b_id=term_drop.id,
        connection_type="drop_patch",
        loss_db=0.2,
        is_active=True,
        version=1,
    )
    terminals[2].occupancy = "connected"
    db_session.add_all([conn_no_client, terminals[2]])
    db_session.commit()

    # 3. Porta 3 reservada (1 reservada)
    terminals[3].occupancy = "reserved"
    reservation = TerminalReservation(
        terminal_id=terminals[3].id,
        reason="Reserva técnica para expansão corporativa",
        reserved_by_id=user.id,
        is_active=True,
        version=1,
    )
    db_session.add_all([reservation, terminals[3]])

    # 4. Porta 7 danificada (mas livre para demonstrar que estado danificado é separado de ocupação)
    ports[7].notes = "[Danificada] Trava mecânica quebrada pelo técnico"
    db_session.add(ports[7])
    db_session.commit()

    # Consulta ocupação
    resp = client.get(f"/api/v1/structures/{cto.id}/cto-occupancy")
    assert resp.status_code == status.HTTP_200_OK
    occ = resp.json()

    # Total 8 portas: 3 conectadas (2 com cliente + 1 sem cliente), 1 reservada, 4 livres!
    assert occ["total_ports"] == 8
    assert occ["occupied_ports"] == 3
    assert occ["connected_without_customer"] == 1
    assert occ["reserved_ports"] == 1
    assert occ["free_ports"] == 4

    # Valida detalhamento das portas
    ports_map = {p["name"]: p for p in occ["ports"]}
    assert ports_map["Porta 1"]["status"] == "customer_connected"
    assert ports_map["Porta 1"]["customer"]["name"] == "Assinante 1"
    assert ports_map["Porta 2"]["status"] == "customer_connected"
    assert ports_map["Porta 3"]["status"] == "connected_no_customer"
    assert ports_map["Porta 4"]["status"] == "reserved"
    assert (
        ports_map["Porta 4"]["reservation"]["reason"] == "Reserva técnica para expansão corporativa"
    )
    assert ports_map["Porta 5"]["status"] == "free"
    assert ports_map["Porta 8"]["status"] == "free"
    assert ports_map["Porta 8"]["is_damaged"] is True


def test_delete_customer_with_historical_links_is_conflict_not_500(
    client: TestClient, db_session: Session
) -> None:
    """N-01: vínculos desativados mantêm a FK (RESTRICT) — a exclusão deve virar 409, não 500."""
    user = create_test_user(db_session, "user_del_hist@provedor.com.br")
    csrf_token = auth_client_login(client, user.email)
    cto = create_test_cto(db_session, "CTO-HIST-01")
    port = create_test_ports(db_session, cto, 1)[0]
    onu = create_test_onu(db_session, "ONU-HIST-01", cto)
    customer = Customer(code="CLI-HIST-01", name="Cliente Histórico", version=1)
    db_session.add(customer)
    db_session.commit()
    db_session.add(
        ServiceLink(
            customer_id=customer.id,
            onu_device_id=onu.id,
            port_id=port.id,
            status="inactive",
            deactivated_at=datetime.now(UTC),
            version=1,
        )
    )
    db_session.commit()

    resp = client.delete(
        f"/api/v1/customers/{customer.id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT, resp.text
    assert "histór" in resp.json()["detail"]
    db_session.expire_all()
    assert db_session.get(Customer, customer.id) is not None


def test_delete_customer_without_links_still_works(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session, "user_del_ok@provedor.com.br")
    csrf_token = auth_client_login(client, user.email)
    customer = Customer(code="CLI-DEL-OK", name="Sem Vínculos", version=1)
    db_session.add(customer)
    db_session.commit()

    resp = client.delete(
        f"/api/v1/customers/{customer.id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT, resp.text
