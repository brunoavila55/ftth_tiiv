export type UserRole = "admin" | "engineer" | "technician" | "viewer";

export type Permission =
  | "network:read"
  | "network:write"
  | "optical:read"
  | "optical:write"
  | "reports:read"
  | "map:read"
  | "measurements:read"
  | "measurements:write"
  | "telemetry:write"
  | "attachments:read"
  | "attachments:write"
  | "customers:read"
  | "customers:write"
  | "cables:read"
  | "cables:write"
  | "splitters:read"
  | "splitters:write"
  | "connectivity:read"
  | "connectivity:write"
  | "topology:read"
  | "topology:write"
  | "imports:read"
  | "imports:write"
  | "exports:read"
  | "exports:write"
  | "audit:read"
  | "users:read"
  | "users:write"
  | "settings:read"
  | "settings:write";

export const ROLE_PERMISSIONS: Record<UserRole, readonly Permission[]> = {
  viewer: [
    "network:read",
    "optical:read",
    "reports:read",
    "map:read",
  ],
  technician: [
    "network:read",
    "optical:read",
    "reports:read",
    "map:read",
    "measurements:read",
    "measurements:write",
    "telemetry:write",
    "attachments:read",
    "attachments:write",
    "audit:read",
  ],
  engineer: [
    "network:read",
    "network:write",
    "optical:read",
    "optical:write",
    "reports:read",
    "map:read",
    "measurements:read",
    "measurements:write",
    "telemetry:write",
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
  ],
  admin: [
    "network:read",
    "network:write",
    "optical:read",
    "optical:write",
    "reports:read",
    "map:read",
    "measurements:read",
    "measurements:write",
    "telemetry:write",
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
    "users:read",
    "users:write",
    "settings:read",
    "settings:write",
  ],
};

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
