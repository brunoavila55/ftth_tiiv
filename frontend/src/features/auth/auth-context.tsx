"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getMe, login as apiLogin, logout as apiLogout } from "@/features/auth/api";
import type { LoginRequest, MeResponse } from "@/lib/api/types";
import { hasPermission as checkPermission, type Permission, type UserRole } from "@/lib/permissions/rbac";

export interface AuthContextType {
  user: MeResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  role: UserRole | null;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (permission: Permission) => boolean;
  refetchUser: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

export const AUTH_QUERY_KEY = ["auth", "me"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const router = useRouter();

  const {
    data: user = null,
    isLoading,
    refetch,
  } = useQuery<MeResponse | null>({
    queryKey: AUTH_QUERY_KEY,
    queryFn: async () => {
      try {
        const res = await getMe();
        return res ?? null;
      } catch {
        // Se retornar 401 ou falha de sessão, usuário não autenticado
        return null;
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutos
    retry: false,
    refetchOnWindowFocus: true,
  });

  const loginMutation = useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      const response = await apiLogin(credentials);
      return response.user;
    },
    onSuccess: (userData) => {
      queryClient.setQueryData(AUTH_QUERY_KEY, userData);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      try {
        await apiLogout();
      } catch {
        // Continua com logout local mesmo se a chamada de rede falhar
      }
    },
    onSuccess: () => {
      // Limpa todo o cache remoto para garantir que dados de clientes não persistam
      queryClient.clear();
      router.push("/login");
    },
  });

  const login = async (credentials: LoginRequest) => {
    await loginMutation.mutateAsync(credentials);
  };

  const logout = async () => {
    await logoutMutation.mutateAsync();
  };

  const hasPermission = React.useCallback(
    (permission: Permission): boolean => {
      if (!user) return false;
      // Valida tanto a lista explícita de permissões retornada pelo backend quanto a matriz de papéis
      if (user.permissions && user.permissions.includes(permission)) {
        return true;
      }
      return checkPermission(user.role as UserRole, permission);
    },
    [user]
  );

  const refetchUser = async () => {
    await refetch();
  };

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: Boolean(user),
    role: (user?.role as UserRole) || null,
    login,
    logout,
    hasPermission,
    refetchUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth deve ser utilizado dentro de um AuthProvider");
  }
  return context;
}
