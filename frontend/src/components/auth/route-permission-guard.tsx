"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { AuthGuard } from "@/components/auth/auth-guard";
import { requiredPermissionForPath } from "@/lib/navigation";

/**
 * Exige, por rota, a mesma permissão que o item de menu declara (o servidor continua sendo a
 * autoridade; isto só evita mostrar uma tela que resultaria em 403).
 */
export function RoutePermissionGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const requiredPermission = requiredPermissionForPath(pathname) ?? undefined;
  return <AuthGuard requiredPermission={requiredPermission}>{children}</AuthGuard>;
}
