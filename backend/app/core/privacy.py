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


def mask_pii_changes(changes: Any) -> Any:
    """Mascara recursivamente phone/email/address, preservando as chaves (o campo mudou)."""
    if isinstance(changes, dict):
        return {
            key: REDACTED
            if isinstance(key, str) and key.lower() in AUDIT_PII_FIELDS
            else mask_pii_changes(value)
            for key, value in changes.items()
        }
    if isinstance(changes, list):
        return [mask_pii_changes(item) for item in changes]
    return changes
