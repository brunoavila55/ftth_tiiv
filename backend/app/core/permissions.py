from app.schemas.common import UserRole

# Matriz de permissões estritas do FTTH Manager
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.VIEWER: {
        "network:read",
        "optical:read",
        "reports:read",
        "map:read",
    },
    UserRole.TECHNICIAN: {
        "network:read",
        "optical:read",
        "reports:read",
        "map:read",
        "measurements:read",
        "measurements:write",
        "attachments:read",
        "attachments:write",
        "audit:read",
    },
    UserRole.ENGINEER: {
        "network:read",
        "network:write",
        "optical:read",
        "optical:write",
        "reports:read",
        "map:read",
        "measurements:read",
        "measurements:write",
        "attachments:read",
        "attachments:write",
        "customers:read",
        "customers:write",
        "cables:read",
        "cables:write",
        "splitters:read",
        "splitters:write",
        "connectivity:read",
        "connectivity:write",
        "topology:read",
        "topology:write",
        "imports:read",
        "imports:write",
        "exports:read",
        "exports:write",
        "audit:read",
    },
    UserRole.ADMIN: {
        "network:read",
        "network:write",
        "optical:read",
        "optical:write",
        "reports:read",
        "map:read",
        "measurements:read",
        "measurements:write",
        "attachments:read",
        "attachments:write",
        "customers:read",
        "customers:write",
        "cables:read",
        "cables:write",
        "splitters:read",
        "splitters:write",
        "connectivity:read",
        "connectivity:write",
        "topology:read",
        "topology:write",
        "imports:read",
        "imports:write",
        "exports:read",
        "exports:write",
        "users:read",
        "users:write",
        "settings:read",
        "settings:write",
        "audit:read",
    },
}


def get_role_permissions(role: UserRole) -> list[str]:
    """Retorna lista ordenada de permissões para um determinado papel."""
    return sorted(ROLE_PERMISSIONS.get(role, set()))


def has_permission(role: UserRole, required_permission: str) -> bool:
    """Verifica se o papel possui a permissão requerida."""
    return required_permission in ROLE_PERMISSIONS.get(role, set())
