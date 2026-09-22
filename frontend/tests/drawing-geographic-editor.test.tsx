import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  haversineDistance,
  calculateLineLength,
  findNearestSnapCandidate,
} from "@/features/map/utils/geometry";
import { DrawingToolbar } from "@/features/map/components/drawing-toolbar";
import { DrawingModal } from "@/features/map/components/drawing-modal";
import * as inventoryApi from "@/features/inventory/api";
import * as cablesApi from "@/features/cables/api";
import type { DrawingDraft } from "@/features/map/types";

// Mock de APIs
vi.mock("@/features/cables/api", () => ({
  listCables: vi.fn().mockResolvedValue({
    items: [
      {
        id: "cable-uuid-1",
        code: "CAB-TRONCO-72",
        model: "Cabo ASU 72FO",
        fiber_count: 72,
        tube_count: 6,
        color_standard: "NBR",
        status: "installed",
        version: 1,
      },
    ],
    total: 1,
  }),
  createCableSegment: vi.fn().mockResolvedValue({
    id: "segment-uuid-1",
    cable_id: "cable-uuid-1",
    origin_structure_id: "struct-1",
    destination_structure_id: "struct-2",
    geometry: {
      type: "LineString",
      coordinates: [
        [-46.633308, -23.55052],
        [-46.634, -23.551],
      ],
    },
    map_length_m: 85.5,
    measured_length_m: 90.0,
    slack_length_m: 10.0,
    effective_length_m: 90.0,
    length_source: "measured",
    version: 1,
  }),
}));

vi.mock("@/features/inventory/api", () => ({
  listStructures: vi.fn().mockResolvedValue({
    items: [
      {
        id: "struct-orig-1",
        code: "CTO-ORIG-01",
        kind: "cto",
        location: { type: "Point", coordinates: [-46.633308, -23.55052] },
        capacity: 16,
        status: "installed",
        condition: "ok",
        version: 1,
      },
      {
        id: "struct-dest-2",
        code: "CTO-DEST-02",
        kind: "cto",
        location: { type: "Point", coordinates: [-46.634, -23.551] },
        capacity: 16,
        status: "installed",
        condition: "ok",
        version: 1,
      },
    ],
    total: 2,
    page: 1,
    page_size: 200,
  }),
  createSite: vi.fn().mockResolvedValue({
    id: "site-uuid-new",
    code: "POP-NOVO",
    name: "Estação Nova",
    kind: "pop",
    status: "installed",
    version: 1,
  }),
  createStructure: vi.fn().mockResolvedValue({
    id: "struct-uuid-new",
    code: "CTO-NOVA-01",
    kind: "cto",
    status: "installed",
    version: 1,
  }),
}));

describe("Desenho e Edição Geográfica (F07)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Cálculos Geodésicos e Snap Magnético", () => {
    it("calcula distância de Haversine precisa entre duas coordenadas WGS-84", () => {
      // Coordenadas próximas (~85 a 90 metros em São Paulo)
      const p1: [number, number] = [-46.633308, -23.55052];
      const p2: [number, number] = [-46.634, -23.551];

      const dist = haversineDistance(p1, p2);
      expect(dist).toBeGreaterThan(80);
      expect(dist).toBeLessThan(110);
    });

    it("calcula a extensão acumulada de múltiplos vértices de um cabo óptico", () => {
      const coords: [number, number][] = [
        [-46.633308, -23.55052],
        [-46.634, -23.551],
        [-46.635, -23.552],
      ];

      const totalLen = calculateLineLength(coords);
      expect(totalLen).toBeGreaterThan(150);
      expect(totalLen).toBeLessThan(250);
    });

    it("identifica snap magnético à estrutura mais próxima dentro do raio limite", () => {
      const cursor: [number, number] = [-46.63335, -23.55054]; // ~5 metros de p1
      const candidates = [
        {
          id: "cto-1",
          code: "CTO-CENTRAL-01",
          entity_type: "cto",
          coordinates: [-46.633308, -23.55052] as [number, number],
        },
        {
          id: "pole-2",
          code: "POSTE-DISTANTE",
          entity_type: "pole",
          coordinates: [-46.64, -23.56] as [number, number],
        },
      ];

      const snap = findNearestSnapCandidate(cursor, candidates, 25);
      expect(snap).not.toBeNull();
      if (snap) {
        expect(snap.id).toBe("cto-1");
        expect(snap.code).toBe("CTO-CENTRAL-01");
        expect(snap.distanceMeters).toBeLessThan(10);
      }
    });

    it("retorna null quando nenhuma estrutura estiver dentro do raio de snap", () => {
      const cursor: [number, number] = [-46.65, -23.57]; // Bem longe
      const candidates = [
        {
          id: "cto-1",
          code: "CTO-CENTRAL-01",
          entity_type: "cto",
          coordinates: [-46.633308, -23.55052] as [number, number],
        },
      ];

      const snap = findNearestSnapCandidate(cursor, candidates, 25);
      expect(snap).toBeNull();
    });
  });

  describe("DrawingToolbar Component", () => {
    it("exibe o menu sem recorte e ativa a criação do tipo de ponto escolhido", () => {
      const handleSetMode = vi.fn();

      render(
        <DrawingToolbar
          mode="view"
          verticesCount={0}
          canUndo={false}
          canRedo={false}
          currentLengthMeters={0}
          snapCandidate={null}
          onSetMode={handleSetMode}
          onUndo={vi.fn()}
          onRedo={vi.fn()}
          onCancel={vi.fn()}
          onFinish={vi.fn()}
        />
      );

      const toolbar = screen.getByRole("toolbar");
      const actionBar = toolbar.firstElementChild;
      expect(actionBar?.className).toContain("overflow-visible");
      expect(actionBar?.className).not.toContain("overflow-x-auto");

      fireEvent.click(screen.getByTitle("Adicionar POP, CTO, Poste ou CEO"));
      expect(screen.getByRole("menu", { name: "Tipo de ponto" })).toBeDefined();

      fireEvent.click(screen.getByRole("menuitem", { name: /CTO \(Terminação\)/i }));
      expect(handleSetMode).toHaveBeenCalledWith("draw_point", "cto");
      expect(screen.queryByRole("menu", { name: "Tipo de ponto" })).toBeNull();
    });

    it("renderiza modo ativo, instruções e botões de ação", () => {
      const handleSetMode = vi.fn();
      const handleUndo = vi.fn();
      const handleCancel = vi.fn();
      const handleFinish = vi.fn();

      render(
        <DrawingToolbar
          mode="draw_cable"
          verticesCount={2}
          canUndo={true}
          canRedo={false}
          currentLengthMeters={112.5}
          snapCandidate={{
            id: "cto-1",
            code: "CTO-01",
            entity_type: "cto",
            coordinates: [-46.633, -23.55],
            distanceMeters: 2.1,
          }}
          onSetMode={handleSetMode}
          onUndo={handleUndo}
          onRedo={vi.fn()}
          onCancel={handleCancel}
          onFinish={handleFinish}
        />
      );

      expect(screen.getByRole("toolbar")).toBeDefined();
      expect(screen.getByText(/Adicionando vértices/i)).toBeDefined();
      expect(screen.getByText(/Snap: CTO-01/i)).toBeDefined();

      const undoBtn = screen.getByLabelText("Desfazer");
      fireEvent.click(undoBtn);
      expect(handleUndo).toHaveBeenCalledTimes(1);

      const cancelBtn = screen.getByLabelText("Cancelar desenho");
      fireEvent.click(cancelBtn);
      expect(handleCancel).toHaveBeenCalledTimes(1);

      const finishBtn = screen.getByLabelText("Concluir traçado");
      expect(finishBtn.hasAttribute("disabled")).toBe(false);
      fireEvent.click(finishBtn);
      expect(handleFinish).toHaveBeenCalledTimes(1);
    });
  });

  describe("DrawingModal Component", () => {
    it("renderiza e persiste ponto no inventário físico", async () => {
      const handleSuccess = vi.fn();
      const draft: DrawingDraft = {
        mode: "draw_point",
        pointKind: "cto",
        coordinates: [[-46.633308, -23.55052]],
      };

      render(
        <DrawingModal
          open={true}
          draft={draft}
          onClose={vi.fn()}
          onSuccess={handleSuccess}
        />
      );

      expect(screen.getByText("Cadastrar CTO")).toBeDefined();

      const saveBtn = screen.getByRole("button", { name: /Confirmar e Salvar/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(inventoryApi.createStructure).toHaveBeenCalledWith(
          expect.objectContaining({
            kind: "cto",
            status: "installed",
            location: {
              type: "Point",
              coordinates: [-46.633308, -23.55052],
            },
          })
        );
        expect(handleSuccess).toHaveBeenCalledWith("struct-uuid-new");
      });
    });

    it("renderiza métricas tripartidas de comprimento óptico para traçado de cabos", async () => {
      const handleSuccess = vi.fn();
      const draft: DrawingDraft = {
        mode: "draw_cable",
        coordinates: [
          [-46.633308, -23.55052],
          [-46.634, -23.551],
        ],
        originStructureId: "struct-orig-1",
        originStructureCode: "CTO-ORIG-01",
        destinationStructureId: "struct-dest-2",
        destinationStructureCode: "POSTE-DEST-02",
      };

      render(
        <DrawingModal
          open={true}
          draft={draft}
          onClose={vi.fn()}
          onSuccess={handleSuccess}
        />
      );

      expect(screen.getByText("Cadastrar Trecho de Cabo Óptico")).toBeDefined();
      expect(screen.getByText("Métricas de Comprimento e Regra Óptica")).toBeDefined();
      expect(screen.getByText("Mapa (Geodésico)")).toBeDefined();
      expect(screen.getByText("Medido (Campo)")).toBeDefined();
      expect(screen.getByText("Reserva Técnica")).toBeDefined();

      // Confirma valores pré-preenchidos de snap
      expect(screen.getByText("Snap: CTO-ORIG-01")).toBeDefined();
      expect(screen.getByText("Snap: POSTE-DEST-02")).toBeDefined();

      // Aguarda carregamento assíncrono dos cabos disponíveis para seleção
      await waitFor(() => {
        expect(screen.getByText(/CAB-TRONCO-72/i)).toBeDefined();
      });

      // Salva o trecho de cabo
      const saveBtn = screen.getByRole("button", { name: /Confirmar e Salvar/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(cablesApi.createCableSegment).toHaveBeenCalledWith(
          expect.objectContaining({
            cable_id: "cable-uuid-1",
            origin_structure_id: "struct-orig-1",
            destination_structure_id: "struct-dest-2",
            geometry: {
              type: "LineString",
              coordinates: [
                [-46.633308, -23.55052],
                [-46.634, -23.551],
              ],
            },
            slack_length_m: 10,
          })
        );
        expect(handleSuccess).toHaveBeenCalledWith("segment-uuid-1");
      });
    });

    it("associa CTOs pelas listas e encaixa as pontas do traçado nas estruturas", async () => {
      const handleSuccess = vi.fn();
      const draft: DrawingDraft = {
        mode: "draw_cable",
        coordinates: [
          [-46.632, -23.549],
          [-46.635, -23.552],
        ],
      };

      render(
        <DrawingModal
          open={true}
          draft={draft}
          onClose={vi.fn()}
          onSuccess={handleSuccess}
        />
      );

      const originSelect = await screen.findByLabelText(/Estrutura Origem/);
      const destinationSelect = screen.getByLabelText(/Estrutura Destino/);

      await waitFor(() => {
        expect(screen.getAllByText(/CTO-ORIG-01 — CTO/).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/CTO-DEST-02 — CTO/).length).toBeGreaterThan(0);
      });

      fireEvent.change(originSelect, { target: { value: "struct-orig-1" } });
      fireEvent.change(destinationSelect, { target: { value: "struct-dest-2" } });
      fireEvent.click(screen.getByRole("button", { name: /Confirmar e Salvar/i }));

      await waitFor(() => {
        expect(cablesApi.createCableSegment).toHaveBeenCalledWith(
          expect.objectContaining({
            origin_structure_id: "struct-orig-1",
            destination_structure_id: "struct-dest-2",
            geometry: {
              type: "LineString",
              coordinates: [
                [-46.633308, -23.55052],
                [-46.634, -23.551],
              ],
            },
          })
        );
      });
    });
  });
});
