import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardView } from "@/features/reports/components/dashboard-view";
import { GlobalSearchDialog } from "@/components/ui/global-search-dialog";
import * as reportsApi from "@/features/reports/api";

// Mock do router do Next.js
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// O diálogo filtra a navegação pelas permissões do usuário (R27)
vi.mock("@/features/auth/auth-context", () => ({
  useAuth: () => ({ hasPermission: () => true }),
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

describe("Dashboard Operacional e Busca Global (F05)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("DashboardView Component", () => {
    it("exibe estado de carregamento ao inicializar", () => {
      vi.spyOn(reportsApi, "getDashboardSummary").mockReturnValue(
        new Promise(() => {}) // Promessa pendente
      );

      renderWithQuery(<DashboardView />);

      expect(
        screen.getByText("Consultando indicadores consolidados da rede óptica...")
      ).toBeDefined();
    });

    it("exibe estado de erro e NÃO mostra zeros falsos quando a requisição falha", async () => {
      vi.spyOn(reportsApi, "getDashboardSummary").mockRejectedValue(
        new Error("Erro de conexão com o banco de dados")
      );

      renderWithQuery(<DashboardView />);

      await waitFor(() => {
        expect(
          screen.getByText("Falha ao carregar dados do painel operacional")
        ).toBeDefined();
      });

      expect(
        screen.getByText("Erro de conexão com o banco de dados")
      ).toBeDefined();

      // Confirma que não exibiu os cards com "0" fingindo ser dado real
      expect(screen.queryByText("POPs & Sites")).toBeNull();
      expect(screen.queryByText("Ocupação Documentada de CTOs")).toBeNull();
    });

    it("exibe empty state orientador quando não há ativos documentados", async () => {
      vi.spyOn(reportsApi, "getDashboardSummary").mockResolvedValue({
        total_sites: 0,
        total_structures: 0,
        total_cables: 0,
        total_customers: 0,
        total_active_service_links: 0,
        ctos_occupancy: {
          empty_0_pct: 0,
          low_1_to_50_pct: 0,
          high_51_to_99_pct: 0,
          full_100_pct: 0,
        },
        incomplete_documentation_alerts: [],
        topology_revision: 0,
      });

      renderWithQuery(<DashboardView />);

      await waitFor(() => {
        expect(
          screen.getByText("Nenhum elemento de rede documentado")
        ).toBeDefined();
      });

      const link = screen.getByRole("link", { name: /Cadastrar Primeiro POP \/ Site/i });
      expect(link.getAttribute("href")).toBe("/sites");
    });

    it("renderiza métricas reais, faixas de ocupação e alertas de documentação", async () => {
      vi.spyOn(reportsApi, "getDashboardSummary").mockResolvedValue({
        total_sites: 3,
        total_structures: 42,
        total_cables: 18,
        total_customers: 120,
        total_active_service_links: 98,
        ctos_occupancy: {
          empty_0_pct: 10,
          low_1_to_50_pct: 15,
          high_51_to_99_pct: 12,
          full_100_pct: 5,
        },
        incomplete_documentation_alerts: [
          "2 cabo(s) cadastrado(s) sem nenhum segmento georreferenciado",
        ],
        topology_revision: 7,
      });

      renderWithQuery(<DashboardView />);

      await waitFor(() => {
        expect(screen.getByText("Painel Operacional")).toBeDefined();
      });

      // Revisão de topologia
      expect(screen.getByText(/Revisão topológica/i)).toBeDefined();

      // Métricas dos cards
      expect(screen.getByText("POPs & Sites")).toBeDefined();
      expect(screen.getByText("3")).toBeDefined();
      expect(screen.getByText("Estruturas & Postes")).toBeDefined();
      expect(screen.getByText("42")).toBeDefined();
      expect(screen.getByText("Cabos Ópticos")).toBeDefined();
      expect(screen.getByText("18")).toBeDefined();
      expect(screen.getByText("Clientes & Conexões")).toBeDefined();
      expect(screen.getByText("120")).toBeDefined();
      expect(screen.getByText("98 serviço(s) ativo(s)")).toBeDefined();

      // Ocupação de CTOs
      expect(screen.getByText("Ocupação Documentada de CTOs")).toBeDefined();
      expect(screen.getByText("42 CTOs")).toBeDefined();
      expect(screen.getByText("0% Vazia")).toBeDefined();
      expect(screen.getByText("10")).toBeDefined();
      expect(screen.getByText("100% Esgotada")).toBeDefined();
      expect(screen.getByText("5")).toBeDefined();

      // Alertas de incompletude técnica
      expect(
        screen.getByText("1 apontamento(s) requerem atenção")
      ).toBeDefined();
      expect(
        screen.getByText("2 cabo(s) cadastrado(s) sem nenhum segmento georreferenciado")
      ).toBeDefined();

      // Atalhos abrem rotas corretas com filtros
      const popLink = screen.getByRole("link", { name: /Gerenciar POPs/i });
      expect(popLink.getAttribute("href")).toBe("/sites");

      const emptyCtoLink = screen.getByRole("link", { name: /0% Vazia/i });
      expect(emptyCtoLink.getAttribute("href")).toBe("/ctos?occupancy=empty");

      const fullCtoLink = screen.getByRole("link", { name: /100% Esgotada/i });
      expect(fullCtoLink.getAttribute("href")).toBe("/ctos?occupancy=full");
    });
  });

  describe("GlobalSearchDialog Component", () => {
    it("renderiza o modal quando aberto e fecha com Esc", () => {
      const handleOpenChange = vi.fn();
      render(<GlobalSearchDialog open={true} onOpenChange={handleOpenChange} />);

      expect(screen.getByRole("dialog")).toBeDefined();
      expect(screen.getByPlaceholderText(/Buscar páginas/i)).toBeDefined();

      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
      expect(handleOpenChange).toHaveBeenCalledWith(false);
    });

    it("dispara busca global no servidor ao digitar mais de 2 caracteres e exibe resultados de entidades", async () => {
      const handleOpenChange = vi.fn();
      vi.spyOn(reportsApi, "searchGlobal").mockResolvedValue({
        query: "POP",
        total_results: 2,
        groups: [
          {
            entity_type: "site",
            items: [
              {
                id: "1234",
                entity_type: "site",
                code: "POP-CENTRAL-01",
                name: "Estação Matriz",
                status: "installed",
              },
            ],
          },
          {
            entity_type: "cable",
            items: [
              {
                id: "5678",
                entity_type: "cable",
                code: "CAB-TRONCO-01",
                name: "Cabo 72FO",
                status: "installed",
              },
            ],
          },
        ],
      });

      render(<GlobalSearchDialog open={true} onOpenChange={handleOpenChange} />);

      const input = screen.getByPlaceholderText(/Buscar páginas/i);
      fireEvent.change(input, { target: { value: "POP" } });

      await waitFor(() => {
        expect(reportsApi.searchGlobal).toHaveBeenCalledWith(
          "POP",
          10,
          expect.any(AbortSignal)
        );
      });

      await waitFor(() => {
        expect(screen.getByText("POP-CENTRAL-01")).toBeDefined();
        expect(screen.getByText("POP: Estação Matriz")).toBeDefined();
        expect(screen.getByText("CAB-TRONCO-01")).toBeDefined();
      });

      // Clicar no resultado navega para o link correto
      const siteItem = screen.getByText("POP-CENTRAL-01").closest("div[role='option']");
      expect(siteItem).not.toBeNull();
      if (siteItem) {
        fireEvent.click(siteItem);
        expect(mockPush).toHaveBeenCalledWith("/sites?q=POP-CENTRAL-01");
        expect(handleOpenChange).toHaveBeenCalledWith(false);
      }
    });
  });
});
