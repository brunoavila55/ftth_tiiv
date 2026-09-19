"""Retenção de dados operacionais (PERF-11).

Rotina idempotente executada periodicamente pelo worker. Remove, em lotes:
- `login_attempts` mais antigos que LOGIN_ATTEMPTS_RETENTION_DAYS (30);
- `user_sessions` inválidas (expiradas ou revogadas) há mais de SESSIONS_RETENTION_DAYS (7);
- arquivos de exportação vencidos e prévias de importação expiradas (ver `jobs.service`).

**Nunca** toca em `audit_events`: a trilha é append-only (trigger no banco) e sem retenção.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.identity.models import LoginAttempt, UserSession
from app.modules.jobs.service import clean_expired_previews_and_exports


def _delete_in_batches(db: Session, model: Any, condition: Any, batch_size: int) -> int:
    """Apaga `condition` em lotes (commits curtos: sem transação gigante nem lock longo)."""
    total = 0
    while True:
        ids = select(model.id).where(condition).limit(batch_size)
        result = cast(CursorResult[Any], db.execute(delete(model).where(model.id.in_(ids))))
        removed = result.rowcount or 0
        db.commit()
        total += removed
        if removed < batch_size:
            return total


def run_retention(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Aplica a política de retenção. `now` permite simular o relógio nos testes."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    batch = settings.RETENTION_BATCH_SIZE

    attempts_cutoff = now - timedelta(days=settings.LOGIN_ATTEMPTS_RETENTION_DAYS)
    sessions_cutoff = now - timedelta(days=settings.SESSIONS_RETENTION_DAYS)

    removed_attempts = _delete_in_batches(
        db, LoginAttempt, LoginAttempt.attempted_at < attempts_cutoff, batch
    )
    removed_sessions = _delete_in_batches(
        db,
        UserSession,
        or_(
            UserSession.expires_at < sessions_cutoff,
            and_(UserSession.is_revoked.is_(True), UserSession.last_activity_at < sessions_cutoff),
        ),
        batch,
    )
    files = clean_expired_previews_and_exports(db)  # exportações vencidas (R11) e prévias expiradas

    return {
        "login_attempts": removed_attempts,
        "user_sessions": removed_sessions,
        "expired_exports": files.get("expired_exports", 0),
        "cleaned_previews": files.get("cleaned_previews", 0),
    }
