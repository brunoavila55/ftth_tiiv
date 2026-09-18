import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FusionEditor } from "@/features/connectivity/components/fusion-editor";
import { ConnectionModal } from "@/features/connectivity/components/connection-modal";
import { DisconnectDialog } from "@/features/connectivity/components/disconnect-dialog";
import { ReservationDialog } from "@/features/connectivity/components/reservation-dialog";
import * as connectivityApi from "@/features/connectivity/api";
import { ApiError } from "@/lib/api/types";
import type {
  StructureConnectivityResponse,
  TerminalRead,
  ConnectionRead,
} from "@/features/connectivity/api";

// Mock da API de Conectividade
vi.mock("@/features/connectivity/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/connectivity/api")>();
  return {
    ...actual,
    getStructureConnectivity: vi.fn(),
    executeBatchConnections: vi.fn(),
    createConnection: vi.fn(),
    deleteConnection: vi.fn(),
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

describe("Editor de Fusões e Terminais (F10)", () => {
  const mockTerminals: TerminalRead[] = [
    {
      id: "term-fib-1",
      kind: "fiber_endpoint",
      entity_id: "fib-1",
      entity_type: "fiber",
      label: "CAB-TRONCAL-01 / Tubo 1.1 / FO #1",
      is_occupied: true,
    },
    {
      id: "term-fib-2",
      kind: "fiber_endpoint",
      entity_id: "fib-2",
      entity_type: "fiber",
      label: "CAB-TRONCAL-01 / Tubo 1.2 / FO #2",
      is_occupied: false,
    },
    {
      id: "term-spl-in",
      kind: "splitter_input",
      entity_id: "spl-1",
      entity_type: "splitter",
      label: "Splitter PLC 1:8 / IN",
      is_occupied: true,
    },
    {
      id: "term-spl-out-1",
      kind: "splitter_output",
      entity_id: "spl-1",
      entity_type: "splitter",
      label: "Splitter PLC 1:8 / OUT-1",
      is_occupied: false,
    },
    {
      id: "term-port-front",
      kind: "port_front",
      entity_id: "port-1",
      entity_type: "port",
      label: "Porta 1 (Frontal)",
      is_occupied: false,
    },
    {
      id: "term-port-back",
      kind: "port_back",
      entity_id: "port-1",
      entity_type: "port",
      label: "Porta 1 (Traseira)",
      is_occupied: false,
    },
  ];

  const mockConnections: ConnectionRead[] = [
    {
      id: "conn-1",
      terminal_a_id: "term-fib-1",
      terminal_b_id: "term-spl-in",
      connection_type: "fusion_splice",
      loss_db: 0.08,
      structure_id: "struct-ceo-01",
      is_active: true,
      version: 1,
      created_at: "2026-09-18T00:00:00Z",
      updated_at: "2026-09-18T00:00:00Z",
    },
  ];

  const mockConnectivityData: StructureConnectivityResponse = {
    structure_id: "struct-ceo-01",
    topology_revision: 14,
    terminals: mockTerminals,
    connections: mockConnections,
    reservations: [],
    internal_edges: [
      {
        id: "edge-1",
        terminal_a_id: "term-spl-in",
        terminal_b_id: "term-spl-out-1",
        edge_type: "splitter_split",
        entity_type: "splitter",
        entity_id: "spl-1",
        loss_db: 10.5,
        is_bidirectional: true,
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(connectivityApi.getStructureConnectivity).mockResolvedValue(mockConnectivityData);
  });

  it("renderiza o cabeçalho do editor com a revisão topológica monotônica", async () => {
    renderWithQueryClient(
      <FusionEditor
        structureId="struct-ceo-01"
        structureCode="CEO-DIST-01"
        structureKind="ceo"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Editor de Fusões e Terminais: CEO-DIST-01/i)).toBeTruthy();
      expect(screen.getByText("rev #14")).toBeTruthy();
    });
  });

  it("renderiza os 3 painéis lógicos (Fibras, Splitters e Portas) com diferenciação clara", async () => {
    renderWithQueryClient(
      <FusionEditor
        structureId="struct-ceo-01"
        structureCode="CEO-DIST-01"
        structureKind="ceo"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Pontas de Cabos \/ Fibras/i)).toBeTruthy();
      expect(screen.getByText(/Splitters Ópticos/i)).toBeTruthy();
      expect(screen.getByText(/Portas \(Frente \/ Traseira\)/i)).toBeTruthy();
    });

    // Terminal de entrada e saída do splitter devidamente rotulados
    expect(screen.getByText("Splitter PLC 1:8 / IN")).toBeTruthy();
    expect(screen.getByText("Splitter PLC 1:8 / OUT-1")).toBeTruthy();
  });

  it("alterna para a tabela textual acessível com ID do terminal como chave e todas as colunas", async () => {
    renderWithQueryClient(
      <FusionEditor
        structureId="struct-ceo-01"
        structureCode="CEO-DIST-01"
        structureKind="ceo"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Tabela Textual Acessível/i)).toBeTruthy();
    });

    // Clica na aba de tabela
    fireEvent.click(screen.getByText(/Tabela Textual Acessível/i));

    await waitFor(() => {
      expect(screen.getByText("Terminal ID")).toBeTruthy();
      expect(screen.getByText("Rótulo / Descrição")).toBeTruthy();
      expect(screen.getByText("term-fib-1")).toBeTruthy();
      expect(screen.getByText("term-fib-2")).toBeTruthy();
      expect(screen.getByText("term-spl-in")).toBeTruthy();
    });
  });

  it("impede conexão em terminal ocupado e valida seleção de dois terminais distintos", async () => {
    const onAddOperation = vi.fn();
    const occupiedIds = new Set(["term-fib-1", "term-spl-in"]);

    render(
      <ConnectionModal
        open={true}
        onOpenChange={vi.fn()}
        terminals={mockTerminals}
        initialTerminalAId="term-fib-2"
        occupiedTerminalIds={occupiedIds}
        onAddOperation={onAddOperation}
      />
    );

    // Terminal A está preenchido como term-fib-2 (livre)
    // Seleciona Terminal B
    const destSelect = screen.getByLabelText(/Terminal de Destino/i);
    fireEvent.change(destSelect, { target: { value: "term-spl-out-1" } });

    // Clica em Adicionar ao Lote
    const submitBtn = screen.getByRole("button", { name: /Adicionar ao Lote/i });
    fireEvent.click(submitBtn);

    expect(onAddOperation).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "connect",
        terminal_a_id: "term-fib-2",
        terminal_b_id: "term-spl-out-1",
        connection_type: "fusion_splice",
        loss_db: 0.1,
      })
    );
  });

  it("adiciona fusão ao rascunho de lote sem chamada imediata à API, permitindo remoção local", async () => {
    renderWithQueryClient(
      <FusionEditor
        structureId="struct-ceo-01"
        structureCode="CEO-DIST-01"
        structureKind="ceo"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Nenhuma operação em rascunho/i)).toBeTruthy();
    });

    // Clica no botão "Nova Conexão"
    fireEvent.click(screen.getByRole("button", { name: /Nova Conexão/i }));

    // Diálogo aberto
    await waitFor(() => {
      expect(screen.getByText("Nova Conexão Óptica")).toBeTruthy();
    });

    // Seleciona Terminal A (term-fib-2) e Terminal B (term-spl-out-1)
    const termASelect = screen.getByLabelText(/Terminal de Origem/i);
    fireEvent.change(termASelect, { target: { value: "term-fib-2" } });

    const termBSelect = screen.getByLabelText(/Terminal de Destino/i);
    fireEvent.change(termBSelect, { target: { value: "term-spl-out-1" } });

    fireEvent.click(screen.getByRole("button", { name: /Adicionar ao Lote/i }));

    // Operação adicionada ao carrinho de rascunho
    await waitFor(() => {
      expect(screen.getByText(/Lote de Alterações em Rascunho \(1\)/i)).toBeTruthy();
      expect(screen.getByText(/Confirmar e Aplicar Lote \(1\)/i)).toBeTruthy();
    });

    // Nenhuma chamada foi feita ao backend ainda!
    expect(connectivityApi.executeBatchConnections).not.toHaveBeenCalled();

    // Remove do rascunho local
    const removeBtn = screen.getByLabelText(/Remover operação 1 do rascunho/i);
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(screen.getByText(/Lote de Alterações em Rascunho \(0\)/i)).toBeTruthy();
    });
  });

  it("submete lote com expected_topology_revision ao clicar em Confirmar e Aplicar Lote", async () => {
    vi.mocked(connectivityApi.executeBatchConnections).mockResolvedValue({
      success: true,
      applied_operations_count: 1,
      new_topology_revision: 15,
    });

    renderWithQueryClient(
      <FusionEditor
        structureId="struct-ceo-01"
        structureCode="CEO-DIST-01"
        structureKind="ceo"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Nova Conexão/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Nova Conexão/i }));

    await waitFor(() => {
      expect(screen.getByText("Nova Conexão Óptica")).toBeTruthy();
    });

    const termASelect = screen.getByLabelText(/Terminal de Origem/i);
    fireEvent.change(termASelect, { target: { value: "term-fib-2" } });

    const termBSelect = screen.getByLabelText(/Terminal de Destino/i);
    fireEvent.change(termBSelect, { target: { value: "term-spl-out-1" } });

    fireEvent.click(screen.getByRole("button", { name: /Adicionar ao Lote/i }));

    await waitFor(() => {
      expect(screen.getByText(/Confirmar e Aplicar Lote \(1\)/i)).toBeTruthy();
    });

    // Submete o lote
    fireEvent.click(screen.getByRole("button", { name: /Confirmar e Aplicar Lote \(1\)/i }));

    await waitFor(() => {
      expect(connectivityApi.executeBatchConnections).toHaveBeenCalledWith({
        structure_id: "struct-ceo-01",
        expected_topology_revision: 14,
        operations: [
          {
            action: "connect",
            terminal_a_id: "term-fib-2",
            terminal_b_id: "term-spl-out-1",
            connection_type: "fusion_splice",
            loss_db: 0.1,
          },
        ],
      });
    });
  });

  it("trata conflito 409 de revisão divergente sem perder o rascunho de operações do operador", async () => {
    const conflictError = new ApiError(
      {
        title: "Conflict",
        status: 409,
        code: "topology_revision_conflict",
        detail: "Revisão topológica divergente. A topologia foi alterada por outro operador.",
      },
      409
    );

    vi.mocked(connectivityApi.executeBatchConnections).mockRejectedValue(conflictError);

    renderWithQueryClient(
      <FusionEditor
        structureId="struct-ceo-01"
        structureCode="CEO-DIST-01"
        structureKind="ceo"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Nova Conexão/i })).toBeTruthy();
    });

    // Prepara uma conexão no rascunho
    fireEvent.click(screen.getByRole("button", { name: /Nova Conexão/i }));
    const termASelect = screen.getByLabelText(/Terminal de Origem/i);
    fireEvent.change(termASelect, { target: { value: "term-fib-2" } });
    const termBSelect = screen.getByLabelText(/Terminal de Destino/i);
    fireEvent.change(termBSelect, { target: { value: "term-spl-out-1" } });
    fireEvent.click(screen.getByRole("button", { name: /Adicionar ao Lote/i }));

    // Clica em confirmar lote
    await waitFor(() => {
      expect(screen.getByText(/Confirmar e Aplicar Lote \(1\)/i)).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: /Confirmar e Aplicar Lote \(1\)/i }));

    // Modal de Conflito 409 deve abrir
    await waitFor(() => {
      expect(screen.getByText("Conflito de Revisão Topológica (409)")).toBeTruthy();
      expect(screen.getByText(/1 ações preservadas/i)).toBeTruthy();
    });

    // Ao clicar em Recarregar e Reconciliar, recarrega a conectividade
    const reconcileBtn = screen.getByRole("button", { name: /Recarregar e Reconciliar/i });
    fireEvent.click(reconcileBtn);

    await waitFor(() => {
      expect(connectivityApi.getStructureConnectivity).toHaveBeenCalledTimes(2);
      // As propostas no rascunho continuam preservadas!
      expect(screen.getByText(/Lote de Alterações em Rascunho \(1\)/i)).toBeTruthy();
    });
  });

  it("exibe diálogo de desconexão com aviso de impacto e adiciona disconnect ao lote", async () => {
    const onAddOperation = vi.fn();
    const connToDisconnect = mockConnections[0];

    render(
      <DisconnectDialog
        open={true}
        onOpenChange={vi.fn()}
        connection={connToDisconnect}
        terminals={mockTerminals}
        onAddOperation={onAddOperation}
      />
    );

    expect(screen.getByText("Desconectar Terminais Ópticos")).toBeTruthy();
    expect(screen.getByText(/Aviso de Impacto no Circuito/i)).toBeTruthy();

    // Confirma desconexão
    const confirmBtn = screen.getByRole("button", { name: /Adicionar Desconexão ao Lote/i });
    fireEvent.click(confirmBtn);

    expect(onAddOperation).toHaveBeenCalledWith({
      action: "disconnect",
      terminal_a_id: "term-fib-1",
      terminal_b_id: "term-spl-in",
    });
  });

  it("permite reservar terminal óptico com motivo obrigatório", async () => {
    const onAddOperation = vi.fn();
    const terminalToReserve = mockTerminals[1]; // term-fib-2

    render(
      <ReservationDialog
        open={true}
        onOpenChange={vi.fn()}
        terminal={terminalToReserve}
        onAddOperation={onAddOperation}
      />
    );

    expect(screen.getByText("Reservar Terminal Óptico")).toBeTruthy();

    const reasonInput = screen.getByLabelText(/Motivo da Reserva/i);
    fireEvent.change(reasonInput, { target: { value: "Reserva para cliente VIP" } });

    const submitBtn = screen.getByRole("button", { name: /Adicionar Reserva ao Lote/i });
    fireEvent.click(submitBtn);

    expect(onAddOperation).toHaveBeenCalledWith({
      action: "reserve",
      terminal_a_id: "term-fib-2",
      reservation_reason: "Reserva para cliente VIP",
    });
  });
});
