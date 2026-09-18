"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/features/auth/auth-context";
import { LoadingState, ErrorState } from "@/components/ui/state-displays";
import type { Permission, UserRole } from "@/lib/permissions/rbac";

export interface AuthGuardProps {
  children: React.ReactNode;
  requiredPermission?: Permission;
  requiredRole?: UserRole | UserRole[];
}

export function AuthGuard({ children, requiredPermission, requiredRole }: AuthGuardProps) {
  const { user, isLoading, isAuthenticated, hasPermission } = useAuth();
  const router = useRouter();
  const pathname = usePathname() || "/";

  React.useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // Redireciona para o login informando a rota original de retorno
      const returnUrl = encodeURIComponent(pathname);
      router.replace(`/login?returnUrl=${returnUrl}`);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex h-[70vh] items-center justify-center">
        <LoadingState
          message="Verificando sessão de acesso..."
          description="Validando credenciais corporativas no servidor FTTH"
          size="lg"
        />
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  // Validação de permissão
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4">
        <ErrorState
          title="Acesso Não Autorizado (HTTP 403)"
          error="Seu perfil de usuário não possui as permissões necessárias para acessar este recurso ou executar esta ação técnica."
        />
      </div>
    );
  }

  // Validação de papel
  if (requiredRole) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!roles.includes(user.role as UserRole)) {
      return (
        <div className="max-w-xl mx-auto py-12 px-4">
          <ErrorState
            title="Acesso Restrito ao Papel (HTTP 403)"
            error="Este módulo requer privilégios específicos de engenharia ou administração."
          />
        </div>
      );
    }
  }

  return <>{children}</>;
}
