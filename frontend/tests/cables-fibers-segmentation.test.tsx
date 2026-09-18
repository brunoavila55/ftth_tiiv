import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  getColorForPosition,
  getFiberHierarchy,
  NBR_COLORS,
  TIA_598_COLORS,
} from "@/features/cables/utils/colors";
import { CableFormDialog } from "@/features/cables/components/cable-form-dialog";
import { CableFibersView } from "@/features/cables/components/cable-fibers-view";
import { SplitSegmentDialog } from "@/features/cables/components/split-segment-dialog";
import * as cablesApi from "@/features/cables/api";
import * as inventoryApi from "@/features/inventory/api";
import type { CableRead, CableSegmentRead } from "@/features/cables/api";

// Mock das APIs
vi.mock("@/features/cables/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/cables/api")>();
  return {
    ...actual,
    createCable: vi.fn(),
    updateCable: vi.fn(),
    deleteCable: vi.fn(),
    listSegmentFibers: vi.fn().mockResolvedValue({
      items: [
        {
          id: "fs-1",
          cable_segment_id: "seg-1",
          fiber_id: "fib-1",
          fiber_number: 1,
          terminal_a_id: "term-a-1",
          terminal_b_id: "term-b-1",
          occupancy: "connected",
        },
        {
          id: "fs-2",
          cable_segment_id: "seg-1",
          fiber_id: "fib-2",
          fiber_number: 2,
          terminal_a_id: "term-a-2",
          terminal_b_id: "term-b-2",
          occupancy: "free",
        },
      ],
      total: 2,
    }),
    previewSegmentSplit: vi.fn().mockResolvedValue({
      original_segment_id: "seg-1",
      access_structure_id: "struct-1",
      total_fibers_count: 12,
      cut_fibers_count: 2,
      pass_through_fibers_count: 10,
      segment_1_map_length_m: 150.5,
      segment_2_map_length_m: 230.2,
      warnings: ["Atenção: Fibra conectada FO #1 será cortada"],
    }),
    splitSegment: vi.fn().mockResolvedValue({
      success: true,
      original_segment_id: "seg-1",
      segment_1: { id: "seg-1-a" },
      segment_2: { id: "seg-1-b" },
      pass_through_continuities_count: 10,
      cut_terminals_count: 2,
      new_topology_revision: 5,
    }),
  };
});

vi.mock("@/features/inventory/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/inventory/api")>();
  return {
    ...actual,
    listStructures: vi.fn().mockResolvedValue({
      items: [
        { id: "struct-ceo-1", code: "CEO-01", kind: "ceo" },
        { id: "struct-cto-1", code: "CTO-04", kind: "cto" },
      ],
      total: 2,
    }),
  };
});

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Cabos, Tubos e Fibras (F09)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Normas de Cores e Hierarquia Tubo-Fibra", () => {
    it("segue a sequência oficial ABNT NBR 14106 com 12 cores padronizadas", () => {
      expect(NBR_COLORS.length).toBe(12);
      expect(NBR_COLORS[0].name).toBe("Verde");
      expect(NBR_COLORS[1].name).toBe("Amarelo");
      expect(NBR_COLORS[2].name).toBe("Branco");
      expect(NBR_COLORS[3].name).toBe("Azul");
      expect(NBR_COLORS[4].name).toBe("Vermelho");
      expect(NBR_COLORS[11].name).toBe("Aqua");
    });

    it("segue a sequência oficial ANSI / TIA-598", () => {
      expect(TIA_598_COLORS.length).toBe(12);
      expect(TIA_598_COLORS[0].name).toBe("Azul");
      expect(TIA_598_COLORS[1].name).toBe("Laranja");
      expect(TIA_598_COLORS[2].name).toBe("Verde");
      expect(TIA_598_COLORS[11].name).toBe("Aqua");
    });

    it("garante que fibras de mesma cor em tubos diferentes nunca se confundem", () => {
      // Cabo 24 FO com 2 tubos de 12 fibras cada (Norma NBR)
      // Fibra 1: Tubo 1 (Verde), Posição 1 no tubo (Verde)
      const fiber1 = getFiberHierarchy(1, 24, 2, "NBR");
      expect(fiber1.tubeNumber).toBe(1);
      expect(fiber1.fiberPositionInTube).toBe(1);
      expect(fiber1.tubeColor.name).toBe("Verde");
      expect(fiber1.fiberColor.name).toBe("Verde");

      // Fibra 13: Tubo 2 (Amarelo), Posição 1 no tubo (Verde)
      const fiber13 = getFiberHierarchy(13, 24, 2, "NBR");
      expect(fiber13.tubeNumber).toBe(2);
      expect(fiber13.fiberPositionInTube).toBe(1);
      expect(fiber13.tubeColor.name).toBe("Amarelo");
      expect(fiber13.fiberColor.name).toBe("Verde");

      // As fibras possuem a mesma cor ('Verde'), mas pertencem a tubos diferentes e identificações globais distintas
      expect(fiber1.fiberColor.name).toBe(fiber13.fiberColor.name);
      expect(fiber1.tubeNumber).not.toBe(fiber13.tubeNumber);
      expect(fiber1.tubeColor.name).not.toBe(fiber13.tubeColor.name);
    });
  });

  describe("CableFormDialog", () => {
    it("renderiza campos cadastrais com opções padronizadas de capacidade", () => {
      renderWithQueryClient(
        <CableFormDialog
          open={true}
          onOpenChange={vi.fn()}
          onSuccess={vi.fn()}
        />
      );

      expect(screen.getByLabelText(/Código do Cabo/i)).toBeTruthy();
      expect(screen.getByLabelText(/Modelo Comercial/i)).toBeTruthy();
      expect(screen.getByLabelText(/Capacidade Fibras \/ Tubos Loose/i)).toBeTruthy();
      expect(screen.getByLabelText(/Norma de Cores/i)).toBeTruthy();
      expect(screen.getByLabelText(/Situação Operacional/i)).toBeTruthy();
    });

    it("valida código obrigatório e submete dados chamando createCable", async () => {
      const mockCreated: CableRead = {
        id: "cable-uuid-1",
        code: "CAB-TRONCAL-01",
        model: "CFOA-SM-AS80-S-12F",
        fiber_count: 12,
        tube_count: 1,
        color_standard: "NBR",
        status: "installed",
        version: 1,
      };
      vi.mocked(cablesApi.createCable).mockResolvedValueOnce(mockCreated);
      const onSuccess = vi.fn();

      renderWithQueryClient(
        <CableFormDialog
          open={true}
          onOpenChange={vi.fn()}
          onSuccess={onSuccess}
        />
      );

      fireEvent.change(screen.getByLabelText(/Código do Cabo/i), {
        target: { value: "CAB-TRONCAL-01" },
      });
      fireEvent.change(screen.getByLabelText(/Modelo Comercial/i), {
        target: { value: "CFOA-SM-AS80-S-12F" },
      });

      const submitBtn = screen.getByRole("button", { name: /Cadastrar Cabo/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(cablesApi.createCable).toHaveBeenCalledWith(
          expect.objectContaining({
            code: "CAB-TRONCAL-01",
            model: "CFOA-SM-AS80-S-12F",
            fiber_count: 12,
            tube_count: 1,
            color_standard: "NBR",
          })
        );
      });
      expect(onSuccess).toHaveBeenCalledWith(mockCreated);
    });
  });

  describe("CableFibersView", () => {
    const mockCable: CableRead = {
      id: "cable-12fo",
      code: "CAB-DIST-12",
      model: "CFOA-AS-12F",
      fiber_count: 12,
      tube_count: 1,
      color_standard: "NBR",
      status: "installed",
      version: 1,
    };

    const mockSegments: CableSegmentRead[] = [
      {
        id: "seg-1",
        cable_id: "cable-12fo",
        origin_structure_id: "struct-1",
        destination_structure_id: "struct-2",
        geometry: { type: "LineString", coordinates: [[-46.63, -23.55], [-46.64, -23.56]] },
        map_length_m: 250,
        measured_length_m: 260,
        slack_length_m: 10,
        effective_length_m: 260,
        length_source: "measured",
        version: 1,
      },
    ];

    it("renderiza tubos e fibras com identificação e cores", async () => {
      renderWithQueryClient(
        <CableFibersView cable={mockCable} segments={mockSegments} />
      );

      await waitFor(() => {
        expect(screen.getByText(/Tubo Loose 1: Cor Verde/i)).toBeTruthy();
        expect(screen.getByText("FO #1")).toBeTruthy();
        expect(screen.getByText("FO #2")).toBeTruthy();
      });
    });

    it("permite filtrar por estado de ocupação", async () => {
      renderWithQueryClient(
        <CableFibersView cable={mockCable} segments={mockSegments} />
      );

      await waitFor(() => {
        expect(screen.getByText("FO #1")).toBeTruthy();
      });

      const occupancySelect = screen.getByLabelText(/Filtrar por ocupação/i);
      fireEvent.change(occupancySelect, { target: { value: "connected" } });

      await waitFor(() => {
        expect(screen.getByText("FO #1")).toBeTruthy();
        // A fibra 2 é 'free', não deve aparecer quando filtrado por connected
        expect(screen.queryByText("FO #2")).toBeNull();
      });
    });
  });

  describe("SplitSegmentDialog — Divisão de Trecho e Fibras Sangradas", () => {
    const mockSegment: CableSegmentRead = {
      id: "seg-1",
      cable_id: "cable-12fo",
      origin_structure_id: "struct-1",
      destination_structure_id: "struct-2",
      geometry: { type: "LineString", coordinates: [[-46.63, -23.55], [-46.64, -23.56]] },
      map_length_m: 380.7,
      measured_length_m: null,
      slack_length_m: 10,
      effective_length_m: 390.7,
      length_source: "calculated",
      version: 1,
    };

    it("exibe diálogo com seleção de estrutura e botões de corte de fibras", async () => {
      renderWithQueryClient(
        <SplitSegmentDialog
          open={true}
          onOpenChange={vi.fn()}
          segment={mockSegment}
          totalFibers={12}
          onSuccess={vi.fn()}
        />
      );

      expect(screen.getByText(/Dividir Trecho de Cabo Óptico/i)).toBeTruthy();
      expect(screen.getByLabelText(/Estrutura de Acesso \(Ponto de Divisão\)/i)).toBeTruthy();
      expect(screen.getByText(/Plano de Sangria de Fibras/i)).toBeTruthy();

      await waitFor(() => {
        expect(screen.getByText(/CEO-01/i)).toBeTruthy();
      });
    });

    it("alterna fibras para corte e executa prévia", async () => {
      renderWithQueryClient(
        <SplitSegmentDialog
          open={true}
          onOpenChange={vi.fn()}
          segment={mockSegment}
          totalFibers={12}
          onSuccess={vi.fn()}
        />
      );

      // Clica para cortar a fibra 1
      const fiberBtn1 = screen.getByTitle(/Fibra #1: PASSANTE/i);
      fireEvent.click(fiberBtn1);

      await waitFor(() => {
        expect(cablesApi.previewSegmentSplit).toHaveBeenCalled();
      });
    });

    it("confirma divisão chamando splitSegment na API", async () => {
      const onSuccess = vi.fn();

      renderWithQueryClient(
        <SplitSegmentDialog
          open={true}
          onOpenChange={vi.fn()}
          segment={mockSegment}
          totalFibers={12}
          onSuccess={onSuccess}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Confirmar Divisão do Trecho/i })).toBeTruthy();
      });

      const confirmBtn = screen.getByRole("button", { name: /Confirmar Divisão do Trecho/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(cablesApi.splitSegment).toHaveBeenCalledWith(
          "seg-1",
          expect.objectContaining({
            access_structure_id: expect.any(String),
          })
        );
      });
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
