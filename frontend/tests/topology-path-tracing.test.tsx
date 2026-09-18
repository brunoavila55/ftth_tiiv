import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TopologyTraceView } from "@/features/topology/components/topology-trace-view";
import * as topologyApi from "@/features/topology/api";
import * as customerApi from "@/features/customers/api";
import type { TraceResponse } from "@/features/topology/types";

// Mock do next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/topology",
}));

// Mock das APIs
vi.mock("@/features/topology/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/topology/api")>();
  return {
    ...actual,
    traceOpticalPath: vi.fn(),
  };
});

vi.mock("@/features/customers/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/customers/api")>();
  return {
    ...actual,
    listCustomers: vi.fn(),
  };
});

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe("Rastreamento Óptico e Topologia (F12)", () => {
  const mockCompleteTraceResponse: TraceResponse = {
    topology_revision: 5,
    status: "complete",
    paths: [
      {
        path_id: "path_abc123",
        origin_terminal_id: "term-pon-01",
        destination_terminal_id: "term-onu-01",
        total_length_m: 2000.0,
        total_loss_db: 0.7,
        steps: [
          {
            step_number: 1,
            element_type: "fusion",
            element_id: "conn-fuse-1",
            element_code: "Fusão Central",
            input_terminal_id: "term-pon-01",
            output_terminal_id: "term-c1-a",
            length_m: 0.0,
            loss_db: 0.1,
            accumulated_length_m: 0.0,
            accumulated_loss_db: 0.1,
            location_code: "SITE-CENTRAL",
          },
          {
            step_number: 2,
            element_type: "fiber_segment",
            element_id: "fseg-1",
            element_code: "CAB-TRONCAL-01 - FO #1",
            input_terminal_id: "term-c1-a",
            output_terminal_id: "term-c1-b",
            length_m: 2000.0,
            loss_db: 0.5,
            accumulated_length_m: 2000.0,
            accumulated_loss_db: 0.6,
            location_code: "SITE-CENTRAL",
          },
          {
            step_number: 3,
            element_type: "fusion",
            element_id: "conn-fuse-2",
            element_code: "Fusão CTO",
            input_terminal_id: "term-c1-b",
            output_terminal_id: "term-onu-01",
            length_m: 0.0,
            loss_db: 0.1,
            accumulated_length_m: 2000.0,
            accumulated_loss_db: 0.7,
            location_code: "CTO-FINAL-01",
          },
        ],
      },
    ],
    warnings: [],
    unresolved_terminals: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(customerApi.listCustomers).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
    });
  });

  it("renderiza o traçado óptico completo com timeline ordenada de passos", async () => {
    vi.mocked(topologyApi.traceOpticalPath).mockResolvedValue(mockCompleteTraceResponse);

    renderWithQueryClient(<TopologyTraceView />);

    // Informa terminal de partida
    const input = screen.getByLabelText(/Terminal Óptico de Partida/i);
    fireEvent.change(input, { target: { value: "00000000-0000-0000-0000-000000000001" } });

    // Dispara rastreamento
    const traceBtn = screen.getByRole("button", { name: /^Rastrear$/i });
    fireEvent.click(traceBtn);

    await waitFor(() => {
      // Valida banner de status
      expect(screen.getByRole("status")).toBeDefined();
      expect(screen.getByText(/Rastreamento Concluído com Sucesso/i)).toBeDefined();
    });

    // Valida revisão topológica
    expect(screen.getByText("v5")).toBeDefined();

    // Valida passos ordenados
    expect(screen.getAllByText("Fusão Central").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("CAB-TRONCAL-01 - FO #1")).toBeDefined();
    expect(screen.getByText("Fusão CTO")).toBeDefined();
  });

  it("clique no step detalha o elemento técnico e link para recurso", async () => {
    vi.mocked(topologyApi.traceOpticalPath).mockResolvedValue(mockCompleteTraceResponse);

    renderWithQueryClient(<TopologyTraceView />);

    const input = screen.getByLabelText(/Terminal Óptico de Partida/i);
    fireEvent.change(input, { target: { value: "00000000-0000-0000-0000-000000000001" } });
    fireEvent.click(screen.getByRole("button", { name: /^Rastrear$/i }));

    await waitFor(() => {
      expect(screen.getByText("CAB-TRONCAL-01 - FO #1")).toBeDefined();
    });

    // Clica no passo 2 (cabo de fibra)
    const step2Btn = screen.getByText("CAB-TRONCAL-01 - FO #1");
    fireEvent.click(step2Btn);

    await waitFor(() => {
      expect(screen.getByText("Detalhes do Elemento Selecionado")).toBeDefined();
      expect(screen.getByText("Passo #2")).toBeDefined();
      expect(screen.getByText("Ver Cabo no Inventário")).toBeDefined();
    });
  });

  it("exibe ponta aberta e terminais não resolvidos quando o status é incomplete", async () => {
    const mockIncompleteResponse: TraceResponse = {
      topology_revision: 3,
      status: "incomplete",
      paths: [
        {
          path_id: "path_inc_01",
          origin_terminal_id: "term-pon-01",
          destination_terminal_id: "term-orphan-99",
          total_length_m: 500.0,
          total_loss_db: 0.12,
          steps: [],
        },
      ],
      warnings: ["Ponta aberta detectada: Terminal 'CAB-01 FO #1' não possui continuidade óptica."],
      unresolved_terminals: ["term-orphan-99"],
    };

    vi.mocked(topologyApi.traceOpticalPath).mockResolvedValue(mockIncompleteResponse);

    renderWithQueryClient(<TopologyTraceView />);

    const input = screen.getByLabelText(/Terminal Óptico de Partida/i);
    fireEvent.change(input, { target: { value: "00000000-0000-0000-0000-000000000002" } });
    fireEvent.click(screen.getByRole("button", { name: /^Rastrear$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Ponta Aberta Detectada/i)).toBeDefined();
      expect(screen.getByText(/term-orphan-99/i)).toBeDefined();
      expect(screen.getByText("INCOMPLETE")).toBeDefined();
    });
  });

  it("detecta ciclo óptico inválido com encerramento seguro sem travar a interface", async () => {
    const mockCycleResponse: TraceResponse = {
      topology_revision: 4,
      status: "cycle_detected",
      paths: [
        {
          path_id: "path_cycle_01",
          origin_terminal_id: "term-1",
          destination_terminal_id: "term-1",
          total_length_m: 10.0,
          total_loss_db: 0.3,
          steps: [],
        },
      ],
      warnings: ["Ciclo óptico detectado: O terminal 'T1' já foi visitado neste caminho."],
      unresolved_terminals: [],
    };

    vi.mocked(topologyApi.traceOpticalPath).mockResolvedValue(mockCycleResponse);

    renderWithQueryClient(<TopologyTraceView />);

    const input = screen.getByLabelText(/Terminal Óptico de Partida/i);
    fireEvent.change(input, { target: { value: "00000000-0000-0000-0000-000000000003" } });
    fireEvent.click(screen.getByRole("button", { name: /^Rastrear$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Ciclo Óptico Inválido Detectado/i)).toBeDefined();
      expect(screen.getByText("CYCLE_DETECTED")).toBeDefined();
    });
  });

  it("permite expansão e navegação entre múltiplos ramos de splitters", async () => {
    const mockMultiBranchResponse: TraceResponse = {
      topology_revision: 6,
      status: "complete",
      paths: [
        {
          path_id: "path_branch_1",
          origin_terminal_id: "term-in",
          destination_terminal_id: "term-out-1",
          total_length_m: 1500.0,
          total_loss_db: 10.5,
          steps: [
            {
              step_number: 1,
              element_type: "splitter",
              element_id: "spl-1",
              element_code: "SPL-01 (1:4) S#1",
              length_m: 0.0,
              loss_db: 7.2,
              accumulated_length_m: 0.0,
              accumulated_loss_db: 7.2,
            },
          ],
        },
        {
          path_id: "path_branch_2",
          origin_terminal_id: "term-in",
          destination_terminal_id: "term-out-2",
          total_length_m: 1600.0,
          total_loss_db: 10.5,
          steps: [
            {
              step_number: 1,
              element_type: "splitter",
              element_id: "spl-1",
              element_code: "SPL-01 (1:4) S#2",
              length_m: 0.0,
              loss_db: 7.2,
              accumulated_length_m: 0.0,
              accumulated_loss_db: 7.2,
            },
          ],
        },
      ],
      warnings: [],
      unresolved_terminals: [],
    };

    vi.mocked(topologyApi.traceOpticalPath).mockResolvedValue(mockMultiBranchResponse);

    renderWithQueryClient(<TopologyTraceView />);

    const input = screen.getByLabelText(/Terminal Óptico de Partida/i);
    fireEvent.change(input, { target: { value: "00000000-0000-0000-0000-000000000004" } });
    fireEvent.click(screen.getByRole("button", { name: /^Rastrear$/i }));

    await waitFor(() => {
      expect(screen.getByText("Ramificações Encontradas (2 ramos)")).toBeDefined();
      expect(screen.getByText(/Ramo #1/)).toBeDefined();
      expect(screen.getByText(/Ramo #2/)).toBeDefined();
    });

    // Alterna para o Ramo #2
    fireEvent.click(screen.getByText(/Ramo #2/));

    await waitFor(() => {
      expect(screen.getAllByText("SPL-01 (1:4) S#2").length).toBeGreaterThanOrEqual(1);
    });
  });
});
