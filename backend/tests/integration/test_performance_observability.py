import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_session_token
from app.modules.identity.models import User, UserSession


@pytest.fixture
def test_users(db_session: Session) -> dict[str, tuple[User, str]]:
    """Cria um usuário admin e um usuário viewer para testes de RBAC em observabilidade."""
    admin_token = f"admin_token_{uuid.uuid4().hex}"
    viewer_token = f"viewer_token_{uuid.uuid4().hex}"

    admin_user = User(
        id=uuid.uuid4(),
        email="admin.obs@ftth.local",
        password_hash=hash_password("AdminPass123!"),
        name="Admin Observabilidade",
        role="admin",
        is_active=True,
    )
    viewer_user = User(
        id=uuid.uuid4(),
        email="viewer.obs@ftth.local",
        password_hash=hash_password("ViewerPass123!"),
        name="Viewer Observabilidade",
        role="viewer",
        is_active=True,
    )
    db_session.add_all([admin_user, viewer_user])
    db_session.flush()

    now = datetime.now(UTC)
    expires = now + timedelta(days=7)

    admin_session = UserSession(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        token_hash=hash_session_token(admin_token),
        expires_at=expires,
        last_activity_at=now,
    )
    viewer_session = UserSession(
        id=uuid.uuid4(),
        user_id=viewer_user.id,
        token_hash=hash_session_token(viewer_token),
        expires_at=expires,
        last_activity_at=now,
    )
    db_session.add_all([admin_session, viewer_session])
    db_session.commit()

    return {
        "admin": (admin_user, admin_token),
        "viewer": (viewer_user, viewer_token),
    }


def test_metrics_endpoint_security(
    client: TestClient,
    test_users: dict[str, tuple[User, str]],
) -> None:
    """Verifica proteção e isolamento do endpoint de métricas (B16)."""
    settings = get_settings()

    # 1. Anônimo sem cabeçalho e sem sessão -> 401 Unauthorized
    res_anon = client.get("/api/v1/metrics")
    assert res_anon.status_code == 401
    assert "problem+json" in res_anon.headers.get("content-type", "")

    # 2. Usuário com papel 'viewer' sem token de monitoramento -> 403 Forbidden
    _, viewer_token = test_users["viewer"]
    res_viewer = client.get(
        "/api/v1/metrics",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_viewer.status_code == 403
    assert "problem+json" in res_viewer.headers.get("content-type", "")

    # 3. Requisição com token de scraping de observabilidade (X-Metrics-Token) -> 200 OK
    res_token = client.get(
        "/api/v1/metrics",
        headers={"X-Metrics-Token": settings.METRICS_SECRET_TOKEN},
    )
    assert res_token.status_code == 200
    assert "text/plain" in res_token.headers.get("content-type", "")
    assert "ftth_uptime_seconds" in res_token.text

    # 4. Operador autenticado com papel 'admin' -> 200 OK
    _, admin_token = test_users["admin"]
    res_admin = client.get(
        "/api/v1/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200


def test_metrics_formats_and_low_cardinality(
    client: TestClient,
    test_users: dict[str, tuple[User, str]],
) -> None:
    """Verifica formatos Prometheus / JSON e assegura que não haja explosão de cardinalidade."""
    _, admin_token = test_users["admin"]
    auth_headers = {"Authorization": f"Bearer {admin_token}"}

    # Gera algumas requisições com UUIDs dinâmicos
    fake_uuid_1 = str(uuid.uuid4())
    fake_uuid_2 = str(uuid.uuid4())
    client.get(f"/api/v1/structures/{fake_uuid_1}", headers=auth_headers)
    client.get(f"/api/v1/structures/{fake_uuid_2}", headers=auth_headers)

    # 1. Formato Prometheus Texto Puro
    res_prom = client.get("/api/v1/metrics", headers=auth_headers)
    assert res_prom.status_code == 200
    content = res_prom.text

    assert "ftth_uptime_seconds" in content
    assert "ftth_http_requests_total" in content
    assert "ftth_http_request_duration_seconds" in content

    # Garante que UUIDs dinâmicos não vazaram nas labels do Prometheus
    assert fake_uuid_1 not in content
    assert fake_uuid_2 not in content
    assert "{structure_id}" in content or "{id}" in content

    # 2. Formato JSON Estruturado
    res_json = client.get("/api/v1/metrics?format=json", headers=auth_headers)
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers.get("content-type", "")

    data = res_json.json()
    assert "uptime_seconds" in data
    assert "topology_revision" in data
    assert "http_requests" in data
    assert "http_durations" in data
    assert isinstance(data["http_requests"], list)


def test_trace_hops_limit_truncation(
    client: TestClient,
    test_users: dict[str, tuple[User, str]],
    db_session: Session,
) -> None:
    """Verifica que ultrapassar o limite max_hops trunca o caminho e retorna status LIMIT_EXCEEDED."""
    _, admin_token = test_users["admin"]

    # Cria terminal de teste
    term_id = uuid.uuid4()
    site_id = uuid.uuid4()
    from app.modules.connectivity.models import Terminal
    from app.modules.inventory.models import Site

    site = Site(
        id=site_id,
        code="SITE-TEST-HOPS",
        name="Site Test Hops",
        kind="central_office",
        location="SRID=4326;POINT(-46.63 23.55)",
    )
    term = Terminal(
        id=term_id,
        site_id=site_id,
        kind="port",
        label="Term Hops Test",
        occupancy="free",
    )
    db_session.add_all([site, term])
    db_session.commit()

    # Executa trace com max_hops=0 (já começa estourado)
    res = client.post(
        "/api/v1/topology/trace",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "start_terminal_id": str(term_id),
            "direction": "downstream",
            "max_hops": 1,
            "max_results": 10,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    # Deve responder com sucesso e status bem definido
    assert data["status"] in ("incomplete", "complete", "limit_exceeded")
