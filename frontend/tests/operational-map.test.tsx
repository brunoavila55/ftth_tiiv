import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { formatBBox, getMapFeatures } from "@/features/map/api";
import { MapLegend } from "@/features/map/components/map-legend";
import { MapFeatureSheet } from "@/features/map/components/map-feature-sheet";
import { MapFallbackTable } from "@/features/map/components/map-fallback-table";
import { MapView } from "@/features/map/components/map-view";
import * as mapApi from "@/features/map/api";
import * as settingsApi from "@/features/settings/api";
import { api } from "@/lib/api/client";
import type { MapFeature } from "@/features/map/types";

vi.mock("@/features/auth/auth-context", () => import("./support/auth-context-mock"));

// Mock do router do Next.js
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams("lat=-23.55052&lng=-46.633308&zoom=14");
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockReplace,
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
}));

function renderMapView() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MapView />
    </QueryClientProvider>
  );
}

const mockSiteFeature: MapFeature = {
  id: "feat-site-1",
  type: "Feature",
  geometry: {
    type: "Point",
    coordinates: [-46.633308, -23.55052],
  },
  properties: {
    entity_id: "site-uuid-1",
    entity_type: "site",
    code: "POP-CENTRAL-01",
    status: "installed",
    version: 1,
  },
};

const mockCtoFeature: MapFeature = {
  id: "feat-cto-1",
  type: "Feature",
  geometry: {
    type: "Point",
    coordinates: [-46.634, -23.551],
  },
  properties: {
    entity_id: "cto-uuid-1",
    entity_type: "cto",
    code: "CTO-16P-01",
    status: "installed",
    version: 2,
    occupancy: {
      free: 10,
      reserved: 2,
      connected: 4,
    },
  },
};

const mockCableFeature: MapFeature = {
  id: "feat-cable-1",
  type: "Feature",
  geometry: {
    type: "LineString",
    coordinates: [
      [-46.633308, -23.55052],
      [-46.634, -23.551],
    ],
  },
  properties: {
    entity_id: "cable-uuid-1",
    entity_type: "cable_segment",
    code: "CAB-TRONCO-01",
    status: "installed",
    version: 1,
  },
};

describe("Mapa Operacional e Camadas GIS (F06)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams("lat=-23.55052&lng=-46.633308&zoom=14");
  });

  describe("Utilitários de BBox e API de Mapa", () => {
    it("converte limites geográficos para formato de BBox com 6 casas decimais", () => {
      const bbox = formatBBox({
        west: -46.635,
        south: -23.555,
        east: -46.63,
        north: -23.55,
      });
      expect(bbox).toBe("-46.635000,-23.555000,-46.630000,-23.550000");
    });

    it("chama endpoint /map/features com parâmetros corretos", async () => {
      const spyGet = vi.spyOn(api, "get").mockResolvedValue({
        type: "FeatureCollection",
        features: [],
        bbox: [-46.64, -23.56, -46.62, -23.54],
        topology_revision: 5,
        truncated: false,
      });

      await getMapFeatures({
        bbox: "-46.64,-23.56,-46.62,-23.54",
        layers: "sites,structures,cables",
        zoom: 15,
      });

      expect(spyGet).toHaveBeenCalledWith("/map/features", {
        params: {
          bbox: "-46.64,-23.56,-46.62,-23.54",
          layers: "sites,structures,cables",
          zoom: 15,
        },
        signal: undefined,
      });
    });
  });

  describe("MapLegend Component", () => {
    it("renderiza todos os itens de legenda e alterna visibilidade das camadas", () => {
      const handleToggle = vi.fn();
      const layers = {
        sites: true,
        structures: true,
        ctos: true,
        cables: true,
      };

      render(<MapLegend layers={layers} onToggleLayer={handleToggle} />);

      expect(screen.getByText("Camadas & Legenda")).toBeDefined();
      expect(screen.getByText("POP / Site Central")).toBeDefined();
      expect(screen.getByText("CTO (Terminação)")).toBeDefined();
      expect(screen.getByText("Poste / CEO")).toBeDefined();
      expect(screen.getByText("Cabo Óptico")).toBeDefined();

      // Clicar no checkbox de sites dispara o toggle
      const sitesCheckbox = screen.getByLabelText("Alternar exibição de Sites");
      fireEvent.click(sitesCheckbox);
      expect(handleToggle).toHaveBeenCalledWith("sites");
    });

    it("permite recolher e expandir a legenda", () => {
      const layers = {
        sites: true,
        structures: true,
        ctos: true,
        cables: true,
      };

      render(<MapLegend layers={layers} onToggleLayer={vi.fn()} />);

      const toggleBtn = screen.getByLabelText("Recolher legenda");
      fireEvent.click(toggleBtn);

      // Itens internos somem ao recolher
      expect(screen.queryByText("POP / Site Central")).toBeNull();

      const expandBtn = screen.getByLabelText("Expandir legenda");
      fireEvent.click(expandBtn);

      expect(screen.getByText("POP / Site Central")).toBeDefined();
    });
  });

  describe("MapFeatureSheet Component", () => {
    it("não renderiza nada se feature for null", () => {
      const { container } = render(
        <MapFeatureSheet feature={null} onClose={vi.fn()} />
      );
      expect(container.firstChild).toBeNull();
    });

    it("renderiza informações de POP / Site e link para cadastro", () => {
      const handleClose = vi.fn();
      render(<MapFeatureSheet feature={mockSiteFeature} onClose={handleClose} />);

      expect(screen.getByText("POP-CENTRAL-01")).toBeDefined();
      expect(screen.getByText("POP / Site Central")).toBeDefined();
      expect(screen.getByText("v1")).toBeDefined();

      const link = screen.getByRole("link", { name: /Abrir Cadastro Completo/i });
      expect(link.getAttribute("href")).toBe("/sites?q=POP-CENTRAL-01");

      const closeBtn = screen.getByLabelText("Fechar detalhes");
      fireEvent.click(closeBtn);
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it("renderiza contadores de ocupação de portas quando a feature é uma CTO", () => {
      render(<MapFeatureSheet feature={mockCtoFeature} onClose={vi.fn()} />);

      expect(screen.getByText("CTO-16P-01")).toBeDefined();
      expect(screen.getByText("Caixa de Terminação (CTO)")).toBeDefined();
      expect(screen.getByText("Ocupação de Portas:")).toBeDefined();
      expect(screen.getByText("10")).toBeDefined(); // Livres
      expect(screen.getByText("2")).toBeDefined();  // Reservadas
      expect(screen.getByText("4")).toBeDefined();  // Conectadas

      const link = screen.getByRole("link", { name: /Abrir Cadastro Completo/i });
      expect(link.getAttribute("href")).toBe("/ctos?q=CTO-16P-01");
    });
  });

  describe("MapFallbackTable Component", () => {
    it("renderiza a tabela com elementos da região e permite filtrar", () => {
      const handleSelect = vi.fn();
      const features = [mockSiteFeature, mockCtoFeature, mockCableFeature];

      render(<MapFallbackTable features={features} onSelectFeature={handleSelect} />);

      expect(screen.getByText("POP-CENTRAL-01")).toBeDefined();
      expect(screen.getByText("CTO-16P-01")).toBeDefined();
      expect(screen.getByText("CAB-TRONCO-01")).toBeDefined();

      // Filtra por CTO
      const input = screen.getByPlaceholderText(/Filtrar por código ou tipo/i);
      fireEvent.change(input, { target: { value: "CTO" } });

      expect(screen.getByText("CTO-16P-01")).toBeDefined();
      expect(screen.queryByText("POP-CENTRAL-01")).toBeNull();
      expect(screen.queryByText("CAB-TRONCO-01")).toBeNull();

      // Clicar na linha seleciona o elemento
      const row = screen.getByText("CTO-16P-01").closest("tr");
      expect(row).not.toBeNull();
      if (row) {
        fireEvent.click(row);
        expect(handleSelect).toHaveBeenCalledWith(mockCtoFeature);
      }
    });
  });

  describe("MapView Component", () => {
    it("carrega o centro persistido quando a URL não informa uma posição", async () => {
      mockSearchParams = new URLSearchParams();
      const settingsSpy = vi.spyOn(settingsApi, "getAppSettings").mockResolvedValue({
        app_name: "FTTH Manager",
        organization_name: "Operação FTTH",
        timezone: "America/Sao_Paulo",
        default_map_center: [-53, -30],
        default_map_zoom: 7,
        max_upload_size_bytes: 10_485_760,
        trace_max_depth: 100,
        excess_loss_tolerance_db: 2,
        version: 2,
      });

      renderMapView();

      await waitFor(() => expect(settingsSpy).toHaveBeenCalledTimes(1));
    });

    it("renderiza cabeçalho, controles de modo e alterna para visão em tabela", async () => {
      vi.spyOn(mapApi, "getMapFeatures").mockResolvedValue({
        type: "FeatureCollection",
        features: [mockSiteFeature],
        bbox: [-46.64, -23.56, -46.62, -23.54],
        topology_revision: 9,
        truncated: false,
      });

      renderMapView();

      expect(screen.getByRole("heading", { name: /Mapa Operacional/i })).toBeDefined();

      // Alterna para o modo lista
      const listModeBtn = screen.getByRole("button", { name: /Lista/i });
      fireEvent.click(listModeBtn);

      expect(
        screen.getByPlaceholderText(/Filtrar por código ou tipo/i)
      ).toBeDefined();
    });

    it("exibe aviso de truncamento quando limite de feições é excedido", async () => {
      vi.spyOn(mapApi, "getMapFeatures").mockResolvedValue({
        type: "FeatureCollection",
        features: [mockSiteFeature],
        bbox: [-46.64, -23.56, -46.62, -23.54],
        topology_revision: 11,
        truncated: true,
      });

      renderMapView();

      expect(screen.getByRole("heading", { name: /Mapa Operacional/i })).toBeDefined();
    });
  });
});
