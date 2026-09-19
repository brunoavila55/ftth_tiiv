"use client";

import * as React from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useTheme } from "next-themes";
import { Plus, Minus, Maximize2, Locate, AlertTriangle, Fullscreen, Minimize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { MapFeature, LayerFilters, MapInteractionMode } from "../types";
import type { SnapCandidate } from "../utils/geometry";

export interface OperationalMapProps {
  features: MapFeature[];
  layers: LayerFilters;
  selectedFeatureId: string | null;
  onSelectFeature: (feature: MapFeature | null) => void;
  onViewportChange: (bounds: { west: number; south: number; east: number; north: number }, zoom: number) => void;
  initialLat?: number;
  initialLng?: number;
  initialZoom?: number;
  // Propriedades do Modo Desenho e Edição (F07)
  mode?: MapInteractionMode;
  draftCoordinates?: [number, number][];
  snapCandidate?: SnapCandidate | null;
  onMapClick?: (coords: [number, number]) => void;
  onMouseMove?: (coords: [number, number]) => void;
  onDoubleClick?: () => void;
}

// Estilo raster CARTO Voyager (padrão de alto desempenho, CDN global com CORS liberado)
export const CARTO_VOYAGER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>',
    },
  },
  layers: [
    {
      id: "carto-tiles",
      type: "raster",
      source: "carto",
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

// Estilo raster CARTO Dark Matter (modo escuro com alto contraste para cabos ópticos)
export const CARTO_DARK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>',
    },
  },
  layers: [
    {
      id: "carto-tiles",
      type: "raster",
      source: "carto",
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

function checkWebGLSupport(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext("webgl") ||
          canvas.getContext("experimental-webgl") ||
          canvas.getContext("webgl2"))
    );
  } catch {
    return false;
  }
}

export function OperationalMap({
  features,
  layers,
  selectedFeatureId,
  onSelectFeature,
  onViewportChange,
  initialLat = -23.55052,
  initialLng = -46.633308,
  initialZoom = 14,
  mode = "view",
  draftCoordinates = [],
  snapCandidate = null,
  onMapClick,
  onMouseMove,
  onDoubleClick,
}: OperationalMapProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const mapContainerRef = React.useRef<HTMLDivElement>(null);
  const mapRef = React.useRef<maplibregl.Map | null>(null);
  const [webglSupported, setWebglSupported] = React.useState<boolean>(true);
  const [locating, setLocating] = React.useState<boolean>(false);
  const [geoError, setGeoError] = React.useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = React.useState<boolean>(false);

  // 1. Verificação de suporte a WebGL
  React.useEffect(() => {
    if (!checkWebGLSupport()) {
      setWebglSupported(false);
    }
  }, []);

  // Monitora mudanças no modo de tela cheia
  React.useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
      setTimeout(() => mapRef.current?.resize(), 100);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  // ResizeObserver para redimensionar o canvas automaticamente quando o container mudar de tamanho
  React.useEffect(() => {
    if (!mapContainerRef.current) return;
    const ro = new ResizeObserver(() => {
      mapRef.current?.resize();
    });
    ro.observe(mapContainerRef.current);
    return () => ro.disconnect();
  }, []);

  // Listener para redimensionamento de janela
  React.useEffect(() => {
    const handleWindowResize = () => mapRef.current?.resize();
    window.addEventListener("resize", handleWindowResize);
    return () => window.removeEventListener("resize", handleWindowResize);
  }, []);

  // 2. Separação de geometrias em Linhas (cabos) e Pontos (estruturas/sites)
  const lineGeoJson = React.useMemo(() => {
    if (!layers.cables) {
      return { type: "FeatureCollection" as const, features: [] };
    }
    const lineFeatures = features
      .filter((f) => f.geometry.type === "LineString")
      .map((f) => ({
        type: "Feature" as const,
        id: f.id,
        geometry: {
          type: "LineString" as const,
          coordinates: f.geometry.coordinates,
        },
        properties: {
          ...f.properties,
          isSelected: f.id === selectedFeatureId,
        },
      }));
    return { type: "FeatureCollection" as const, features: lineFeatures };
  }, [features, layers.cables, selectedFeatureId]);

  const pointGeoJson = React.useMemo(() => {
    const pointFeatures = features
      .filter((f) => {
        if (f.geometry.type !== "Point") return false;
        if (f.properties.entity_type === "site" && !layers.sites) return false;
        if (f.properties.entity_type === "cto" && !layers.ctos) return false;
        if (f.properties.entity_type === "structure" && !layers.structures) return false;
        return true;
      })
      .map((f) => ({
        type: "Feature" as const,
        id: f.id,
        geometry: {
          type: "Point" as const,
          coordinates: f.geometry.coordinates,
        },
        properties: {
          ...f.properties,
          isSelected: f.id === selectedFeatureId,
        },
      }));
    return { type: "FeatureCollection" as const, features: pointFeatures };
  }, [features, layers, selectedFeatureId]);

  // GeoJSON do rascunho de desenho
  const draftLineGeoJson = React.useMemo(() => {
    if (draftCoordinates.length < 2) {
      return { type: "FeatureCollection" as const, features: [] };
    }
    return {
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          geometry: {
            type: "LineString" as const,
            coordinates: draftCoordinates,
          },
          properties: {},
        },
      ],
    };
  }, [draftCoordinates]);

  const draftPointsGeoJson = React.useMemo(() => {
    const pts = draftCoordinates.map((c, idx) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: c,
      },
      properties: { index: idx },
    }));
    return { type: "FeatureCollection" as const, features: pts };
  }, [draftCoordinates]);

  // GeoJSON do indicador de snap magnético
  const snapGeoJson = React.useMemo(() => {
    if (!snapCandidate) {
      return { type: "FeatureCollection" as const, features: [] };
    }
    return {
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          geometry: {
            type: "Point" as const,
            coordinates: snapCandidate.coordinates,
          },
          properties: { code: snapCandidate.code },
        },
      ],
    };
  }, [snapCandidate]);

  // 3. Inicialização do MapLibre
  React.useEffect(() => {
    if (!webglSupported || !mapContainerRef.current || mapRef.current) return;

    const styleUrl: string | maplibregl.StyleSpecification =
      process.env.NEXT_PUBLIC_MAP_STYLE_URL || (isDark ? CARTO_DARK_STYLE : CARTO_VOYAGER_STYLE);

    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: styleUrl,
        center: [initialLng, initialLat],
        zoom: initialZoom,
        attributionControl: false,
      });
    } catch (err) {
      console.warn("Falha ao instanciar MapLibre GL:", err);
      return;
    }

    map.addControl(
      new maplibregl.AttributionControl({
        compact: false,
      }),
      "bottom-right"
    );

    map.addControl(
      new maplibregl.ScaleControl({
        maxWidth: 120,
        unit: "metric",
      }),
      "bottom-left"
    );

    const setupSourcesAndLayers = () => {
      if (!map || map.getSource("ftth-lines-source")) return;

      try {
        // Fontes e layers da rede cadastrada
        map.addSource("ftth-lines-source", {
          type: "geojson",
          data: lineGeoJson,
        });

        map.addLayer({
          id: "ftth-cables-layer",
          type: "line",
          source: "ftth-lines-source",
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
          paint: {
            "line-color": [
              "case",
              ["boolean", ["get", "isSelected"], false],
              "#f43f5e",
              "#4f46e5",
            ],
            "line-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              10,
              2,
              16,
              4.5,
            ],
          },
        });

        map.addSource("ftth-points-source", {
          type: "geojson",
          data: pointGeoJson,
        });

        map.addLayer({
          id: "ftth-points-layer",
          type: "circle",
          source: "ftth-points-source",
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              10,
              4,
              16,
              7.5,
            ],
            "circle-color": [
              "case",
              ["boolean", ["get", "isSelected"], false],
              "#f43f5e",
              [
                "match",
                ["get", "entity_type"],
                "site",
                "#0284c7",
                "cto",
                "#f59e0b",
                "ceo",
                "#8b5cf6",
                "#64748b",
              ],
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });

        // Fontes e layers para rascunho de desenho (F07)
        map.addSource("ftth-draft-line-source", {
          type: "geojson",
          data: draftLineGeoJson,
        });

        map.addLayer({
          id: "ftth-draft-line-layer",
          type: "line",
          source: "ftth-draft-line-source",
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
          paint: {
            "line-color": "#f43f5e",
            "line-width": 3,
            "line-dasharray": [2, 2],
          },
        });

        map.addSource("ftth-draft-points-source", {
          type: "geojson",
          data: draftPointsGeoJson,
        });

        map.addLayer({
          id: "ftth-draft-points-layer",
          type: "circle",
          source: "ftth-draft-points-source",
          paint: {
            "circle-radius": 6,
            "circle-color": "#f43f5e",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });

        // Fonte e layer para indicador de snap magnético
        map.addSource("ftth-snap-source", {
          type: "geojson",
          data: snapGeoJson,
        });

        map.addLayer({
          id: "ftth-snap-layer",
          type: "circle",
          source: "ftth-snap-source",
          paint: {
            "circle-radius": 12,
            "circle-color": "transparent",
            "circle-stroke-width": 2.5,
            "circle-stroke-color": "#0ea5e9",
          },
        });
      } catch (err) {
        console.warn("Aviso ao carregar camadas no mapa:", err);
      }

      // Dispara primeira sincronização de viewport
      try {
        const bounds = map.getBounds();
        onViewportChange(
          {
            west: bounds.getWest(),
            south: bounds.getSouth(),
            east: bounds.getEast(),
            north: bounds.getNorth(),
          },
          Math.round(map.getZoom())
        );
      } catch {}

      // Garante que o canvas ocupe as dimensões completas do elemento
      map.resize();
    };

    // Dispara tanto em style.load quanto em load para garantir renderização imediata
    map.once("style.load", setupSourcesAndLayers);
    map.once("load", setupSourcesAndLayers);

    map.on("error", (e) => {
      const err = e as { error?: { message?: string }; status?: number };
      if (err?.error?.message?.includes("tile") || err?.status === 404 || err?.status === 403) {
        return;
      }
      console.warn("Aviso interno do mapa:", e);
    });

    mapRef.current = map;

    // Timeout de segurança para forçar resize caso o layout flex termine de calcular
    const timer = setTimeout(() => {
      map.resize();
    }, 200);

    return () => {
      clearTimeout(timer);
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [webglSupported]);

  // Atualização das fontes de desenho e rede
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    (map.getSource("ftth-lines-source") as maplibregl.GeoJSONSource)?.setData(lineGeoJson);
    (map.getSource("ftth-points-source") as maplibregl.GeoJSONSource)?.setData(pointGeoJson);
    (map.getSource("ftth-draft-line-source") as maplibregl.GeoJSONSource)?.setData(draftLineGeoJson);
    (map.getSource("ftth-draft-points-source") as maplibregl.GeoJSONSource)?.setData(draftPointsGeoJson);
    (map.getSource("ftth-snap-source") as maplibregl.GeoJSONSource)?.setData(snapGeoJson);
  }, [lineGeoJson, pointGeoJson, draftLineGeoJson, draftPointsGeoJson, snapGeoJson]);

  // Eventos de clique, movimento e interação vinculados dinamicamente ao modo ativo
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Atualiza cursor conforme o modo
    const canvas = map.getCanvas();
    if (mode === "draw_point" || mode === "draw_cable") {
      canvas.style.cursor = "crosshair";
    } else if (mode === "edit_geometry") {
      canvas.style.cursor = "grab";
    } else {
      canvas.style.cursor = "";
    }

    const handleMapClick = (e: maplibregl.MapMouseEvent) => {
      if (mode !== "view") {
        onMapClick?.([e.lngLat.lng, e.lngLat.lat]);
      } else {
        const pointFeatures = map.queryRenderedFeatures(e.point, {
          layers: ["ftth-points-layer", "ftth-cables-layer"],
        });
        if (pointFeatures.length > 0) {
          const clickedId = pointFeatures[0].id;
          const found = features.find((f) => f.id === clickedId);
          if (found) onSelectFeature(found);
        } else {
          onSelectFeature(null);
        }
      }
    };

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      if (mode !== "view") {
        onMouseMove?.([e.lngLat.lng, e.lngLat.lat]);
      } else {
        const pointFeatures = map.queryRenderedFeatures(e.point, {
          layers: ["ftth-points-layer", "ftth-cables-layer"],
        });
        canvas.style.cursor = pointFeatures.length > 0 ? "pointer" : "";
      }
    };

    const handleDblClick = (e: maplibregl.MapMouseEvent) => {
      if (mode === "draw_cable") {
        e.preventDefault();
        onDoubleClick?.();
      }
    };

    const handleMoveEnd = () => {
      const bounds = map.getBounds();
      onViewportChange(
        {
          west: bounds.getWest(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          north: bounds.getNorth(),
        },
        Math.round(map.getZoom())
      );
    };

    map.on("click", handleMapClick);
    map.on("mousemove", handleMouseMove);
    map.on("dblclick", handleDblClick);
    map.on("moveend", handleMoveEnd);

    return () => {
      map.off("click", handleMapClick);
      map.off("mousemove", handleMouseMove);
      map.off("dblclick", handleDblClick);
      map.off("moveend", handleMoveEnd);
    };
  }, [mode, features, onMapClick, onMouseMove, onDoubleClick, onSelectFeature, onViewportChange]);

  // Controles de navegação customizados
  const handleZoomIn = () => mapRef.current?.zoomIn();
  const handleZoomOut = () => mapRef.current?.zoomOut();

  const handleFitBounds = () => {
    const map = mapRef.current;
    if (!map || features.length === 0) return;

    const bounds = new maplibregl.LngLatBounds();
    for (const f of features) {
      if (f.geometry.type === "Point") {
        bounds.extend(f.geometry.coordinates);
      } else if (f.geometry.type === "LineString") {
        for (const coord of f.geometry.coordinates) {
          bounds.extend(coord);
        }
      }
    }

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 60, maxZoom: 17 });
    }
  };

  const handleLocateMe = () => {
    if (!navigator.geolocation) {
      setGeoError("Geolocalização não suportada pelo navegador.");
      return;
    }

    setLocating(true);
    setGeoError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        mapRef.current?.flyTo({
          center: [pos.coords.longitude, pos.coords.latitude],
          zoom: 16,
        });
      },
      (err) => {
        setLocating(false);
        if (err.code === err.PERMISSION_DENIED) {
          setGeoError("Permissão de localização recusada pelo usuário.");
        } else {
          setGeoError("Não foi possível obter a sua localização atual.");
        }
        setTimeout(() => setGeoError(null), 4000);
      },
      { timeout: 8000 }
    );
  };

  if (!webglSupported) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center rounded-xl border border-destructive/20 bg-destructive/5 my-6">
        <AlertTriangle className="h-10 w-10 text-destructive mb-3" />
        <h3 className="font-bold text-base text-foreground">
          WebGL Não Suportado ou Desativado
        </h3>
        <p className="text-xs text-muted-foreground mt-1 max-w-md">
          O renderizador geográfico MapLibre requer aceleração WebGL ativa no seu navegador. Você pode habilitar o WebGL nas configurações de vídeo ou utilizar a alternativa em lista acima.
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full min-h-[450px] overflow-hidden bg-card">
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Controles Flutuantes de Mapa */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-1.5 shadow-md">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleZoomIn}
          className="h-8 w-8 p-0 rounded-md bg-card/90 backdrop-blur-sm border border-border hover:bg-card"
          aria-label="Aproximar zoom"
          title="Aproximar zoom"
        >
          <Plus className="h-4 w-4" />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleZoomOut}
          className="h-8 w-8 p-0 rounded-md bg-card/90 backdrop-blur-sm border border-border hover:bg-card"
          aria-label="Afastar zoom"
          title="Afastar zoom"
        >
          <Minus className="h-4 w-4" />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleFitBounds}
          className="h-8 w-8 p-0 rounded-md bg-card/90 backdrop-blur-sm border border-border hover:bg-card mt-1"
          aria-label="Enquadrar todos os elementos da rede"
          title="Enquadrar todos os elementos"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleLocateMe}
          disabled={locating}
          className="h-8 w-8 p-0 rounded-md bg-card/90 backdrop-blur-sm border border-border hover:bg-card"
          aria-label="Centralizar na minha localização"
          title="Minha Localização"
        >
          <Locate className={`h-3.5 w-3.5 ${locating ? "animate-pulse text-primary" : ""}`} />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            if (!document.fullscreenElement) {
              mapContainerRef.current?.parentElement?.requestFullscreen().catch(() => {});
            } else {
              document.exitFullscreen().catch(() => {});
            }
          }}
          className="h-8 w-8 p-0 rounded-md bg-card/90 backdrop-blur-sm border border-border hover:bg-card mt-1"
          aria-label={isFullscreen ? "Sair da tela cheia" : "Modo tela cheia"}
          title={isFullscreen ? "Sair da tela cheia" : "Tela cheia"}
        >
          {isFullscreen ? (
            <Minimize2 className="h-3.5 w-3.5" />
          ) : (
            <Fullscreen className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>

      {/* Alerta de erro de geolocalização temporário */}
      {geoError && (
        <div className="absolute top-4 left-16 z-20 rounded-md border border-destructive/30 bg-destructive/90 px-3 py-1.5 text-xs text-white shadow-lg backdrop-blur-sm animate-in fade-in">
          {geoError}
        </div>
      )}
    </div>
  );
}
