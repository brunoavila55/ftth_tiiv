import * as React from "react";
import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mapMocks = vi.hoisted(() => {
  class HoistedMockMap {
    static latest: HoistedMockMap | null = null;

    readonly options: { style: string };
    readonly setStyle = vi.fn((style: string) => {
      this.options.style = style;
      this.sources.clear();
    });
    readonly sources = new Map<string, { setData: ReturnType<typeof vi.fn> }>();
    readonly layers: Array<Record<string, unknown>> = [];
    readonly handlers = new Map<string, Set<(...args: unknown[]) => void>>();
    readonly canvas = { style: { cursor: "" } };
    readonly dragPan = { disable: vi.fn(), enable: vi.fn() };
    renderedFeatures: Array<{ id?: string | number; properties?: Record<string, unknown> }> = [];
    readonly queryRenderedFeatures = vi.fn(() => this.renderedFeatures);

    constructor(options: { style: string }) {
      this.options = { ...options };
      HoistedMockMap.latest = this;
      state.instances.push(this);
    }

    addControl() {}
    addLayer(layer: Record<string, unknown>) { this.layers.push(layer); }
    resize() {}
    remove() {}
    zoomIn() {}
    zoomOut() {}
    fitBounds() {}
    flyTo() {}
    isStyleLoaded() { return true; }
    getCanvas() { return this.canvas; }
    getZoom() { return 7; }
    getBounds() {
      return {
        getWest: () => -54,
        getSouth: () => -31,
        getEast: () => -52,
        getNorth: () => -29,
      };
    }
    getSource(id: string) { return this.sources.get(id); }
    addSource(id: string) { this.sources.set(id, { setData: vi.fn() }); }
    on(event: string, callback: (...args: unknown[]) => void) {
      const callbacks = this.handlers.get(event) ?? new Set();
      callbacks.add(callback);
      this.handlers.set(event, callbacks);
    }
    once(event: string, callback: (...args: unknown[]) => void) {
      const onceCallback = (...args: unknown[]) => {
        this.off(event, onceCallback);
        callback(...args);
      };
      this.on(event, onceCallback);
    }
    off(event: string, callback: (...args: unknown[]) => void) {
      this.handlers.get(event)?.delete(callback);
    }
    emit(event: string, payload?: unknown) {
      for (const callback of [...(this.handlers.get(event) ?? [])]) callback(payload);
    }
  }

  const state = {
    resolvedTheme: "light",
    instances: [] as HoistedMockMap[],
    MockMap: HoistedMockMap,
  };
  return state;
});

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: mapMocks.resolvedTheme }),
}));

vi.mock("maplibre-gl", () => ({
  Map: mapMocks.MockMap,
  AttributionControl: class {},
  ScaleControl: class {},
  LngLatBounds: class {
    extend() { return this; }
    isEmpty() { return false; }
  },
  setWorkerUrl: vi.fn(),
}));

import {
  MAP_POINT_COLORS,
  MAP_STYLE_DARK_URL,
  MAP_STYLE_LIGHT_URL,
  OperationalMap,
} from "@/features/map/components/operational-map";

describe("Tema do mapa operacional", () => {
  beforeEach(() => {
    mapMocks.resolvedTheme = "light";
    mapMocks.instances.length = 0;
    mapMocks.MockMap.latest = null;
    Object.defineProperty(window, "WebGLRenderingContext", {
      configurable: true,
      value: function WebGLRenderingContext() {},
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as never);
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      }
    );
  });

  it("usa cores distintas para CTO e CEO", () => {
    expect(MAP_POINT_COLORS.cto).toBe("#f59e0b");
    expect(MAP_POINT_COLORS.ceo).toBe("#8b5cf6");
    expect(MAP_POINT_COLORS.cto).not.toBe(MAP_POINT_COLORS.ceo);
  });

  it("mantém o zoom no topo da expressão de raio aceita pelo MapLibre", () => {
    render(
      <OperationalMap
        features={[]}
        layers={{ sites: true, structures: true, ctos: true, cables: true }}
        selectedFeatureId={null}
        onSelectFeature={vi.fn()}
        onViewportChange={vi.fn()}
      />
    );
    const map = mapMocks.MockMap.latest;
    act(() => map?.emit("style.load"));

    const pointLayer = map?.layers.find((layer) => layer.id === "ftth-points-layer");
    const paint = pointLayer?.paint as Record<string, unknown> | undefined;
    const radius = paint?.["circle-radius"] as unknown[] | undefined;
    expect(radius?.[0]).toBe("interpolate");
    expect(radius?.[2]).toEqual(["zoom"]);
  });

  it("troca o style sem recriar o mapa e restaura as camadas FTTH", () => {
    const props = {
      features: [],
      layers: { sites: true, structures: true, ctos: true, cables: true },
      selectedFeatureId: null,
      onSelectFeature: vi.fn(),
      onViewportChange: vi.fn(),
    };
    const view = render(<OperationalMap {...props} />);
    const map = mapMocks.MockMap.latest;

    expect(map).not.toBeNull();
    expect(map?.options.style).toBe(MAP_STYLE_LIGHT_URL);

    act(() => map?.emit("style.load"));
    expect(map?.getSource("ftth-points-source")).toBeDefined();

    mapMocks.resolvedTheme = "dark";
    view.rerender(<OperationalMap {...props} />);

    expect(mapMocks.instances).toHaveLength(1);
    expect(map?.setStyle).toHaveBeenCalledWith(MAP_STYLE_DARK_URL);
    expect(map?.getSource("ftth-points-source")).toBeUndefined();

    act(() => map?.emit("style.load"));
    expect(map?.getSource("ftth-points-source")).toBeDefined();
    expect(map?.getSource("ftth-lines-source")).toBeDefined();
  });

  it("seleciona CTO, CEO e cabo pelo identificador da entidade renderizada", () => {
    const features = [
      {
        id: "structure:cto-1",
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [-51.2, -30.1] as [number, number] },
        properties: {
          entity_id: "cto-1",
          entity_type: "structure",
          code: "CTO-01",
          status: "installed",
          version: 1,
          extra: { kind: "cto" },
        },
      },
      {
        id: "structure:ceo-1",
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [-51.21, -30.11] as [number, number] },
        properties: {
          entity_id: "ceo-1",
          entity_type: "structure",
          code: "CEO-01",
          status: "installed",
          version: 1,
          extra: { kind: "ceo" },
        },
      },
      {
        id: "cable_segment:segment-1",
        type: "Feature" as const,
        geometry: {
          type: "LineString" as const,
          coordinates: [[-51.2, -30.1], [-51.21, -30.11]] as [number, number][],
        },
        properties: {
          entity_id: "segment-1",
          entity_type: "cable_segment",
          code: "CAB-01",
          status: "installed",
          version: 1,
          extra: { cable_id: "cable-1" },
        },
      },
    ];
    const onSelectFeature = vi.fn();
    render(
      <OperationalMap
        features={features}
        layers={{ sites: true, structures: true, ctos: true, cables: true }}
        selectedFeatureId={null}
        onSelectFeature={onSelectFeature}
        onViewportChange={vi.fn()}
      />
    );
    const map = mapMocks.MockMap.latest;
    act(() => map?.emit("style.load"));

    for (const feature of features) {
      if (!map) throw new Error("Mapa não inicializado");
      map.renderedFeatures = [{ properties: { entity_id: feature.properties.entity_id } }];
      act(() =>
        map.emit("click", {
          point: { x: 10, y: 10 },
          lngLat: { lng: -51.2, lat: -30.1 },
        })
      );
      expect(onSelectFeature).toHaveBeenLastCalledWith(feature);
    }

    expect(map?.queryRenderedFeatures).toHaveBeenCalledWith(
      { x: 10, y: 10 },
      { layers: ["ftth-points-layer", "ftth-cables-layer", "ftth-cables-hit-layer"] }
    );
  });

  it("arrasta apenas vértices intermediários durante a edição do cabo", () => {
    const onVertexMove = vi.fn();
    const onVertexMoveEnd = vi.fn();
    const onMapClick = vi.fn();
    render(
      <OperationalMap
        features={[]}
        layers={{ sites: true, structures: true, ctos: true, cables: true }}
        selectedFeatureId={null}
        onSelectFeature={vi.fn()}
        onViewportChange={vi.fn()}
        mode="edit_geometry"
        draftCoordinates={[
          [-51.2, -30.1],
          [-51.195, -30.105],
          [-51.19, -30.11],
        ]}
        onMapClick={onMapClick}
        onVertexMove={onVertexMove}
        onVertexMoveEnd={onVertexMoveEnd}
      />
    );
    const map = mapMocks.MockMap.latest;
    act(() => map?.emit("style.load"));
    if (!map) throw new Error("Mapa não inicializado");

    map.renderedFeatures = [{ properties: { index: 1 } }];
    const preventDefault = vi.fn();
    act(() =>
      map.emit("mousedown", {
        point: { x: 10, y: 10 },
        lngLat: { lng: -51.195, lat: -30.105 },
        preventDefault,
      })
    );
    act(() =>
      map.emit("mousemove", {
        point: { x: 12, y: 12 },
        lngLat: { lng: -51.194, lat: -30.104 },
      })
    );
    act(() => map.emit("mouseup", {}));

    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(map.dragPan.disable).toHaveBeenCalledTimes(1);
    expect(map.dragPan.enable).toHaveBeenCalledTimes(1);
    expect(onVertexMove).toHaveBeenCalledWith(1, [-51.194, -30.104]);
    expect(onVertexMoveEnd).toHaveBeenCalledTimes(1);

    // O click emitido pelo navegador ao final do arraste é descartado.
    act(() =>
      map.emit("click", {
        point: { x: 12, y: 12 },
        lngLat: { lng: -51.194, lat: -30.104 },
      })
    );
    expect(onMapClick).not.toHaveBeenCalled();
  });
});
