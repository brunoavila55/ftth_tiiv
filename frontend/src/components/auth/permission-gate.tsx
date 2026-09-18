"use client";

import * as React from "react";
import { useAuth } from "@/features/auth/auth-context";
import type { Permission, UserRole } from "@/lib/permissions/rbac";

export interface PermissionGateProps {
  permission?: Permission;
  role?: UserRole | UserRole[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export function PermissionGate({
  permission,
  role,
  fallback = null,
  children,
}: PermissionGateProps) {
  const { user, hasPermission } = useAuth();

  if (!user) {
    return <>{fallback}</>;
  }

  // Validação por permissão granular
  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>;
  }

  // Validação por papel específico
  if (role) {
    const roles = Array.isArray(role) ? role : [role];
    if (!roles.includes(user.role as UserRole)) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}
