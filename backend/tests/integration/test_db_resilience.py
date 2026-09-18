"""R15 (PERF-09/10/12/13): timeouts de banco, pool, readiness independente e /auth/me enxuto."""

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import build_engine, get_engine, set_engine_and_factory
from app.main import create_app
from app.modules.identity.models import UserSession
from tests.conftest import create_test_user, login_test_client
from tests.integration.test_dashboard_performance import StatementCounter

BACKEND_DIR = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------------------------
# PERF-12 — statement_timeout, connect_timeout, workers e pool por processo
# ---------------------------------------------------------------------------------------------


def test_default_timeouts_and_pool_sizing() -> None:
    settings = get_settings()
    assert settings.DB_STATEMENT_TIMEOUT_MS == 30_000
    assert settings.DB_WORKER_STATEMENT_TIMEOUT_MS == 600_000  # importações longas no worker
    assert settings.DB_CONNECT_TIMEOUT_SECONDS == 10
    # pool POR processo: com 2 workers ficam ≤ 20 conexões da API (postgres padrão: 100)
    assert settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW <= 10


def test_engine_applies_statement_timeout() -> None:
    engine = build_engine(statement_timeout_ms=300)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SHOW statement_timeout")).scalar() == "300ms"
            started = time.perf_counter()
            with pytest.raises(DBAPIError) as exc:
                conn.execute(text("SELECT pg_sleep(60)"))
            elapsed = time.perf_counter() - started
        assert "statement timeout" in str(exc.value.orig)
        assert elapsed < 3, f"a query de 60 s deveria ser cancelada em ~0,3 s (levou {elapsed:.1f}s)"
    finally:
        engine.dispose()


def test_application_and_worker_engines_use_different_timeouts() -> None:
    api = get_engine()
    with api.connect() as conn:
        assert conn.execute(text("SHOW statement_timeout")).scalar() == "30s"
    worker = build_engine(statement_timeout_ms=get_settings().DB_WORKER_STATEMENT_TIMEOUT_MS)
    try:
        with worker.connect() as conn:
            assert conn.execute(text("SHOW statement_timeout")).scalar() == "10min"
    finally:
        worker.dispose()


def test_connect_timeout_bounds_unreachable_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://u:p@10.255.255.1:5432/x"
    )  # IP sem rota: a conexão penduraria
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    engine = build_engine()
    started = time.perf_counter()
    with pytest.raises(OperationalError):
        engine.connect()
    assert time.perf_counter() - started < 5


def test_container_runs_uvicorn_with_configurable_workers() -> None:
    dockerfile = (BACKEND_DIR / "Dockerfile").read_text()
    assert "WEB_CONCURRENCY" in dockerfile and "--workers" in dockerfile


# ---------------------------------------------------------------------------------------------
# PERF-13 — readiness sem depender do pool da aplicação nem ler o Alembic a cada chamada
# ---------------------------------------------------------------------------------------------


def test_readiness_stays_fast_with_the_application_pool_saturated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DB_POOL_SIZE", "2")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "1")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "5")
    get_settings.cache_clear()
    original = get_engine()
    saturated = build_engine()
    set_engine_and_factory(saturated)
    held = [saturated.connect() for _ in range(3)]  # esgota pool_size + max_overflow
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            client.get("/health/ready")  # aquece o cache da head do Alembic
            started = time.perf_counter()
            resp = client.get("/health/ready")
            elapsed = time.perf_counter() - started
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert elapsed < 0.5, f"readiness levou {elapsed:.2f}s com o pool saturado"
    finally:
        for conn in held:
            conn.close()
        saturated.dispose()
        set_engine_and_factory(original)


def test_readiness_does_not_read_alembic_directory_per_call() -> None:
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        assert client.get("/health/ready").status_code == status.HTTP_200_OK  # aquecimento
        with patch("app.db.health.ScriptDirectory.from_config", side_effect=AssertionError("Alembic lido")):
            for _ in range(3):
                assert client.get("/health/ready").status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------------------------
# PERF-10 — /auth/me com 1 SELECT e last_activity_at com throttle
# ---------------------------------------------------------------------------------------------


def test_auth_me_executes_a_single_select(client: TestClient, db_session: Session) -> None:
    create_test_user(db_session, "me@provedor.com.br", "viewer")
    login_test_client(client, "me@provedor.com.br")
    with StatementCounter() as counter:
        resp = client.get("/api/v1/auth/me")
    assert resp.status_code == status.HTTP_200_OK
    assert counter.count == 1, f"{counter.count} statements em /auth/me"


def test_last_activity_is_updated_with_throttle(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session, "throttle@provedor.com.br", "viewer")
    login_test_client(client, "throttle@provedor.com.br")

    def last_activity() -> datetime:
        db_session.expire_all()
        row = db_session.query(UserSession).filter_by(user_id=user.id).one()
        return row.last_activity_at

    first = last_activity()
    client.get("/api/v1/auth/me")
    client.get("/api/v1/auth/me")
    assert last_activity() == first  # dentro da janela de 60 s: nenhuma escrita

    row = db_session.query(UserSession).filter_by(user_id=user.id).one()
    row.last_activity_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()
    stale = last_activity()
    with StatementCounter() as counter:
        client.get("/api/v1/auth/me")
    assert last_activity() > stale  # passou da janela: atualiza
    assert counter.count == 2  # SELECT + 1 UPDATE (commit único)


# ---------------------------------------------------------------------------------------------
# PERF-09 — bump_topology_revision é o último passo antes do commit
# ---------------------------------------------------------------------------------------------


def test_topology_revision_bump_is_the_last_step_before_commit(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Import: o bump da revisão (que trava a linha de estado) vem depois da auditoria."""
    import inspect

    from app.modules.jobs import service as jobs_service

    source = inspect.getsource(jobs_service.execute_import_commit)
    assert source.rindex("record_audit_event(") < source.rindex("bump_topology_revision(db)")
    assert "bump_revision=False" in source  # segmentos não bumpam a cada cabo importado
    _ = db_session, monkeypatch
