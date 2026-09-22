import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Configurar ambiente de teste antes de importar a aplicação
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ftth_user:ftth_password@127.0.0.1:5432/ftth_manager_test",
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage_backend import get_storage_backend
from app.db.session import get_session_factory
from app.main import create_app
from app.modules.identity.models import User  # noqa: E402


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    get_storage_backend.cache_clear()
    yield
    get_settings.cache_clear()
    get_storage_backend.cache_clear()


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator[None, None, None]:
    from app.core.rate_limit import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    with factory() as session:
        yield session


@pytest.fixture(autouse=True)
def clean_identity_tables(db_session: Session) -> Generator[None, None, None]:
    truncate_sql = text(
        "TRUNCATE TABLE app_settings, import_previews, async_jobs, attachments, optical_measurements, audit_events, service_links, customers, splitter_outputs, splitters, connections, fiber_segments, fibers, tubes, terminals, cable_segments, cables, ports, devices, structures, sites, optical_profiles, user_sessions, login_attempts, users CASCADE;"
    )
    reset_topology_sql = text(
        "INSERT INTO network_topology_state (id, topology_revision, updated_at) "
        "VALUES (1, 1, NOW()) "
        "ON CONFLICT (id) DO UPDATE SET topology_revision = 1, updated_at = NOW();"
    )
    reset_settings_sql = text(
        "INSERT INTO app_settings "
        "(id, organization_name, timezone, default_map_longitude, default_map_latitude, "
        "default_map_zoom, excess_loss_tolerance_db, version) VALUES "
        "('00000000-0000-0000-0000-000000000001', 'Operação FTTH', "
        "'America/Sao_Paulo', -53.0, -30.0, 7, 2.0, 1);"
    )
    db_session.rollback()
    db_session.execute(truncate_sql)
    db_session.execute(reset_topology_sql)
    db_session.execute(reset_settings_sql)
    db_session.commit()
    yield
    db_session.rollback()
    db_session.execute(truncate_sql)
    db_session.execute(reset_topology_sql)
    db_session.execute(reset_settings_sql)
    db_session.commit()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


DEFAULT_TEST_PASSWORD = "SenhaSegura123!"


def create_test_user(
    db_session: Session,
    email: str,
    role: str = "admin",
    password: str = DEFAULT_TEST_PASSWORD,
    name: str | None = None,
) -> User:
    """Cria (e comita) um usuário ativo para os testes de integração."""
    from app.core.security import hash_password
    from app.modules.identity.models import User

    user = User(
        email=email,
        name=name or f"User {role}",
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login_test_client(client: TestClient, email: str, password: str = DEFAULT_TEST_PASSWORD) -> str:
    """Faz login pelo fluxo real (CSRF + cookie) e devolve o token CSRF rotacionado."""
    csrf_resp = client.get("/api/v1/auth/csrf")
    assert csrf_resp.status_code == 200
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf_resp.json()["csrf_token"]},
    )
    assert login_resp.status_code == 200, login_resp.text
    rotated = client.cookies.get("ftth_csrf_token")
    assert rotated is not None
    return str(rotated)
