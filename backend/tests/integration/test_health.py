from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


def test_health_live_endpoint(client: TestClient) -> None:
    resp = client.get("/health/live")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"status": "alive"}

    # Também testar rota montada sob /api/v1/health/live
    resp_v1 = client.get("/api/v1/health/live")
    assert resp_v1.status_code == status.HTTP_200_OK
    assert resp_v1.json() == {"status": "alive"}


def test_health_ready_fails_when_db_is_unavailable() -> None:
    """Readiness deve falhar com 503 quando o banco de dados estiver inacessível."""
    mock_session = MagicMock()

    with patch("app.api.v1.health.check_database_connectivity") as mock_conn:
        mock_conn.return_value = {
            "status": "disconnected",
            "message": "Não foi possível conectar ao banco de dados",
        }

        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/health/ready")
                assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                data = resp.json()
                assert data["status"] == "unhealthy"
                assert data["database"]["status"] == "disconnected"
                # Nenhuma credencial ou URL sensível exposta
                assert "password" not in str(data).lower()
                assert "postgresql" not in str(data).lower()
        finally:
            app.dependency_overrides.clear()


def test_health_ready_succeeds_when_db_and_migrations_are_ready() -> None:
    """Readiness deve retornar 200 quando o banco e as migrações estiverem saudáveis."""
    mock_session = MagicMock()

    with (
        patch("app.api.v1.health.check_database_connectivity") as mock_conn,
        patch("app.api.v1.health.check_database_migrations") as mock_mig,
    ):
        mock_conn.return_value = {"status": "connected", "latency_ms": 1.5}
        mock_mig.return_value = {
            "status": "applied",
            "current_revision": "0001_initial_postgis",
            "expected_revision": "0001_initial_postgis",
        }

        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/health/ready")
                assert resp.status_code == status.HTTP_200_OK
                data = resp.json()
                assert data["status"] == "ready"
                assert data["database"]["status"] == "connected"
                assert data["migrations"]["status"] == "applied"
        finally:
            app.dependency_overrides.clear()
