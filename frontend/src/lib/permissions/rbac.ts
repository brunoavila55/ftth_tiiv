import { PERMISSIONS, ROLE_PERMISSIONS as GENERATED_ROLE_PERMISSIONS } from "./rbac.generated";

// A matriz é GERADA do backend (backend/scripts/export_permissions.py → rbac.generated.ts): o
// servidor é a autoridade e a UI apenas esconde/desabilita o que ele recusaria. Não há mais
// matriz mantida à mão aqui (evita divergências como o antigo `telemetry:write`).
export { PERMISSIONS };

export type UserRole = keyof typeof GENERATED_ROLE_PERMISSIONS;

export type Permission = (typeof PERMISSIONS)[number];

export const ROLE_PERMISSIONS: Record<UserRole, readonly Permission[]> = GENERATED_ROLE_PERMISSIONS;

export function hasPermission(
  role: UserRole | string | null | undefined,
  permission: Permission | string
): boolean {
  if (!role) return false;
  const permissions = ROLE_PERMISSIONS[role as UserRole];
  if (!permissions) return false;
  return permissions.includes(permission as Permission);
}

export function canWriteNetwork(role: UserRole | string | null | undefined): boolean {
  return hasPermission(role, "network:write");
}

export function canManageUsers(role: UserRole | string | null | undefined): boolean {
  return hasPermission(role, "users:write");
}
