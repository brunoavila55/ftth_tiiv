import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Configurar ambiente de teste antes de importar a aplicação
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://ftth_user:ftth_password@127.0.0.1:5432/ftth_manager_test"
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.main import create_app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    with factory() as session:
        yield session


@pytest.fixture(autouse=True)
def clean_identity_tables(db_session: Session) -> Generator[None, None, None]:
    truncate_sql = text(
        "TRUNCATE TABLE cable_segments, cables, ports, devices, structures, sites, optical_profiles, user_sessions, login_attempts, users CASCADE;"
    )
    reset_topology_sql = text(
        "INSERT INTO network_topology_state (id, topology_revision, updated_at) "
        "VALUES (1, 1, NOW()) "
        "ON CONFLICT (id) DO UPDATE SET topology_revision = 1, updated_at = NOW();"
    )
    db_session.rollback()
    db_session.execute(truncate_sql)
    db_session.execute(reset_topology_sql)
    db_session.commit()
    yield
    db_session.rollback()
    db_session.execute(truncate_sql)
    db_session.execute(reset_topology_sql)
    db_session.commit()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
