"""R24 (PERF-11): retenção de login_attempts e sessões, sem tocar na trilha de auditoria."""

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.audit.models import AuditEvent
from app.modules.identity.models import LoginAttempt, User, UserSession
from app.modules.retention.service import run_retention
from tests.conftest import create_test_user

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
WORKER_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_worker.py"


def attempt(db: Session, age_days: float, email: str = "x@y.com") -> None:
    db.add(
        LoginAttempt(
            ip_address="203.0.113.1",
            email=email,
            attempted_at=NOW - timedelta(days=age_days),
            success=False,
        )
    )


def session_row(
    db: Session,
    user: User,
    *,
    expires_in_days: float,
    revoked: bool,
    last_activity_days_ago: float,
) -> UserSession:
    row = UserSession(
        user_id=user.id,
        token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        created_at=NOW - timedelta(days=30),
        last_activity_at=NOW - timedelta(days=last_activity_days_ago),
        expires_at=NOW + timedelta(days=expires_in_days),
        is_revoked=revoked,
    )
    db.add(row)
    return row


def test_defaults_are_the_confirmed_retention_periods() -> None:
    settings = get_settings()
    assert settings.LOGIN_ATTEMPTS_RETENTION_DAYS == 30
    assert settings.SESSIONS_RETENTION_DAYS == 7


def test_login_attempts_older_than_ttl_are_removed_and_recent_ones_stay(
    db_session: Session,
) -> None:
    attempt(db_session, 31)
    attempt(db_session, 45)
    attempt(db_session, 29)
    attempt(db_session, 0.1)
    db_session.commit()

    result = run_retention(db_session, now=NOW)
    assert result["login_attempts"] == 2
    remaining = db_session.scalars(select(LoginAttempt.attempted_at)).all()
    assert len(remaining) == 2 and all(NOW - t < timedelta(days=30) for t in remaining)


def test_only_invalid_sessions_past_the_window_are_removed(db_session: Session) -> None:
    user = create_test_user(db_session, "ret@provedor.com.br", "viewer")
    active = session_row(
        db_session, user, expires_in_days=3, revoked=False, last_activity_days_ago=0
    )
    revoked_recent = session_row(
        db_session, user, expires_in_days=3, revoked=True, last_activity_days_ago=6
    )
    revoked_old = session_row(
        db_session, user, expires_in_days=3, revoked=True, last_activity_days_ago=8
    )
    expired_old = session_row(
        db_session, user, expires_in_days=-9, revoked=False, last_activity_days_ago=10
    )
    expired_recent = session_row(
        db_session, user, expires_in_days=-2, revoked=False, last_activity_days_ago=3
    )
    db_session.commit()
    ids = {
        name: row.id
        for name, row in {
            "active": active,
            "revoked_recent": revoked_recent,
            "revoked_old": revoked_old,
            "expired_old": expired_old,
            "expired_recent": expired_recent,
        }.items()
    }

    result = run_retention(db_session, now=NOW)
    assert result["user_sessions"] == 2
    left = set(db_session.scalars(select(UserSession.id)).all())
    assert left == {ids["active"], ids["revoked_recent"], ids["expired_recent"]}


def test_retention_is_idempotent(db_session: Session) -> None:
    attempt(db_session, 60)
    db_session.commit()
    assert run_retention(db_session, now=NOW)["login_attempts"] == 1
    again = run_retention(db_session, now=NOW)
    assert again["login_attempts"] == 0 and again["user_sessions"] == 0


def test_audit_events_are_never_touched(db_session: Session) -> None:
    ancient = AuditEvent(
        actor_name="t", action="x:y", entity_type="site", entity_id=uuid.uuid4(), changes={}
    )
    db_session.add(ancient)
    db_session.commit()
    db_session.execute(
        text("SELECT 1")
    )  # o created_at real é "agora"; a retenção não olha a tabela
    run_retention(db_session, now=NOW + timedelta(days=3650))  # 10 anos no futuro
    assert db_session.scalar(select(func.count(AuditEvent.id))) == 1


def test_large_backlogs_are_deleted_in_batches(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RETENTION_BATCH_SIZE", "100")
    get_settings.cache_clear()
    for _ in range(350):
        attempt(db_session, 40)
    db_session.commit()
    assert run_retention(db_session, now=NOW)["login_attempts"] == 350
    assert db_session.scalar(select(func.count(LoginAttempt.id))) == 0


def test_rate_limit_indexes_exist(db_session: Session) -> None:
    names = set(db_session.scalars(text("SELECT indexname FROM pg_indexes")).all())
    assert {
        "idx_login_attempts_email_attempted",
        "idx_login_attempts_ip_attempted",
        "idx_user_sessions_expires_at",
        "idx_user_sessions_last_activity",
    } <= names


def test_rate_limit_query_uses_the_composite_index(db_session: Session) -> None:
    db_session.execute(text("SET LOCAL enable_seqscan = off"))
    rows = db_session.execute(
        text(
            "EXPLAIN SELECT count(*) FROM login_attempts WHERE email = 'a@b.com' "
            "AND success = false AND attempted_at >= now() - interval '15 minutes'"
        )
    ).all()
    db_session.rollback()
    assert "idx_login_attempts_email_attempted" in "\n".join(r[0] for r in rows)


def test_worker_loop_runs_retention_periodically(db_session: Session, tmp_path: Path) -> None:
    attempt(db_session, 90)
    db_session.commit()
    spec = importlib.util.spec_from_file_location("run_worker_retention", WORKER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    state: dict[str, float] = {"last": 0.0}
    module.run_iteration(get_session_factory(), "w", tmp_path / "hb", state)
    db_session.expire_all()
    assert db_session.scalar(select(func.count(LoginAttempt.id))) == 0
    assert state.get("retention", 0) > 0  # próxima execução respeita RETENTION_INTERVAL_SECONDS
