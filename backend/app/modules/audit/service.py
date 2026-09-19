import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import request_id_ctx
from app.modules.audit.models import AuditEvent

SENSITIVE_KEYS = {
    "password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "csrf_token",
    "api_key",
    "authorization",
    "credentials",
}


def sanitize_audit_payload(obj: Any) -> Any:
    """Sanitiza recursivamente chaves sensíveis e converte tipos especiais para serialização JSON."""
    if isinstance(obj, dict):
        sanitized = {}
        for key, value in obj.items():
            k_lower = str(key).lower()
            if any(sensitive in k_lower for sensitive in SENSITIVE_KEYS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_audit_payload(value)
        return sanitized
    elif isinstance(obj, list | tuple | set):
        return [sanitize_audit_payload(item) for item in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def record_audit_event(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changes: dict[str, Any] | None = None,
    reason: str | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    """Registra um evento de auditoria append-only na mesma transação da operação.

    Se a transação for revertida (rollback), o evento de auditoria também é revertido atomicamente.
    """
    safe_changes = sanitize_audit_payload(changes or {})
    if request_id is None:
        request_id = request_id_ctx.get()  # correlação automática com o X-Request-ID da requisição

    event = AuditEvent(
        actor_id=actor_id,
        actor_name=actor_name,
        action=action,
        entity_type=entity_type.lower(),
        entity_id=entity_id,
        changes=safe_changes,
        reason=reason,
        request_id=request_id,
    )
    db.add(event)
    return event


def record_contextual_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changes: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditEvent:
    """Registra evento explícito usando ator/request_id do contexto de auditoria da requisição."""
    ctx = db.info.get("audit_ctx")
    return record_audit_event(
        db,
        actor_id=getattr(ctx, "actor_id", None),
        actor_name=getattr(ctx, "actor_name", "Sistema"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        reason=reason,
        request_id=getattr(ctx, "request_id", None),
    )


def list_audit_events_paginated(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    """Consulta paginada de eventos da trilha de auditoria append-only."""
    from sqlalchemy import func

    query = select(AuditEvent)

    if entity_type:
        query = query.where(AuditEvent.entity_type == entity_type.lower())
    if entity_id:
        query = query.where(AuditEvent.entity_id == entity_id)
    if actor_id:
        query = query.where(AuditEvent.actor_id == actor_id)
    if action:
        query = query.where(func.lower(AuditEvent.action) == action.lower())
    if date_from:
        query = query.where(AuditEvent.created_at >= date_from)
    if date_to:
        query = query.where(AuditEvent.created_at <= date_to)

    # Contagem total
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Itens ordenados cronologicamente decrescente
    query = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
    events = list(db.scalars(query).all())

    return events, total
