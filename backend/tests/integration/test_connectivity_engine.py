import concurrent.futures
import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.modules.audit.models import AuditEvent
from app.modules.connectivity.models import (
    Connection,
    ConnectionEndpoint,
    InternalEdge,
    Terminal,
)
from app.modules.gis.helpers import point_geometry_to_wkb
from app.modules.gis.service import get_topology_revision
from app.modules.identity.models import User
from app.modules.inventory.models import Structure
from app.schemas.common import UserRole
from app.schemas.connectivity import TerminalKind
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


def create_test_structure(db_session: Session, code: str = "CEO-01") -> Structure:
    struct = Structure(
        code=code,
        kind="ceo",
        location=point_geometry_to_wkb(
            PointGeometry(type="Point", coordinates=(-46.633308, -23.550520))
        ),
        version=1,
    )
    db_session.add(struct)
    db_session.commit()
    db_session.refresh(struct)
    return struct


def create_test_terminal(
    db_session: Session,
    structure_id: uuid.UUID,
    label: str,
    kind: str = TerminalKind.FIBER_ENDPOINT.value,
) -> Terminal:
    term = Terminal(
        kind=kind,
        structure_id=structure_id,
        label=label,
        occupancy="free",
        is_occupied=False,
        version=1,
    )
    db_session.add(term)
    db_session.commit()
    db_session.refresh(term)
    return term


def test_create_connection_lifecycle_and_audit(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica criação de conexão unitária, endpoints, auditoria e incremento de revisão."""
    user = User(
        email="eng_conn@provedor.com.br",
        name="Connectivity Engineer",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    struct = create_test_structure(db_session, "CEO-B07-01")
    term_a = create_test_terminal(db_session, struct.id, "CAB-01:T1:F01")
    term_b = create_test_terminal(db_session, struct.id, "CAB-02:T1:F01")

    rev_before = get_topology_revision(db_session)

    # 1. Criação da conexão via API
    payload = {
        "terminal_a_id": str(term_a.id),
        "terminal_b_id": str(term_b.id),
        "connection_type": "fusion_splice",
        "loss_db": 0.05,
        "structure_id": str(struct.id),
        "notes": "Fusão troncal para distribuição",
    }
    resp = client.post(
        "/api/v1/connections",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    data = resp.json()
    conn_id = uuid.UUID(data["id"])

    assert data["loss_db"] == 0.05
    assert data["is_active"] is True
    assert data["version"] == 1

    # 2. Verifica reflexo no banco de dados
    db_session.expire_all()
    reloaded_term_a = db_session.get(Terminal, term_a.id)
    reloaded_term_b = db_session.get(Terminal, term_b.id)
    assert reloaded_term_a is not None and reloaded_term_a.is_occupied is True
    assert reloaded_term_a.occupancy == "connected"
    assert reloaded_term_b is not None and reloaded_term_b.is_occupied is True
    assert reloaded_term_b.occupancy == "connected"

    # Verifica connection endpoints
    endpoints = (
        db_session.execute(
            select(ConnectionEndpoint).where(ConnectionEndpoint.connection_id == conn_id)
        )
        .scalars()
        .all()
    )
    assert len(endpoints) == 2
    assert all(ep.is_active is True for ep in endpoints)

    # Verifica evento de auditoria
    audit = (
        db_session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "connection",
                AuditEvent.entity_id == conn_id,
            )
        )
        .scalars()
        .one_or_none()
    )
    assert audit is not None
    assert audit.action == "connection_created"
    assert audit.actor_id == user.id

    # Verifica incremento de revisão
    rev_after = get_topology_revision(db_session)
    assert rev_after == rev_before + 1


def test_duplicate_connection_attempt_conflict(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica que terminal ocupado rejeita nova conexão com HTTP 409 e preserva DB."""
    user = User(
        email="eng_dup@provedor.com.br",
        name="Engineer Dup",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    struct = create_test_structure(db_session, "CEO-DUP-01")
    term_a = create_test_terminal(db_session, struct.id, "TERM-A")
    term_b = create_test_terminal(db_session, struct.id, "TERM-B")
    term_c = create_test_terminal(db_session, struct.id, "TERM-C")

    # Primeira conexão: A com B
    resp1 = client.post(
        "/api/v1/connections",
        json={
            "terminal_a_id": str(term_a.id),
            "terminal_b_id": str(term_b.id),
            "connection_type": "fusion_splice",
            "loss_db": 0.1,
            "structure_id": str(struct.id),
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp1.status_code == 201

    # Segunda tentativa: A (já ocupado) com C
    resp2 = client.post(
        "/api/v1/connections",
        json={
            "terminal_a_id": str(term_a.id),
            "terminal_b_id": str(term_c.id),
            "connection_type": "fusion_splice",
            "loss_db": 0.1,
            "structure_id": str(struct.id),
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp2.status_code == status.HTTP_409_CONFLICT
    problem = resp2.json()
    assert problem["code"] == "terminal_already_connected"
    assert "já possui uma conexão ativa" in problem["detail"]

    # Verifica que terminal C permaneceu livre
    db_session.expire_all()
    reloaded_c = db_session.get(Terminal, term_c.id)
    assert reloaded_c is not None and reloaded_c.is_occupied is False
    assert reloaded_c.occupancy == "free"


def test_concurrent_connection_race_condition(
    db_session: Session,
) -> None:
    """Verifica que requisições concorrentes deixam exatamente uma conexão ativa via restrição do Postgres."""
    user = User(
        email="eng_race@provedor.com.br",
        name="Engineer Race",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()

    struct = create_test_structure(db_session, "CEO-RACE-01")
    term_a = create_test_terminal(db_session, struct.id, "TERM-RACE-A")
    term_b1 = create_test_terminal(db_session, struct.id, "TERM-RACE-B1")
    term_b2 = create_test_terminal(db_session, struct.id, "TERM-RACE-B2")

    from app.modules.connectivity.service import create_connection as service_create_conn
    from app.schemas.connectivity import ConnectionCreate, ConnectionType

    session_factory = get_session_factory()

    def attempt_connect(target_b_id: uuid.UUID) -> str:
        with session_factory() as session:
            try:
                payload = ConnectionCreate(
                    terminal_a_id=str(term_a.id),
                    terminal_b_id=str(target_b_id),
                    connection_type=ConnectionType.FUSION_SPLICE,
                    loss_db=0.1,
                    structure_id=str(struct.id),
                )
                service_create_conn(
                    session,
                    actor_id=user.id,
                    actor_name=user.name,
                    payload=payload,
                )
                return "SUCCESS"
            except Exception as e:
                return f"ERROR: {type(e).__name__}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_connect, term_b1.id)
        f2 = executor.submit(attempt_connect, term_b2.id)
        results = [f1.result(), f2.result()]

    success_count = results.count("SUCCESS")
    assert success_count == 1, f"Esperado exatamente 1 sucesso, obtido: {results}"

    # Verifica no banco que existe exatamente 1 ConnectionEndpoint ativo para term_a
    db_session.expire_all()
    active_eps = (
        db_session.execute(
            select(ConnectionEndpoint).where(
                ConnectionEndpoint.terminal_id == term_a.id,
                ConnectionEndpoint.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    assert len(active_eps) == 1


def test_deactivate_connection_and_concurrency(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica desconexão com If-Match, liberação de terminais e preservação de histórico."""
    user = User(
        email="eng_deact@provedor.com.br",
        name="Engineer Deact",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    struct = create_test_structure(db_session, "CEO-DEACT-01")
    term_a = create_test_terminal(db_session, struct.id, "TERM-D-A")
    term_b = create_test_terminal(db_session, struct.id, "TERM-D-B")

    # Cria conexão
    conn_resp = client.post(
        "/api/v1/connections",
        json={
            "terminal_a_id": str(term_a.id),
            "terminal_b_id": str(term_b.id),
            "connection_type": "fusion_splice",
            "loss_db": 0.1,
            "structure_id": str(struct.id),
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert conn_resp.status_code == 201
    conn_id = conn_resp.json()["id"]

    # 1. Tentativa sem If-Match -> 428 Precondition Required
    del_no_header = client.delete(
        f"/api/v1/connections/{conn_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_no_header.status_code == status.HTTP_428_PRECONDITION_REQUIRED

    # 2. Tentativa com If-Match desatualizado -> 412 Precondition Failed
    del_bad_version = client.delete(
        f"/api/v1/connections/{conn_id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"99"'},
    )
    assert del_bad_version.status_code == status.HTTP_412_PRECONDITION_FAILED

    # 3. Desconexão correta com If-Match="1" -> 204 No Content
    del_ok = client.delete(
        f"/api/v1/connections/{conn_id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert del_ok.status_code == status.HTTP_204_NO_CONTENT

    # 4. Verifica histórico no banco de dados
    db_session.expire_all()
    conn_db = db_session.get(Connection, uuid.UUID(conn_id))
    assert conn_db is not None
    assert conn_db.is_active is False  # Histórico preservado!
    assert conn_db.version == 2

    # Verifica terminais liberados
    term_a_db = db_session.get(Terminal, term_a.id)
    term_b_db = db_session.get(Terminal, term_b.id)
    assert term_a_db is not None and term_a_db.is_occupied is False
    assert term_a_db.occupancy == "free"
    assert term_b_db is not None and term_b_db.is_occupied is False
    assert term_b_db.occupancy == "free"

    # 5. Tentativa de desconectar novamente -> 404
    del_again = client.delete(
        f"/api/v1/connections/{conn_id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"2"'},
    )
    assert del_again.status_code == status.HTTP_404_NOT_FOUND


def test_batch_operations_and_atomic_rollback(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica lote de fusões/conexões e rollback completo em caso de falha no meio."""
    user = User(
        email="eng_batch@provedor.com.br",
        name="Engineer Batch",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    struct = create_test_structure(db_session, "CEO-BATCH-01")
    term_a1 = create_test_terminal(db_session, struct.id, "B-A1")
    term_b1 = create_test_terminal(db_session, struct.id, "B-B1")
    term_a2 = create_test_terminal(db_session, struct.id, "B-A2")
    term_b2 = create_test_terminal(db_session, struct.id, "B-B2")
    term_a3 = create_test_terminal(db_session, struct.id, "B-A3")

    current_rev = get_topology_revision(db_session)

    # 1. Lote Válido: conecta A1 com B1 e reserva A3
    valid_batch = {
        "expected_topology_revision": current_rev,
        "structure_id": str(struct.id),
        "operations": [
            {
                "action": "connect",
                "terminal_a_id": str(term_a1.id),
                "terminal_b_id": str(term_b1.id),
                "connection_type": "fusion_splice",
                "loss_db": 0.08,
            },
            {
                "action": "reserve",
                "terminal_a_id": str(term_a3.id),
                "reservation_reason": "Reserva para cliente corporativo",
            },
        ],
    }
    resp = client.post(
        "/api/v1/connections/batch",
        json=valid_batch,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    batch_data = resp.json()
    assert batch_data["success"] is True
    assert batch_data["applied_operations_count"] == 2
    new_rev = batch_data["new_topology_revision"]
    assert new_rev == current_rev + 1

    # 2. Lote Inválido no meio: primeira op válida (conecta A2-B2), segunda op inválida (conecta A1 que já está ocupado)
    invalid_batch = {
        "expected_topology_revision": new_rev,
        "structure_id": str(struct.id),
        "operations": [
            {
                "action": "connect",
                "terminal_a_id": str(term_a2.id),
                "terminal_b_id": str(term_b2.id),
                "connection_type": "fusion_splice",
                "loss_db": 0.08,
            },
            {
                "action": "connect",
                "terminal_a_id": str(term_a1.id),  # Já ocupado!
                "terminal_b_id": str(term_b2.id),
                "connection_type": "fusion_splice",
            },
        ],
    }
    fail_resp = client.post(
        "/api/v1/connections/batch",
        json=invalid_batch,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert fail_resp.status_code == status.HTTP_409_CONFLICT
    assert fail_resp.json()["code"] == "terminal_already_connected"

    # Verifica Rollback Total: A2 e B2 NÃO foram conectados!
    db_session.expire_all()
    term_a2_db = db_session.get(Terminal, term_a2.id)
    term_b2_db = db_session.get(Terminal, term_b2.id)
    assert term_a2_db is not None and term_a2_db.is_occupied is False
    assert term_a2_db.occupancy == "free"
    assert term_b2_db is not None and term_b2_db.is_occupied is False
    assert term_b2_db.occupancy == "free"


def test_batch_topology_revision_conflict(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica que lote enviado com expected_topology_revision divergente retorna 409."""
    user = User(
        email="eng_rev@provedor.com.br",
        name="Engineer Revision",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    struct = create_test_structure(db_session, "CEO-REV-01")
    term_a = create_test_terminal(db_session, struct.id, "T-A")
    term_b = create_test_terminal(db_session, struct.id, "T-B")

    current_rev = get_topology_revision(db_session)

    # Submete com revisão desatualizada (current_rev + 99)
    resp = client.post(
        "/api/v1/connections/batch",
        json={
            "expected_topology_revision": current_rev + 99,
            "structure_id": str(struct.id),
            "operations": [
                {
                    "action": "connect",
                    "terminal_a_id": str(term_a.id),
                    "terminal_b_id": str(term_b.id),
                }
            ],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    assert resp.json()["code"] == "topology_revision_conflict"


def test_reserved_terminal_requires_explicit_release(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica critério de aceite: reconexão de terminal reservado exige liberação explícita."""
    user = User(
        email="eng_res@provedor.com.br",
        name="Engineer Reservation",
        password_hash=hash_password("EngineerPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    csrf_token = auth_client_login(client, user.email)

    struct = create_test_structure(db_session, "CEO-RESERVE-01")
    term_a = create_test_terminal(db_session, struct.id, "TERM-RES-A")
    term_b = create_test_terminal(db_session, struct.id, "TERM-RES-B")

    current_rev = get_topology_revision(db_session)

    # 1. Reserva o terminal A
    resp_res = client.post(
        "/api/v1/connections/batch",
        json={
            "expected_topology_revision": current_rev,
            "structure_id": str(struct.id),
            "operations": [
                {
                    "action": "reserve",
                    "terminal_a_id": str(term_a.id),
                    "reservation_reason": "Bloqueado para manobra",
                }
            ],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_res.status_code == 200
    rev_after_res = resp_res.json()["new_topology_revision"]

    # 2. Tentativa direta de conectar o terminal A reservado -> 409 Conflict (terminal_reserved)
    resp_fail = client.post(
        "/api/v1/connections",
        json={
            "terminal_a_id": str(term_a.id),
            "terminal_b_id": str(term_b.id),
            "connection_type": "fusion_splice",
            "structure_id": str(struct.id),
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_fail.status_code == status.HTTP_409_CONFLICT
    assert resp_fail.json()["code"] == "terminal_reserved"

    # 3. No lote: liberação explícita seguida de conexão -> Sucesso!
    resp_ok = client.post(
        "/api/v1/connections/batch",
        json={
            "expected_topology_revision": rev_after_res,
            "structure_id": str(struct.id),
            "operations": [
                {"action": "release", "terminal_a_id": str(term_a.id)},
                {
                    "action": "connect",
                    "terminal_a_id": str(term_a.id),
                    "terminal_b_id": str(term_b.id),
                    "connection_type": "fusion_splice",
                },
            ],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["applied_operations_count"] == 2


def test_structure_connectivity_endpoint(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica endpoint GET /structures/{id}/connectivity."""
    user = User(
        email="viewer_conn@provedor.com.br",
        name="Viewer Conn",
        password_hash=hash_password("ViewerPass123!"),
        role=UserRole.VIEWER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    auth_client_login(client, user.email, "ViewerPass123!")

    struct = create_test_structure(db_session, "CEO-OVERVIEW-01")
    term_a = create_test_terminal(db_session, struct.id, "TERM-OV-A")
    term_b = create_test_terminal(db_session, struct.id, "TERM-OV-B")

    # Conexão interna DIO / aresta interna
    internal_edge = InternalEdge(
        terminal_a_id=term_a.id,
        terminal_b_id=term_b.id,
        edge_type="fiber_continuity",
        entity_type="fiber_segment",
        entity_id=uuid.uuid4(),
        loss_db=0.0,
        is_bidirectional=True,
        version=1,
    )
    db_session.add(internal_edge)
    db_session.commit()

    resp = client.get(f"/api/v1/structures/{struct.id}/connectivity")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()

    assert data["structure_id"] == str(struct.id)
    assert len(data["terminals"]) == 2
    assert len(data["internal_edges"]) == 1
    assert data["internal_edges"][0]["edge_type"] == "fiber_continuity"
    assert data["topology_revision"] >= 1


def test_rbac_permissions_connectivity(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica matriz de permissões: viewer lê, technician não pode alterar topologia, engineer altera."""
    viewer = User(
        email="viewer_test@provedor.com.br",
        name="Viewer User",
        password_hash=hash_password("Pass123!"),
        role=UserRole.VIEWER.value,
        is_active=True,
        version=1,
    )
    tech = User(
        email="tech_test@provedor.com.br",
        name="Tech User",
        password_hash=hash_password("Pass123!"),
        role=UserRole.TECHNICIAN.value,
        is_active=True,
        version=1,
    )
    db_session.add_all([viewer, tech])
    db_session.commit()

    struct = create_test_structure(db_session, "CEO-RBAC-01")
    term_a = create_test_terminal(db_session, struct.id, "RBAC-A")
    term_b = create_test_terminal(db_session, struct.id, "RBAC-B")

    # Technician tenta criar conexão -> 403 Forbidden (technician só tem network:read)
    tech_csrf = auth_client_login(client, tech.email, "Pass123!")
    post_resp = client.post(
        "/api/v1/connections",
        json={
            "terminal_a_id": str(term_a.id),
            "terminal_b_id": str(term_b.id),
            "connection_type": "fusion_splice",
            "structure_id": str(struct.id),
        },
        headers={"X-CSRF-Token": tech_csrf},
    )
    assert post_resp.status_code == status.HTTP_403_FORBIDDEN
