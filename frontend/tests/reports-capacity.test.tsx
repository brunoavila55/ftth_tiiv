import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReportsView } from "@/features/reports/components/reports-view";
import * as reportsApi from "@/features/reports/api";
import type {
  CTOOccupancyReportItem,
  CableCapacityReportItem,
  InconsistencyReportItem,
  PaginatedResponse,
} from "@/features/reports/types";

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

const mockCTOsData: PaginatedResponse<CTOOccupancyReportItem> = {
  items: [
    {
      structure_id: "cto-uuid-1",
      code: "CTO-CENTRAL-01",
      site_id: "site-uuid-1",
      site_name: "POP Central",
      total_ports: 8,
      occupied_ports: 2,
      reserved_ports: 1,
      free_ports: 5,
      occupancy_pct: 25.0,
      status: "installed",
    },
    {
      structure_id: "cto-uuid-2",
      code: "CTO-CENTRAL-02",
      site_id: "site-uuid-1",
      site_name: "POP Central",
      total_ports: 16,
      occupied_ports: 16,
      reserved_ports: 0,
      free_ports: 0,
      occupancy_pct: 100.0,
      status: "installed",
    },
    {
      structure_id: "cto-uuid-3",
      code: "CTO-NORTH-01",
      site_id: null,
      site_name: null,
      total_ports: 8,
      occupied_ports: 7,
      reserved_ports: 0,
      free_ports: 1,
      occupancy_pct: 87.5,
      status: "installed",
    },
  ],
  total: 3,
  page: 1,
  page_size: 20,
};

const mockCablesData: PaginatedResponse<CableCapacityReportItem> = {
  items: [
    {
      cable_id: "cable-uuid-1",
      code: "CAB-TRUNK-01",
      model: "CFOA-SM-AS-24F",
      cable_type: "optical_cable",
      total_fibers: 24,
      connected_fibers: 12,
      reserved_fibers: 4,
      free_fibers: 8,
      damaged_fibers: 0,
      usage_pct: 66.7,
      status: "installed",
    },
    {
      cable_id: "cable-uuid-2",
      code: "CAB-DIST-01",
      model: "CFOA-SM-AS-12F",
      cable_type: "optical_cable",
      total_fibers: 12,
      connected_fibers: 2,
      reserved_fibers: 0,
      free_fibers: 9,
      damaged_fibers: 1,
      usage_pct: 16.7,
      status: "installed",
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

const mockInconsistenciesData: PaginatedResponse<InconsistencyReportItem> = {
  items: [
    {
      inconsistency_type: "cable_without_segments",
      entity_type: "cable",
      entity_id: "cable-uuid-99",
      code: "CAB-UNSEG-99",
      severity: "critical",
      description: "Cabo sem segmentos georreferenciados na malha.",
    },
    {
      inconsistency_type: "damaged_port",
      entity_type: "port",
      entity_id: "port-uuid-88",
      code: "P-DANIFICADA-01",
      severity: "warning",
      description: "Porta física com nota de defeito ou avaria.",
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

describe("ReportsView and Capacity Analysis (F17)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(reportsApi, "getCTOOccupancyReport").mockResolvedValue(mockCTOsData);
    vi.spyOn(reportsApi, "getCableCapacityReport").mockResolvedValue(mockCablesData);
    vi.spyOn(reportsApi, "getInconsistenciesReport").mockResolvedValue(mockInconsistenciesData);
  });

  it("renders CTO occupancy tab by default with KPIs, table data and quick export link", async () => {
    renderWithQuery(<ReportsView />);

    // Verifica abas
    expect(screen.getByRole("button", { name: /Ocupação de CTOs/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Capacidade de Cabos/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Inconsistências Técnicas/i })).toBeDefined();

    // Aguarda carregamento dos dados da CTO
    await waitFor(() => {
      expect(screen.getByText("CTO-CENTRAL-01")).toBeDefined();
      expect(screen.getByText("CTO-CENTRAL-02")).toBeDefined();
      expect(screen.getByText("CTO-NORTH-01")).toBeDefined();
    });

    // Verifica métricas dos cards
    expect(screen.getByText("Total de CTOs na Consulta")).toBeDefined();
    expect(screen.getByText("CTOs Críticas (≥ 80%)")).toBeDefined();
    expect(screen.getByText("CTOs Esgotadas (100%)")).toBeDefined();

    // Verifica badges de faixa de ocupação
    expect(screen.getByText("Baixa")).toBeDefined();
    expect(screen.getByText("Esgotada")).toBeDefined();
    expect(screen.getByText("Crítica")).toBeDefined();

    // Verifica botão de exportação da camada CTOs
    const exportLink = screen.getByRole("link", { name: /Exportar Camada CTOs/i });
    expect(exportLink.getAttribute("href")).toBe("/exports?layer=ctos");
  });

  it("applies filters on CTO occupancy report and resets them correctly", async () => {
    renderWithQuery(<ReportsView />);

    await waitFor(() => {
      expect(screen.getByText("CTO-CENTRAL-01")).toBeDefined();
    });

    const minOccInput = screen.getByLabelText(/Ocupação Mínima/i);
    fireEvent.change(minOccInput, { target: { value: "50" } });

    const filterBtn = screen.getByRole("button", { name: /^Filtrar$/i });
    fireEvent.click(filterBtn);

    await waitFor(() => {
      expect(reportsApi.getCTOOccupancyReport).toHaveBeenCalledWith(
        expect.objectContaining({
          min_occupancy_pct: 50,
          page: 1,
          page_size: 20,
        }),
        expect.anything()
      );
    });

    // Resetar filtros
    const resetBtn = screen.getByRole("button", { name: /Limpar/i });
    fireEvent.click(resetBtn);

    await waitFor(() => {
      expect(reportsApi.getCTOOccupancyReport).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1,
          page_size: 20,
        }),
        expect.anything()
      );
    });
  });

  it("switches to Cable Capacity tab and displays fiber metrics, progress bars and export link", async () => {
    renderWithQuery(<ReportsView />);

    const cablesTabBtn = screen.getByRole("button", { name: /Capacidade de Cabos/i });
    fireEvent.click(cablesTabBtn);

    await waitFor(() => {
      expect(screen.getByText("CAB-TRUNK-01")).toBeDefined();
      expect(screen.getByText("CAB-DIST-01")).toBeDefined();
    });

    // Verifica cards de cabos
    expect(screen.getByText("Total de Cabos na Consulta")).toBeDefined();
    expect(screen.getByText("Utilização Média Global")).toBeDefined();
    expect(screen.getByText("Fibras Disponíveis (Livres)")).toBeDefined();
    expect(screen.getByText("Fibras Danificadas / Defeito")).toBeDefined();

    // Verifica presença de fibra danificada destacada
    expect(screen.getByText("CFOA-SM-AS-24F")).toBeDefined();

    // Verifica botão de exportação da camada Cabos
    const exportLink = screen.getByRole("link", { name: /Exportar Camada Cabos/i });
    expect(exportLink.getAttribute("href")).toBe("/exports?layer=cables");
  });

  it("switches to Inconsistencies tab and displays severities, anomaly descriptions and navigation links", async () => {
    renderWithQuery(<ReportsView />);

    const inconsTabBtn = screen.getByRole("button", { name: /Inconsistências Técnicas/i });
    fireEvent.click(inconsTabBtn);

    await waitFor(() => {
      expect(screen.getByText("CAB-UNSEG-99")).toBeDefined();
      expect(screen.getByText("P-DANIFICADA-01")).toBeDefined();
    });

    // Verifica cards
    expect(screen.getByText("Total de Pendências Detectadas")).toBeDefined();
    expect(screen.getByText("Inconsistências Críticas")).toBeDefined();
    expect(screen.getByText("Alertas e Advertências")).toBeDefined();

    // Verifica badges de severidade
    expect(screen.getByText("critical")).toBeDefined();
    expect(screen.getByText("warning")).toBeDefined();

    // Verifica labels amigáveis
    expect(screen.getByText("Cabo sem segmentos georreferenciados")).toBeDefined();
    expect(screen.getByText("Porta física com avaria ou defeito")).toBeDefined();

    // Link para ver elemento
    const actionLinks = screen.getAllByRole("link", { name: /Ver elemento/i });
    expect(actionLinks[0].getAttribute("href")).toBe("/cables/cable-uuid-99");
  });

  it("renders empty state when no items match filters", async () => {
    vi.spyOn(reportsApi, "getCTOOccupancyReport").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    renderWithQuery(<ReportsView />);

    await waitFor(() => {
      expect(
        screen.getByText(/Nenhuma caixa CTO encontrada com os filtros selecionados/i)
      ).toBeDefined();
    });
  });

  it("renders error state on API failure and provides retry button", async () => {
    vi.spyOn(reportsApi, "getCTOOccupancyReport").mockRejectedValue(
      new Error("Erro de conexão com o servidor")
    );

    renderWithQuery(<ReportsView />);

    await waitFor(() => {
      expect(screen.getByText(/Erro ao carregar relatório de CTOs/i)).toBeDefined();
      expect(screen.getByRole("button", { name: /Tentar novamente/i })).toBeDefined();
    });
  });
});
