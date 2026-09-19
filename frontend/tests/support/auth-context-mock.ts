// Substitui `@/features/auth/auth-context` nos testes de componentes: usuário admin com todas as
// permissões (o RBAC em si é coberto por auth-rbac / permissions-parity / route-permission-guard).
export function useAuth() {
  return {
    user: { id: "u-admin", name: "Administrador", email: "admin@example.com", role: "admin" },
    isLoading: false,
    isAuthenticated: true,
    role: "admin",
    hasPermission: () => true,
  };
}
