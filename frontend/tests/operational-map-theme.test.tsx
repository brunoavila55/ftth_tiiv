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
    readonly handlers = new Map<string, Set<(...args: unknown[]) => void>>();
    readonly canvas = { style: { cursor: "" } };

    constructor(options: { style: string }) {
      this.options = { ...options };
      HoistedMockMap.latest = this;
      state.instances.push(this);
    }

    addControl() {}
    addLayer() {}
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
    queryRenderedFeatures() { return []; }
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
    emit(event: string) {
      for (const callback of [...(this.handlers.get(event) ?? [])]) callback();
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
});
