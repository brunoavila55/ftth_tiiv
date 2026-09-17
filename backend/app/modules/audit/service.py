import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent


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
    """Registra um evento de auditoria append-only na mesma transação da operação."""
    event = AuditEvent(
        actor_id=actor_id,
        actor_name=actor_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or {},
        reason=reason,
        request_id=request_id,
    )
    db.add(event)
    return event
