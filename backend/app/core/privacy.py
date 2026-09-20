"""Regras de privacidade (LGPD) para dados pessoais de clientes (SEC-03 / SEC-04).

Dados pessoais de clientes pertencem às permissões `customers:read|write`; anexos e eventos de
auditoria ligados a clientes/vínculos de atendimento seguem a mesma regra.
"""

from typing import Any

from app.core.errors import ForbiddenError
from app.core.permissions import has_permission
from app.modules.identity.models import User
from app.schemas.common import UserRole

# Tipos de entidade cujos anexos/eventos contêm ou identificam dados pessoais de clientes
CUSTOMER_PII_ENTITY_TYPES = frozenset({"customer", "service_link"})

# Campos pessoais mascarados na trilha de auditoria para quem não tem customers:read
AUDIT_PII_FIELDS = frozenset({"phone", "email", "address"})

# `name`/`notes` só identificam pessoa em eventos de cliente/vínculo (`CUSTOMER_PII_ENTITY_TYPES`);
# mascará-los para qualquer entidade escondería dado não sensível (nome de site, notas de medição).
AUDIT_CUSTOMER_ONLY_PII_FIELDS = frozenset({"name", "notes"})

REDACTED = "[REDACTED]"


def user_can(user: User, permission: str) -> bool:
    return has_permission(UserRole(user.role), permission)


def is_customer_pii_entity(entity_type: str) -> bool:
    return entity_type.lower().strip() in CUSTOMER_PII_ENTITY_TYPES


def require_customer_access(user: User, entity_type: str, *, write: bool = False) -> None:
    """Exige customers:read|write para operar sobre anexos de cliente/vínculo."""
    if not is_customer_pii_entity(entity_type):
        return
    permission = "customers:write" if write else "customers:read"
    if not user_can(user, permission):
        raise ForbiddenError(
            f"Acesso negado. Anexos de '{entity_type}' exigem a permissão '{permission}'.",
            code="insufficient_permissions",
        )


def mask_pii_changes(changes: Any, *, entity_type: str | None = None) -> Any:
    """Mascara recursivamente phone/email/address (todas as entidades) e, quando `entity_type` é
    de cliente/vínculo (`is_customer_pii_entity`), também name/notes, preservando as chaves (o
    campo mudou)."""
    fields = AUDIT_PII_FIELDS
    if entity_type is not None and is_customer_pii_entity(entity_type):
        fields = fields | AUDIT_CUSTOMER_ONLY_PII_FIELDS
    if isinstance(changes, dict):
        return {
            key: REDACTED
            if isinstance(key, str) and key.lower() in fields
            else mask_pii_changes(value, entity_type=entity_type)
            for key, value in changes.items()
        }
    if isinstance(changes, list):
        return [mask_pii_changes(item, entity_type=entity_type) for item in changes]
    return changes
