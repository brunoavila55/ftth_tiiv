import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SiteFormDialog } from "@/features/inventory/components/site-form-dialog";
import { StructureFormDialog } from "@/features/inventory/components/structure-form-dialog";
import { DeviceFormDialog } from "@/features/inventory/components/device-form-dialog";
import { DeactivationDialog } from "@/features/inventory/components/deactivation-dialog";
import { ApiError } from "@/lib/api/types";
import * as inventoryApi from "@/features/inventory/api";

// Mock das funções da API de inventário
vi.mock("@/features/inventory/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/inventory/api")>();
  return {
    ...actual,
    createSite: vi.fn(),
    updateSite: vi.fn(),
    deleteSite: vi.fn(),
    createStructure: vi.fn(),
    updateStructure: vi.fn(),
    deleteStructure: vi.fn(),
    createDevice: vi.fn(),
    updateDevice: vi.fn(),
    deleteDevice: vi.fn(),
    listSites: vi.fn().mockResolvedValue({
      items: [{ id: "site-1", code: "POP-CENTRO", name: "Central", kind: "pop" }],
      total: 1,
      page: 1,
      page_size: 20,
    }),
    listStructures: vi.fn().mockResolvedValue({
      items: [{ id: "struct-1", code: "POSTE-01", kind: "pole" }],
      total: 1,
      page: 1,
      page_size: 20,
    }),
  };
});

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Cadastros de Rede Física e Inventário (F08)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("SiteFormDialog", () => {
    it("renderiza campos cadastrais e geográficos para novo site", () => {
      renderWithQueryClient(
        <SiteFormDialog
          open={true}
          onOpenChange={vi.fn()}
          onSuccess={vi.fn()}
        />
      );

      expect(screen.getByLabelText(/Código Único/i)).toBeTruthy();
      expect(screen.getByLabelText(/Nome do Local Técnico/i)).toBeTruthy();
      expect(screen.getByLabelText(/Tipo de Site/i)).toBeTruthy();
      expect(screen.getByLabelText(/Situação Administrativa/i)).toBeTruthy();
      expect(screen.getByText(/Localização Geográfica \(WGS-84\)/i)).toBeTruthy();
    });

    it("valida campos obrigatórios impedindo código muito curto", async () => {
      renderWithQueryClient(
        <SiteFormDialog
          open={true}
          onOpenChange={vi.fn()}
          onSuccess={vi.fn()}
        />
      );

      const codeInput = screen.getByLabelText(/Código Único/i);
      fireEvent.change(codeInput, { target: { value: "A" } });

      const submitBtn = screen.getByRole("button", { name: /Cadastrar Site/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Código deve ter pelo menos 2 caracteres/i)).toBeTruthy();
      });
      expect(inventoryApi.createSite).not.toHaveBeenCalled();
    });

    it("envia dados e chama createSite com formato correto", async () => {
      const mockCreated = {
        id: "site-uuid",
        code: "POP-SUL",
        name: "Estação Sul",
        kind: "pop" as const,
        location: { type: "Point" as const, coordinates: [-46.63, -23.55] as [number, number] },
        status: "installed" as const,
        version: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      vi.mocked(inventoryApi.createSite).mockResolvedValueOnce(mockCreated);
      const onSuccess = vi.fn();

      renderWithQueryClient(
        <SiteFormDialog
          open={true}
          onOpenChange={vi.fn()}
          onSuccess={onSuccess}
        />
      );

      fireEvent.change(screen.getByLabelText(/Código Único/i), { target: { value: "POP-SUL" } });
      fireEvent.change(screen.getByLabelText(/Nome do Local Técnico/i), { target: { value: "Estação Sul" } });

      const submitBtn = screen.getByRole("button", { name: /Cadastrar Site/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(inventoryApi.createSite).toHaveBeenCalledWith(
          expect.objectContaining({
            code: "POP-SUL",
            name: "Estação Sul",
            kind: "pop",
            status: "installed",
          })
        );
      });
      expect(onSuccess).toHaveBeenCalledWith(mockCreated);
    });
  });

  describe("StructureFormDialog", () => {
    it("renderiza opções de tipo para Poste, CEO e CTO", () => {
      renderWithQueryClient(
        <StructureFormDialog
          open={true}
          onOpenChange={vi.fn()}
          defaultKind="cto"
          onSuccess={vi.fn()}
        />
      );

      expect(screen.getByLabelText(/Código da Estrutura/i)).toBeTruthy();
      expect(screen.getByLabelText(/Tipo de Estrutura/i)).toBeTruthy();
      expect(screen.getByLabelText(/Capacidade \(Portas\)/i)).toBeTruthy();
    });

    it("salva estrutura física chamando createStructure", async () => {
      const mockStructure = {
        id: "struct-uuid",
        code: "CTO-10",
        kind: "cto",
        location: { type: "Point" as const, coordinates: [-46.63, -23.55] as [number, number] },
        capacity: 16,
        status: "installed",
        condition: "ok",
        version: 1,
      };
      vi.mocked(inventoryApi.createStructure).mockResolvedValueOnce(mockStructure);

      renderWithQueryClient(
        <StructureFormDialog
          open={true}
          onOpenChange={vi.fn()}
          defaultKind="cto"
          onSuccess={vi.fn()}
        />
      );

      fireEvent.change(screen.getByLabelText(/Código da Estrutura/i), { target: { value: "CTO-10" } });

      const submitBtn = screen.getByRole("button", { name: /Cadastrar Estrutura/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(inventoryApi.createStructure).toHaveBeenCalledWith(
          expect.objectContaining({
            code: "CTO-10",
            kind: "cto",
            capacity: 16,
          })
        );
      });
    });
  });

  describe("DeviceFormDialog — Regra de Exclusividade Site vs Estrutura", () => {
    it("renderiza campos e valida obrigatoriedade de fabricante e modelo", async () => {
      renderWithQueryClient(
        <DeviceFormDialog
          open={true}
          onOpenChange={vi.fn()}
          onSuccess={vi.fn()}
        />
      );

      expect(screen.getByLabelText(/Código do Dispositivo/i)).toBeTruthy();
      expect(screen.getByLabelText(/Fabricante/i)).toBeTruthy();
      expect(screen.getByLabelText(/Modelo/i)).toBeTruthy();
      expect(screen.getByLabelText(/Número de Série \(Serial\)/i)).toBeTruthy();

      fireEvent.change(screen.getByLabelText(/Código do Dispositivo/i), { target: { value: "OLT-01" } });
      const submitBtn = screen.getByRole("button", { name: /Cadastrar Dispositivo/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Fabricante é obrigatório/i)).toBeTruthy();
        expect(screen.getByText(/Modelo é obrigatório/i)).toBeTruthy();
      });
      expect(inventoryApi.createDevice).not.toHaveBeenCalled();
    });

    it("alterna localização mútua exclusiva entre Site e Estrutura sem conflito", async () => {
      renderWithQueryClient(
        <DeviceFormDialog
          open={true}
          onOpenChange={vi.fn()}
          onSuccess={vi.fn()}
        />
      );

      // Inicialmente em Site
      const siteRadio = screen.getByLabelText(/Alocado em Site \/ POP/i) as HTMLInputElement;
      const structRadio = screen.getByLabelText(/Alocado em Estrutura Externa/i) as HTMLInputElement;
      expect(siteRadio.checked).toBe(true);
      expect(screen.getByLabelText(/Selecione o Site \/ POP/i)).toBeTruthy();

      // Alterna para Estrutura
      fireEvent.click(structRadio);
      expect(structRadio.checked).toBe(true);
      expect(screen.getByLabelText(/Selecione a Estrutura/i)).toBeTruthy();
    });
  });

  describe("DeactivationDialog — Concorrência e Integridade Referencial", () => {
    it("exibe alerta claro sobre vínculos quando há dependências ativas", () => {
      render(
        <DeactivationDialog
          open={true}
          onOpenChange={vi.fn()}
          title="Desativar Site / POP"
          entityName="POP-CENTRO"
          entityTypeLabel="Site"
          version={1}
          dependencies={[
            { label: "Equipamentos instalados", count: 3 },
            { label: "Estruturas associadas", count: 0 },
          ]}
          onConfirm={vi.fn()}
          onSuccess={vi.fn()}
        />
      );

      expect(screen.getByText(/Verificação de Vínculos e Dependências/i)).toBeTruthy();
      expect(screen.getByText(/Equipamentos instalados/i)).toBeTruthy();
      expect(screen.getByText(/3/)).toBeTruthy();
      expect(screen.getByText(/Existem vínculos ativos/i)).toBeTruthy();
    });

    it("traduz erro RFC 7807 409 (referenced_entity_conflict) em mensagem orientada", async () => {
      const conflictError = new ApiError(
        {
          type: "about:blank",
          title: "Conflito",
          status: 409,
          detail: "Não é possível excluir o site pois existem estruturas ou dispositivos vinculados.",
          code: "referenced_entity_conflict",
        },
        409
      );

      const onConfirm = vi.fn().mockRejectedValueOnce(conflictError);

      render(
        <DeactivationDialog
          open={true}
          onOpenChange={vi.fn()}
          title="Desativar Site"
          entityName="POP-MATRIZ"
          entityTypeLabel="Site"
          version={2}
          onConfirm={onConfirm}
          onSuccess={vi.fn()}
        />
      );

      const confirmBtn = screen.getByRole("button", { name: /Confirmar Desativação/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(screen.getByText(/Operação bloqueada por integridade referencial/i)).toBeTruthy();
        expect(
          screen.getByText(/Desvincule ou transfira os elementos vinculados antes de desativar/i)
        ).toBeTruthy();
      });
    });

    it("orienta sobre concorrência otimista quando ocorre erro 412 Precondition Failed", async () => {
      const preconditionError = new ApiError(
        {
          type: "about:blank",
          title: "Precondition Failed",
          status: 412,
          detail: "Versão informada não confere.",
          code: "precondition_failed",
        },
        412
      );

      const onConfirm = vi.fn().mockRejectedValueOnce(preconditionError);

      render(
        <DeactivationDialog
          open={true}
          onOpenChange={vi.fn()}
          title="Desativar Estrutura"
          entityName="POSTE-01"
          entityTypeLabel="Estrutura"
          version={1}
          onConfirm={onConfirm}
          onSuccess={vi.fn()}
        />
      );

      const confirmBtn = screen.getByRole("button", { name: /Confirmar Desativação/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(screen.getByText(/Conflito de versão \(412\)/i)).toBeTruthy();
      });
    });
  });
});
