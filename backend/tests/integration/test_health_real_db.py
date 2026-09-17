from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.health import check_database_connectivity, check_database_migrations
from app.db.session import get_session_factory
from app.main import create_app


def test_postgis_extension_and_real_database_readiness() -> None:
    """Valida conexão real com PostgreSQL/PostGIS e status da migração aplicada."""
    factory = get_session_factory()
    with factory() as session:
        # Verifica extensão PostGIS
        postgis_version = session.execute(text("SELECT PostGIS_Version()")).scalar()
        assert postgis_version is not None
        assert "3." in str(postgis_version)

        # Checa conectividade
        conn_health = check_database_connectivity(session)
        assert conn_health["status"] == "connected"
        assert conn_health["latency_ms"] >= 0.0

        # Checa migrações
        mig_health = check_database_migrations(session)
        assert mig_health["status"] == "applied"
        assert mig_health["current_revision"] is not None
        assert mig_health["current_revision"].startswith("000")


def test_real_ready_endpoint_with_database() -> None:
    """Testa o endpoint /health/ready sem mocks contra o banco real."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/health/ready")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "ready"
        assert data["database"]["status"] == "connected"
        assert data["migrations"]["status"] == "applied"
        assert data["migrations"]["current_revision"] is not None
        assert data["migrations"]["current_revision"].startswith("000")
