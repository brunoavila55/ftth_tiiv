import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UsersTable } from "@/features/users/components/users-table";
import { SettingsView } from "@/features/settings/components/settings-view";
import * as usersApi from "@/features/users/api";
import * as settingsApi from "@/features/settings/api";
import type { UserRead, PaginatedResult } from "@/features/users/types";
import { ApiError } from "@/lib/api/types";

vi.mock("@/features/auth/auth-context", () => import("./support/auth-context-mock"));

// Mock do next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

const mockUsersData: PaginatedResult<UserRead> = {
  items: [
    {
      id: "user-1",
      name: "Administrador Principal",
      email: "admin@provedor.com.br",
      role: "admin",
      is_active: true,
      version: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    {
      id: "user-2",
      name: "Engenheiro de Redes",
      email: "engenheiro@provedor.com.br",
      role: "engineer",
      is_active: true,
      version: 2,
      created_at: "2026-01-02T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    },
    {
      id: "user-3",
      name: "Técnico de Campo",
      email: "tecnico@provedor.com.br",
      role: "technician",
      is_active: false,
      version: 1,
      created_at: "2026-01-03T00:00:00Z",
      updated_at: "2026-01-03T00:00:00Z",
    },
  ],
  total: 3,
  page: 1,
  page_size: 15,
};

describe("Settings & User Management (F17)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(usersApi, "listUsers").mockResolvedValue(mockUsersData);
    vi.spyOn(usersApi, "createUser").mockResolvedValue({
      id: "user-new",
      name: "Novo Operador",
      email: "novo@provedor.com.br",
      role: "viewer",
      is_active: true,
      version: 1,
      created_at: "2026-09-18T10:00:00Z",
      updated_at: "2026-09-18T10:00:00Z",
    });
    vi.spyOn(usersApi, "updateUser").mockResolvedValue({
      ...mockUsersData.items[0],
      name: "Admin Atualizado",
      version: 2,
    });
    vi.spyOn(usersApi, "deleteUser").mockResolvedValue();
    vi.spyOn(settingsApi, "getAppSettings").mockResolvedValue({
      app_name: "FTTH Manager",
      organization_name: "Operação FTTH Manager",
      timezone: "America/Sao_Paulo",
      default_map_center: [-46.633308, -23.55052],
      default_map_zoom: 14,
      max_upload_size_bytes: 10_485_760,
      trace_max_depth: 300,
      excess_loss_tolerance_db: 2,
      version: 1,
    });
    vi.spyOn(settingsApi, "updateAppSettings").mockResolvedValue({
      app_name: "FTTH Manager",
      organization_name: "Provedor Atualizado",
      timezone: "America/Fortaleza",
      default_map_center: [-38.5267, -3.7319],
      default_map_zoom: 16,
      max_upload_size_bytes: 10_485_760,
      trace_max_depth: 300,
      excess_loss_tolerance_db: 1.5,
      version: 2,
    });
  });

  it("renders users table with operators, role badges and active statuses", async () => {
    renderWithQuery(<UsersTable />);

    await waitFor(() => {
      expect(screen.getByText("Administrador Principal")).toBeDefined();
      expect(screen.getByText("Engenheiro de Redes")).toBeDefined();
      expect(screen.getByText("Técnico de Campo")).toBeDefined();
    });

    expect(screen.getByText("admin@provedor.com.br")).toBeDefined();
    expect(screen.getByText("Administrador")).toBeDefined();
    expect(screen.getByText("Engenheiro")).toBeDefined();
    expect(screen.getByText("Técnico")).toBeDefined();

    expect(screen.getByText("Mostrando 3 de 3 operadores")).toBeDefined();
  });

  it("filters users by textual search query", async () => {
    renderWithQuery(<UsersTable />);

    await waitFor(() => {
      expect(screen.getByText("Administrador Principal")).toBeDefined();
    });

    const searchInput = screen.getByPlaceholderText(/Buscar por nome ou e-mail/i);
    fireEvent.change(searchInput, { target: { value: "Engenheiro" } });

    const searchBtn = screen.getByRole("button", { name: /^Buscar$/i });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(usersApi.listUsers).toHaveBeenCalledWith(
        expect.objectContaining({
          q: "Engenheiro",
          page: 1,
        }),
        expect.anything()
      );
    });
  });

  it("opens create user dialog and submits new operator", async () => {
    renderWithQuery(<UsersTable />);

    const newBtn = screen.getByRole("button", { name: /Novo Usuário/i });
    fireEvent.click(newBtn);

    await waitFor(() => {
      expect(screen.getByText("Novo Operador / Usuário")).toBeDefined();
    });

    fireEvent.change(screen.getByLabelText(/Nome Completo/i), {
      target: { value: "Novo Operador" },
    });
    fireEvent.change(screen.getByLabelText(/E-mail de Acesso/i), {
      target: { value: "novo@provedor.com.br" },
    });
    fireEvent.change(screen.getByLabelText(/Senha Inicial/i), {
      target: { value: "SenhaSegura123!" },
    });

    const submitBtn = screen.getByRole("button", { name: /Cadastrar Usuário/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(usersApi.createUser).toHaveBeenCalledWith({
        name: "Novo Operador",
        email: "novo@provedor.com.br",
        role: "viewer",
        password: "SenhaSegura123!",
      });
    });
  });

  it("opens edit dialog and updates operator with optimistic concurrency", async () => {
    renderWithQuery(<UsersTable />);

    await waitFor(() => {
      expect(screen.getByText("Administrador Principal")).toBeDefined();
    });

    const editButtons = screen.getAllByRole("button", { name: /Editar/i });
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("Editar Operador")).toBeDefined();
    });

    const nameInput = screen.getByLabelText(/Nome Completo/i);
    fireEvent.change(nameInput, { target: { value: "Admin Atualizado" } });

    const saveBtn = screen.getByRole("button", { name: /Salvar Alterações/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(usersApi.updateUser).toHaveBeenCalledWith(
        "user-1",
        expect.objectContaining({
          name: "Admin Atualizado",
          email: "admin@provedor.com.br",
        }),
        1 // versão original do user-1
      );
    });
  });

  it("handles last active admin protection error on deactivation attempt", async () => {
    vi.spyOn(usersApi, "deleteUser").mockRejectedValue(
      new ApiError(409, {
        detail: "Não é permitido desativar o último administrador ativo do sistema.",
      })
    );

    renderWithQuery(<UsersTable />);

    await waitFor(() => {
      expect(screen.getByText("Administrador Principal")).toBeDefined();
    });

    // Clica em desativar o primeiro usuário (admin)
    const deactivateBtns = screen.getAllByRole("button", { name: /Desativar/i });
    fireEvent.click(deactivateBtns[0]);

    // Modal de confirmação abre
    await waitFor(() => {
      expect(screen.getByText(/Desativar operador "Administrador Principal"\?/i)).toBeDefined();
    });

    const confirmBtn = screen.getByRole("button", { name: /Sim, Desativar/i });
    fireEvent.click(confirmBtn);

    // Deve renderizar o alerta persistente de proteção do último admin
    await waitFor(() => {
      expect(
        screen.getByText(/Não é permitido desativar o último administrador ativo/i)
      ).toBeDefined();
    });
  });

  it("renders and updates organization parameters, color standards and links", async () => {
    renderWithQuery(<SettingsView />);

    const organizationInput = await screen.findByLabelText("Nome da instalação / provedor");
    expect((organizationInput as HTMLInputElement).value).toBe("Operação FTTH Manager");
    expect((screen.getByLabelText("Fuso horário IANA") as HTMLInputElement).value).toBe(
      "America/Sao_Paulo"
    );
    expect(screen.getByText("Catálogos de Código de Cores de Fibras e Tubos")).toBeDefined();

    fireEvent.change(organizationInput, { target: { value: "Provedor Atualizado" } });
    fireEvent.change(screen.getByLabelText("Fuso horário IANA"), {
      target: { value: "America/Fortaleza" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar parâmetros" }));
    await waitFor(() =>
      expect(settingsApi.updateAppSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          organization_name: "Provedor Atualizado",
          timezone: "America/Fortaleza",
        }),
        1
      )
    );

    // Padrão NBR ativo por padrão
    expect(screen.getByText(/#1 Verde/i)).toBeDefined();
    expect(screen.getByText(/#12 Aqua/i)).toBeDefined();

    // Alterna para TIA
    const tiaBtn = screen.getByRole("button", { name: /ANSI\/TIA-598-C/i });
    fireEvent.click(tiaBtn);

    expect(screen.getByText(/#1 Azul/i)).toBeDefined();
    expect(screen.getByText(/#2 Laranja/i)).toBeDefined();

    // Links para áreas administrativas
    const usersLink = screen.getByRole("link", { name: /Gerenciar Usuários/i });
    expect(usersLink.getAttribute("href")).toBe("/settings/users");

    const auditLink = screen.getByRole("link", { name: /Consultar Auditoria/i });
    expect(auditLink.getAttribute("href")).toBe("/audit");
  });
});
