import { describe, it, expect, vi } from "vitest";
import * as React from "react";
import { render, screen } from "@testing-library/react";
import { requiredPermissionForPath, visibleNavigationGroups } from "@/lib/navigation";
import { hasPermission, type Permission } from "@/lib/permissions/rbac";
import { PermissionGate } from "@/components/auth/permission-gate";

// R27 (EST-20): navegação, rotas e ações escondidas conforme as permissões do servidor.
let currentRole = "viewer";
vi.mock("@/features/auth/auth-context", () => ({
  useAuth: () => ({
    user: { id: "u", name: "U", role: currentRole },
    isLoading: false,
    isAuthenticated: true,
    hasPermission: (p: Permission) => hasPermission(currentRole, p),
  }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/settings/users",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const titles = (role: string) =>
  visibleNavigationGroups((p) => hasPermission(role, p)).flatMap((g) => g.items.map((i) => i.href));

describe("navegação por permissão", () => {
  it("viewer não vê módulos administrativos nem de escrita", () => {
    const hrefs = titles("viewer");
    expect(hrefs).toContain("/dashboard");
    expect(hrefs).toContain("/sites");
    for (const hidden of ["/settings", "/settings/users", "/imports", "/exports", "/audit", "/customers"]) {
      expect(hrefs).not.toContain(hidden);
    }
  });

  it("admin vê tudo; technician vê medições e auditoria mas não usuários", () => {
    const admin = titles("admin");
    expect(admin).toContain("/settings/users");
    expect(admin).toContain("/imports");
    const tech = titles("technician");
    expect(tech).toContain("/measurements");
    expect(tech).toContain("/audit");
    expect(tech).not.toContain("/settings/users");
  });

  it("grupos sem itens visíveis somem", () => {
    const groups = visibleNavigationGroups(() => false);
    expect(groups).toEqual([]);
  });

  it("resolve a permissão exigida pela rota (prefixo mais específico vence)", () => {
    expect(requiredPermissionForPath("/settings")).toBe("settings:read");
    expect(requiredPermissionForPath("/settings/users")).toBe("users:read");
    expect(requiredPermissionForPath("/customers/123")).toBe("customers:read");
    expect(requiredPermissionForPath("/profile")).toBeNull();
    expect(requiredPermissionForPath("/")).toBeNull();
  });
});

describe("PermissionGate em ações de escrita", () => {
  it("esconde o botão para quem não tem a permissão e mostra para quem tem", () => {
    currentRole = "viewer";
    const { unmount } = render(
      <PermissionGate permission="network:write">
        <button>Novo Site</button>
      </PermissionGate>
    );
    expect(screen.queryByText("Novo Site")).toBeNull();
    unmount();
    currentRole = "engineer";
    render(
      <PermissionGate permission="network:write">
        <button>Novo Site</button>
      </PermissionGate>
    );
    expect(screen.getByText("Novo Site")).toBeTruthy();
  });
});
