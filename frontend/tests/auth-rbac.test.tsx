import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { sanitizeReturnUrl } from "@/features/auth/utils";
import { AuthProvider, useAuth } from "@/features/auth/auth-context";
import { PermissionGate } from "@/components/auth/permission-gate";
import { hasPermission, canWriteNetwork, canManageUsers } from "@/lib/permissions/rbac";
import * as authApi from "@/features/auth/api";
import type { MeResponse } from "@/lib/api/types";

// Mock do next/navigation para jsdom
const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock das funções de API
vi.mock("@/features/auth/api", () => ({
  getMe: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  changePassword: vi.fn(),
}));

const mockViewerUser: MeResponse = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "viewer@ftth.local",
  name: "Operador Leitor",
  role: "viewer",
  permissions: ["network:read"],
};

const mockEngineerUser: MeResponse = {
  id: "22222222-2222-2222-2222-222222222222",
  email: "engineer@ftth.local",
  name: "Engenheiro de Redes",
  role: "engineer",
  permissions: ["network:read", "network:write", "audit:read"],
};

const mockAdminUser: MeResponse = {
  id: "33333333-3333-3333-3333-333333333333",
  email: "admin@ftth.local",
  name: "Administrador Geral",
  role: "admin",
  permissions: [
    "network:read",
    "network:write",
    "users:read",
    "users:write",
    "settings:read",
    "settings:write",
    "audit:read",
    "telemetry:write",
  ],
};

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    );
  };
}

describe("Segurança contra Open Redirect (sanitizeReturnUrl)", () => {
  it("aceita caminhos locais relativos seguros", () => {
    expect(sanitizeReturnUrl("/")).toBe("/");
    expect(sanitizeReturnUrl("/dashboard")).toBe("/dashboard");
    expect(sanitizeReturnUrl("/sites?kind=pole")).toBe("/sites?kind=pole");
    expect(sanitizeReturnUrl("/cables/123#fibers")).toBe("/cables/123#fibers");
  });

  it("rejeita e neutraliza URLs externas absolutas", () => {
    expect(sanitizeReturnUrl("https://evil.com")).toBe("/");
    expect(sanitizeReturnUrl("http://attacker.org/phish")).toBe("/");
    expect(sanitizeReturnUrl("https://evil.com/login?redirect=steal")).toBe("/");
  });

  it("rejeita URLs com barra dupla (protocol-relative //)", () => {
    expect(sanitizeReturnUrl("//evil.com")).toBe("/");
    expect(sanitizeReturnUrl("//evil.com/phish")).toBe("/");
  });

  it("rejeita esquemas perigosos (javascript:, data:)", () => {
    expect(sanitizeReturnUrl("javascript:alert(1)")).toBe("/");
    expect(sanitizeReturnUrl("data:text/html,<script>alert(1)</script>")).toBe("/");
  });

  it("aceita fallback customizado quando fornecido", () => {
    expect(sanitizeReturnUrl("https://evil.com", "/dashboard")).toBe("/dashboard");
    expect(sanitizeReturnUrl(null, "/map")).toBe("/map");
  });
});

describe("Matriz Granular de Acesso RBAC (frontend.md)", () => {
  it("valida permissões para o papel viewer (somente leitura)", () => {
    expect(hasPermission("viewer", "network:read")).toBe(true);
    expect(hasPermission("viewer", "network:write")).toBe(false);
    expect(hasPermission("viewer", "telemetry:write")).toBe(false);
    expect(hasPermission("viewer", "users:write")).toBe(false);
    expect(canWriteNetwork("viewer")).toBe(false);
  });

  it("valida permissões para o papel technician (medições e fotos, sem topologia)", () => {
    expect(hasPermission("technician", "network:read")).toBe(true);
    expect(hasPermission("technician", "measurements:write")).toBe(true);
    expect(hasPermission("technician", "telemetry:write")).toBe(false); // só existia no front (EST-20)
    expect(hasPermission("technician", "network:write")).toBe(false);
    expect(canWriteNetwork("technician")).toBe(false);
    expect(canManageUsers("technician")).toBe(false);
  });

  it("valida permissões para o papel engineer (edição de topologia e auditoria)", () => {
    expect(hasPermission("engineer", "network:read")).toBe(true);
    expect(hasPermission("engineer", "network:write")).toBe(true);
    expect(hasPermission("engineer", "audit:read")).toBe(true);
    expect(hasPermission("engineer", "users:write")).toBe(false);
    expect(canWriteNetwork("engineer")).toBe(true);
    expect(canManageUsers("engineer")).toBe(false);
  });

  it("valida permissões para o papel admin (gestão completa)", () => {
    expect(hasPermission("admin", "network:read")).toBe(true);
    expect(hasPermission("admin", "network:write")).toBe(true);
    expect(hasPermission("admin", "users:write")).toBe(true);
    expect(hasPermission("admin", "settings:write")).toBe(true);
    expect(canWriteNetwork("admin")).toBe(true);
    expect(canManageUsers("admin")).toBe(true);
  });
});

describe("PermissionGate (Renderização Condicional por Papel/Permissão)", () => {
  it("renderiza children apenas quando o usuário possui a permissão requerida", async () => {
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockEngineerUser);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <PermissionGate permission="network:write">
        <button>Criar Fusão Óptica</button>
      </PermissionGate>,
      { wrapper: createWrapper(queryClient) }
    );

    await waitFor(() => {
      expect(screen.getByText("Criar Fusão Óptica")).toBeDefined();
    });
  });

  it("renderiza fallback quando o usuário não possui permissão", async () => {
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockViewerUser);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <PermissionGate
        permission="network:write"
        fallback={<span>Sem permissão de escrita</span>}
      >
        <button>Criar Fusão Óptica</button>
      </PermissionGate>,
      { wrapper: createWrapper(queryClient) }
    );

    await waitFor(() => {
      expect(screen.queryByText("Criar Fusão Óptica")).toBeNull();
      expect(screen.getByText("Sem permissão de escrita")).toBeDefined();
    });
  });
});

describe("Sessão, Login e Logout (AuthProvider & Limpeza de Cache)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("carrega sessão ativa a partir de /auth/me", async () => {
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAdminUser);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    function TestComponent() {
      const { user, isAuthenticated, role } = useAuth();
      if (!isAuthenticated) return <div>Não Autenticado</div>;
      return (
        <div>
          <span>Usuário: {user?.name}</span>
          <span>Papel: {role}</span>
        </div>
      );
    }

    render(<TestComponent />, { wrapper: createWrapper(queryClient) });

    await waitFor(() => {
      expect(screen.getByText("Usuário: Administrador Geral")).toBeDefined();
      expect(screen.getByText("Papel: admin")).toBeDefined();
    });
  });

  it("limpa completamente o cache do TanStack Query no logout garantindo que cache de dados não vaze", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(mockEngineerUser);
    vi.mocked(authApi.logout).mockImplementation(async () => {
      vi.mocked(authApi.getMe).mockRejectedValue(new Error("Sessão revogada 401"));
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    // Injeta dados sensíveis de simulação no cache
    queryClient.setQueryData(["cables", "sensitive-list"], [{ id: "c1", name: "Cabo Troncal 72F" }]);
    expect(queryClient.getQueryData(["cables", "sensitive-list"])).toBeDefined();

    function TestLogoutComponent() {
      const { logout } = useAuth();
      return <button onClick={() => logout()}>Encerrar Sessão</button>;
    }

    render(<TestLogoutComponent />, { wrapper: createWrapper(queryClient) });

    const btn = screen.getByText("Encerrar Sessão");
    fireEvent.click(btn);

    await waitFor(() => {
      expect(authApi.logout).toHaveBeenCalledTimes(1);
      // Confirma que todo o cache em memória foi purgado
      expect(queryClient.getQueryData(["cables", "sensitive-list"])).toBeUndefined();
    });
  });
});
