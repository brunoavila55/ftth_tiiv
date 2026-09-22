"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Map as MapIcon,
  Table as TableIcon,
  AlertTriangle,
  Loader2,
  RefreshCw,
  GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorState } from "@/components/ui/state-displays";
import { PermissionGate } from "@/components/auth/permission-gate";
import { getMapFeatures, formatBBox } from "../api";
import { getAppSettings } from "@/features/settings/api";
import { DEFAULT_MAP_VIEW } from "../constants";
import { MapLegend } from "./map-legend";
import { MapFeatureSheet } from "./map-feature-sheet";
import { MapFallbackTable } from "./map-fallback-table";
import { DrawingToolbar } from "./drawing-toolbar";
import { DrawingModal } from "./drawing-modal";
import {
  findNearestSnapCandidate,
  calculateLineLength,
  insertVertexAtNearestSegment,
  appendDistinctCoordinate,
  type SnapCandidate,
} from "../utils/geometry";
import { deleteCableSegment, updateCableSegment } from "@/features/cables/api";
import { deleteSite, deleteStructure } from "@/features/inventory/api";
import { ApiError } from "@/lib/api/types";
import type {
  MapFeature,
  MapFeatureCollection,
  LayerFilters,
  MapInteractionMode,
  PointKind,
  DrawingDraft,
} from "../types";

// Importação dinâmica do mapa operacional com SSR desativado
const OperationalMap = dynamic(
  () => import("./operational-map").then((mod) => mod.OperationalMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full min-h-[400px] flex-1 items-center justify-center bg-card">
        <LoadingState
          message="Inicializando motor gráfico de mapa..."
          description="Carregando biblioteca MapLibre GL e aceleração por WebGL."
        />
      </div>
    ),
  }
);

export function MapView() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const urlLat = searchParams.get("lat");
  const urlLng = searchParams.get("lng");
  const urlZoom = searchParams.get("zoom");
  const parsedUrlLat = urlLat === null ? null : Number(urlLat);
  const parsedUrlLng = urlLng === null ? null : Number(urlLng);
  const parsedUrlZoom = urlZoom === null ? null : Number(urlZoom);
  const validUrlLat =
    parsedUrlLat !== null &&
    Number.isFinite(parsedUrlLat) &&
    parsedUrlLat >= -90 &&
    parsedUrlLat <= 90;
  const validUrlLng =
    parsedUrlLng !== null &&
    Number.isFinite(parsedUrlLng) &&
    parsedUrlLng >= -180 &&
    parsedUrlLng <= 180;
  const validUrlZoom =
    parsedUrlZoom !== null &&
    Number.isFinite(parsedUrlZoom) &&
    parsedUrlZoom >= 1 &&
    parsedUrlZoom <= 22;
  const needsAppSettings = !validUrlLat || !validUrlLng || !validUrlZoom;
  const settingsQuery = useQuery({
    queryKey: ["app-settings"],
    queryFn: getAppSettings,
    enabled: needsAppSettings,
  });

  // A URL tem prioridade; na navegação comum, usa a preferência persistida da instalação.
  const initialLat = validUrlLat
    ? parsedUrlLat
    : (settingsQuery.data?.default_map_center[1] ?? DEFAULT_MAP_VIEW.latitude);
  const initialLng = validUrlLng
    ? parsedUrlLng
    : (settingsQuery.data?.default_map_center[0] ?? DEFAULT_MAP_VIEW.longitude);
  const initialZoom = validUrlZoom
    ? parsedUrlZoom
    : (settingsQuery.data?.default_map_zoom ?? DEFAULT_MAP_VIEW.zoom);
  const initialViewReady = !needsAppSettings || !settingsQuery.isPending;
  const initialSelectedId = searchParams.get("selected");

  // Estados locais
  const [viewMode, setViewMode] = React.useState<"map" | "table">("map");
  const [selectedFeature, setSelectedFeature] = React.useState<MapFeature | null>(null);
  const [isLoading, setIsLoading] = React.useState<boolean>(false);
  const [error, setError] = React.useState<Error | null>(null);
  const [data, setData] = React.useState<MapFeatureCollection | null>(null);

  // Estados de Desenho Geográfico (F07)
  const [interactionMode, setInteractionMode] = React.useState<MapInteractionMode>("view");
  const [pointKind, setPointKind] = React.useState<PointKind>("cto");
  const [draftCoordinates, setDraftCoordinates] = React.useState<[number, number][]>([]);
  const [history, setHistory] = React.useState<[number, number][][]>([]);
  const [historyIndex, setHistoryIndex] = React.useState<number>(-1);
  const [snapCandidate, setSnapCandidate] = React.useState<SnapCandidate | null>(null);
  const [modalOpen, setModalOpen] = React.useState<boolean>(false);
  const [activeDraft, setActiveDraft] = React.useState<DrawingDraft | null>(null);
  const [interactionError, setInteractionError] = React.useState<string | null>(null);
  const [isSavingGeometry, setIsSavingGeometry] = React.useState(false);
  const [isDeletingFeature, setIsDeletingFeature] = React.useState(false);
  const [draftCableId, setDraftCableId] = React.useState<string | null>(null);
  const [presetOrigin, setPresetOrigin] = React.useState<{
    id: string;
    code: string;
    coordinates: [number, number];
  } | null>(null);

  // Filtros de camadas ativas
  const [layers, setLayers] = React.useState<LayerFilters>({
    sites: true,
    structures: true,
    ctos: true,
    cables: true,
  });

  const abortControllerRef = React.useRef<AbortController | null>(null);
  const debounceTimerRef = React.useRef<NodeJS.Timeout | null>(null);
  const currentBBoxRef = React.useRef<string | null>(null);
  const currentZoomRef = React.useRef<number>(initialZoom);

  const toggleLayer = (layerKey: keyof LayerFilters) => {
    setLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  // Função central de carregamento de dados geográficos com debounce e cancelamento
  const loadFeatures = React.useCallback(
    (bboxStr: string, zoom: number) => {
      currentBBoxRef.current = bboxStr;
      currentZoomRef.current = zoom;

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(async () => {
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
        }

        const controller = new AbortController();
        abortControllerRef.current = controller;

        setIsLoading(true);
        setError(null);

        try {
          const result = await getMapFeatures(
            {
              bbox: bboxStr,
              layers: "sites,structures,cables",
              zoom,
            },
            controller.signal
          );

          setData(result);
        } catch (err: unknown) {
          if ((err as Error)?.name !== "AbortError") {
            setError(err instanceof Error ? err : new Error("Falha ao carregar mapa"));
          }
        } finally {
          setIsLoading(false);
        }
      }, 350);
    },
    []
  );

  // Dispara consulta inicial imediata para não depender exclusivamente de eventos do MapLibre
  React.useEffect(() => {
    const latSpan = 0.05;
    const lngSpan = 0.07;
    const defaultBBox = `${(initialLng - lngSpan).toFixed(6)},${(initialLat - latSpan).toFixed(6)},${(initialLng + lngSpan).toFixed(6)},${(initialLat + latSpan).toFixed(6)}`;
    loadFeatures(defaultBBox, initialZoom);
  }, [initialLat, initialLng, initialZoom, loadFeatures]);

  // Callback acionado pelo moveend do mapa
  const handleViewportChange = React.useCallback(
    (
      bounds: { west: number; south: number; east: number; north: number },
      zoom: number
    ) => {
      const bboxStr = formatBBox(bounds);
      loadFeatures(bboxStr, zoom);

      const centerLat = ((bounds.south + bounds.north) / 2).toFixed(5);
      const centerLng = ((bounds.west + bounds.east) / 2).toFixed(5);
      const newParams = new URLSearchParams(searchParams.toString());
      newParams.set("lat", centerLat);
      newParams.set("lng", centerLng);
      newParams.set("zoom", String(zoom));

      router.replace(`?${newParams.toString()}`, { scroll: false });
    },
    [loadFeatures, router, searchParams]
  );

  // Sincroniza feature selecionada com URL
  const handleSelectFeature = React.useCallback(
    (feature: MapFeature | null) => {
      if (interactionMode !== "view") return; // Ignora seleção em modo de desenho

      setSelectedFeature(feature);
      const newParams = new URLSearchParams(searchParams.toString());
      if (feature) {
        newParams.set("selected", feature.id);
      } else {
        newParams.delete("selected");
      }
      router.replace(`?${newParams.toString()}`, { scroll: false });
    },
    [interactionMode, router, searchParams]
  );

  // Lista de pontos cadastrados para verificação de snap magnético
  const pointCandidates = React.useMemo(() => {
    if (!data) return [];
    return data.features
      .filter(
        (f) => f.geometry.type === "Point" && f.properties.entity_type === "structure"
      )
      .map((f) => ({
        id: f.properties.entity_id || f.id,
        code: f.properties.code,
        entity_type: f.properties.entity_type,
        coordinates: f.geometry.coordinates as [number, number],
      }));
  }, [data]);

  // Manipulação de modos de desenho
  const handleSetMode = (mode: MapInteractionMode, kind?: PointKind) => {
    if (mode === "edit_geometry") {
      if (
        !selectedFeature ||
        selectedFeature.geometry.type !== "LineString" ||
        selectedFeature.properties.entity_type !== "cable_segment"
      ) {
        setInteractionError("Selecione um trecho de cabo no mapa antes de usar a edição.");
        return;
      }

      const coordinates = selectedFeature.geometry.coordinates.map(
        (coordinate) => [...coordinate] as [number, number]
      );
      // Um segmento reto possui apenas extremidades protegidas; cria um ponto central editável.
      if (coordinates.length === 2) {
        coordinates.splice(1, 0, [
          (coordinates[0][0] + coordinates[1][0]) / 2,
          (coordinates[0][1] + coordinates[1][1]) / 2,
        ]);
      }

      setInteractionError(null);
      setInteractionMode(mode);
      setDraftCoordinates(coordinates);
      setHistory([coordinates]);
      setHistoryIndex(0);
      setSnapCandidate(null);
      setActiveDraft(null);
      setModalOpen(false);
      return;
    }

    setInteractionError(null);
    setDraftCableId(null);
    setPresetOrigin(null);
    setInteractionMode(mode);
    if (kind) setPointKind(kind);
    setDraftCoordinates([]);
    setHistory([]);
    setHistoryIndex(-1);
    setSnapCandidate(null);
    setSelectedFeature(null);
    setActiveDraft(null);
    setModalOpen(false);
  };

  // Undo / Redo no histórico de vértices
  const pushHistory = (coords: [number, number][]) => {
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(coords);
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    setDraftCoordinates(coords);
  };

  const handleUndo = React.useCallback(() => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      setHistoryIndex(newIndex);
      setDraftCoordinates(history[newIndex]);
    } else if (historyIndex === 0 && interactionMode !== "edit_geometry") {
      setHistoryIndex(-1);
      setDraftCoordinates([]);
    }
  }, [history, historyIndex, interactionMode]);

  const handleRedo = React.useCallback(() => {
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      setHistoryIndex(newIndex);
      setDraftCoordinates(history[newIndex]);
    }
  }, [history, historyIndex]);

  const handleCancelDrawing = React.useCallback(() => {
    setInteractionMode("view");
    setDraftCoordinates([]);
    setHistory([]);
    setHistoryIndex(-1);
    setSnapCandidate(null);
    setActiveDraft(null);
    setModalOpen(false);
    setInteractionError(null);
    setDraftCableId(null);
    setPresetOrigin(null);
  }, []);

  // Finaliza desenho e abre modal de revisão técnica
  const handleFinishDrawing = React.useCallback(async () => {
    if (
      interactionMode === "edit_geometry" &&
      selectedFeature?.geometry.type === "LineString"
    ) {
      setIsSavingGeometry(true);
      setInteractionError(null);
      try {
        const updated = await updateCableSegment(
          selectedFeature.properties.entity_id,
          {
            geometry: {
              type: "LineString",
              coordinates: draftCoordinates,
            },
          },
          selectedFeature.properties.version
        );
        setSelectedFeature({
          ...selectedFeature,
          geometry: updated.geometry,
          properties: {
            ...selectedFeature.properties,
            version: updated.version,
          },
        });
        setInteractionMode("view");
        setDraftCoordinates([]);
        setHistory([]);
        setHistoryIndex(-1);
        if (currentBBoxRef.current) {
          loadFeatures(currentBBoxRef.current, currentZoomRef.current);
        }
      } catch (err: unknown) {
        setInteractionError(
          err instanceof Error ? err.message : "Não foi possível salvar a geometria do cabo."
        );
      } finally {
        setIsSavingGeometry(false);
      }
      return;
    }

    if (interactionMode === "draw_point" && draftCoordinates.length > 0) {
      setActiveDraft({
        mode: "draw_point",
        pointKind,
        coordinates: draftCoordinates,
      });
      setModalOpen(true);
    } else if (interactionMode === "draw_cable" && draftCoordinates.length >= 2) {
      // Identifica estruturas de origem e destino se houve snap nas extremidades
      const firstCoord = draftCoordinates[0];
      const lastCoord = draftCoordinates[draftCoordinates.length - 1];

      const snapOrigin =
        presetOrigin ?? findNearestSnapCandidate(firstCoord, pointCandidates, 15);
      const snapDest = findNearestSnapCandidate(lastCoord, pointCandidates, 15);

      setActiveDraft({
        mode: "draw_cable",
        coordinates: draftCoordinates,
        originStructureId: snapOrigin?.id ?? null,
        originStructureCode: snapOrigin?.code ?? null,
        destinationStructureId: snapDest?.id ?? null,
        destinationStructureCode: snapDest?.code ?? null,
        cableId: draftCableId,
      });
      setModalOpen(true);
    }
  }, [
    interactionMode,
    selectedFeature,
    draftCoordinates,
    pointKind,
    pointCandidates,
    draftCableId,
    presetOrigin,
    loadFeatures,
  ]);

  // Clique no mapa durante desenho
  const handleMapClick = (coords: [number, number]) => {
    // Se o snapCandidate estiver ativo, utiliza a coordenada exata da estrutura snapada
    const effectiveCoord = snapCandidate ? snapCandidate.coordinates : coords;

    if (interactionMode === "draw_point") {
      setDraftCoordinates([effectiveCoord]);
      setActiveDraft({
        mode: "draw_point",
        pointKind,
        coordinates: [effectiveCoord],
      });
      setModalOpen(true);
    } else if (interactionMode === "draw_cable") {
      const newCoords = appendDistinctCoordinate(draftCoordinates, effectiveCoord);
      if (newCoords !== draftCoordinates) pushHistory(newCoords);
    } else if (interactionMode === "edit_geometry") {
      pushHistory(insertVertexAtNearestSegment(draftCoordinates, coords));
    }
  };

  const beginCableDrawing = (
    origin: {
      id: string;
      code: string;
      coordinates: [number, number];
    },
    cableId: string | null
  ) => {
    handleSelectFeature(null);
    setInteractionError(null);
    setInteractionMode("draw_cable");
    setDraftCableId(cableId);
    setPresetOrigin(origin);
    setDraftCoordinates([origin.coordinates]);
    setHistory([[origin.coordinates]]);
    setHistoryIndex(0);
    setSnapCandidate(null);
    setActiveDraft(null);
    setModalOpen(false);
  };

  const handleStartCable = (feature: MapFeature) => {
    if (feature.geometry.type !== "Point" || feature.properties.entity_type !== "structure") {
      setInteractionError("O cabo precisa iniciar em uma CTO, CEO, poste ou estrutura física.");
      return;
    }
    beginCableDrawing(
      {
        id: feature.properties.entity_id,
        code: feature.properties.code,
        coordinates: feature.geometry.coordinates,
      },
      null
    );
  };

  const handleContinueCable = (
    feature: MapFeature,
    endpoint: "origin" | "destination"
  ) => {
    if (feature.geometry.type !== "LineString") return;
    const extra = feature.properties.extra ?? {};
    const structureId = extra[`${endpoint}_structure_id`];
    const cableId = extra.cable_id;
    const structureCode = extra[`${endpoint}_code`];
    const coordinate =
      endpoint === "origin"
        ? feature.geometry.coordinates[0]
        : feature.geometry.coordinates.at(-1);

    if (
      typeof structureId !== "string" ||
      typeof cableId !== "string" ||
      !coordinate
    ) {
      setInteractionError("Não foi possível identificar a extremidade deste trecho. Recarregue o mapa.");
      return;
    }

    beginCableDrawing(
      {
        id: structureId,
        code: typeof structureCode === "string" ? structureCode : feature.properties.code,
        coordinates: coordinate,
      },
      cableId
    );
  };

  const handleDeleteFeature = async (feature: MapFeature) => {
    const extra = feature.properties.extra ?? {};
    const kind =
      feature.properties.entity_type === "structure" && typeof extra.kind === "string"
        ? extra.kind.toUpperCase()
        : feature.properties.entity_type === "site"
          ? "POP"
          : "trecho de cabo";
    if (
      !window.confirm(
        `Excluir ${kind} ${feature.properties.code}? Esta operação respeitará os vínculos existentes da rede.`
      )
    ) {
      return;
    }

    setIsDeletingFeature(true);
    setInteractionError(null);
    try {
      if (feature.properties.entity_type === "site") {
        await deleteSite(feature.properties.entity_id, feature.properties.version);
      } else if (feature.properties.entity_type === "structure") {
        await deleteStructure(feature.properties.entity_id, feature.properties.version);
      } else if (feature.properties.entity_type === "cable_segment") {
        await deleteCableSegment(feature.properties.entity_id, feature.properties.version);
      } else {
        throw new Error("Este tipo de elemento não pode ser excluído pelo mapa.");
      }

      setData((current) =>
        current
          ? { ...current, features: current.features.filter((item) => item.id !== feature.id) }
          : current
      );
      handleSelectFeature(null);
      if (currentBBoxRef.current) {
        loadFeatures(currentBBoxRef.current, currentZoomRef.current);
      }
    } catch (err: unknown) {
      setInteractionError(
        err instanceof ApiError
          ? err.detail || err.message
          : err instanceof Error
            ? err.message
            : "Não foi possível excluir o elemento."
      );
    } finally {
      setIsDeletingFeature(false);
    }
  };

  const handleVertexMove = React.useCallback(
    (index: number, coordinates: [number, number]) => {
      setDraftCoordinates((current) =>
        current.map((coordinate, currentIndex) =>
          currentIndex === index ? coordinates : coordinate
        )
      );
    },
    []
  );

  const handleVertexMoveEnd = () => {
    const lastSnapshot = history[historyIndex];
    if (JSON.stringify(lastSnapshot) !== JSON.stringify(draftCoordinates)) {
      pushHistory(draftCoordinates);
    }
  };

  // Movimento do mouse: calcula snap magnético em estruturas próximas
  const handleMouseMove = (coords: [number, number]) => {
    if (interactionMode === "draw_point" || interactionMode === "draw_cable") {
      const nearest = findNearestSnapCandidate(coords, pointCandidates, 25);
      setSnapCandidate(nearest);
    }
  };

  // Atalhos de teclado (Escape e Ctrl+Z)
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && interactionMode !== "view") {
        e.preventDefault();
        handleCancelDrawing();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [interactionMode, handleCancelDrawing, handleUndo, handleRedo]);

  // Limpeza de timers e requisições no unmount
  React.useEffect(() => {
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  // Seleciona feature inicial se especificada na URL
  React.useEffect(() => {
    if (initialSelectedId && data && !selectedFeature && interactionMode === "view") {
      const found = data.features.find((f) => f.id === initialSelectedId);
      if (found) setSelectedFeature(found);
    }
  }, [initialSelectedId, data, selectedFeature, interactionMode]);

  const features = data?.features ?? [];
  const currentLengthMeters = calculateLineLength(draftCoordinates);

  return (
    <div className="flex flex-col h-full w-full min-h-0 relative overflow-hidden bg-background">
      {/* Barra Superior do Mapa */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 border-b border-border bg-card/95 backdrop-blur-sm shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <MapIcon className="h-4 w-4 text-primary" />
            <h1 className="text-sm font-semibold tracking-tight text-foreground">
              Mapa Operacional & Desenho Geográfico
            </h1>
          </div>
          {data && (
            <Badge variant="outline" className="font-mono text-[11px] gap-1 py-0 px-2 h-5">
              <GitBranch className="h-2.5 w-2.5" />
              Topologia: #{data.topology_revision}
            </Badge>
          )}
          <Badge variant="secondary" className="text-[11px] py-0 px-2 h-5">
            {features.length} elementos
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          {isLoading && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mr-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              <span className="hidden sm:inline">Sincronizando BBox...</span>
            </div>
          )}

          {/* Alternador de Modo Mapa / Modo Tabela */}
          <div className="flex items-center rounded-lg border border-border bg-muted p-0.5">
            <Button
              variant={viewMode === "map" ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setViewMode("map")}
              className="h-7 px-2.5 text-xs gap-1.5"
            >
              <MapIcon className="h-3.5 w-3.5" />
              <span>Mapa</span>
            </Button>
            <Button
              variant={viewMode === "table" ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setViewMode("table")}
              className="h-7 px-2.5 text-xs gap-1.5"
            >
              <TableIcon className="h-3.5 w-3.5" />
              <span>Lista ({features.length})</span>
            </Button>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (currentBBoxRef.current) {
                loadFeatures(currentBBoxRef.current, currentZoomRef.current);
              }
            }}
            disabled={isLoading}
            className="h-7 px-2.5 text-xs gap-1.5"
            title="Recarregar dados geográficos da área atual"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin text-primary" : ""}`} />
            <span className="hidden sm:inline">Recarregar</span>
          </Button>
        </div>
      </div>

      {/* Alerta de Erro de Carregamento */}
      {error && (
        <div className="p-3 border-b border-destructive/20 bg-destructive/5 shrink-0">
          <ErrorState
            title="Não foi possível consultar os dados geográficos da rede"
            error={error}
            onRetry={() => {
              if (currentBBoxRef.current) {
                loadFeatures(currentBBoxRef.current, currentZoomRef.current);
              }
            }}
          />
        </div>
      )}

      {interactionError && (
        <div
          role="alert"
          className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs font-medium text-amber-900 dark:text-amber-100"
        >
          {interactionError}
        </div>
      )}

      {/* Alerta de Truncamento de Features */}
      {data?.truncated && (
        <div className="flex items-center justify-between gap-3 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-foreground shrink-0 animate-in fade-in">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <span>
              Muitos ativos nesta região. Aproxime o zoom para carregar toda a densidade física de cabos e estruturas.
            </span>
          </div>
          <Badge variant="outline" className="text-[10px] uppercase font-mono border-amber-500/40 text-amber-700 dark:text-amber-300">
            Truncado
          </Badge>
        </div>
      )}

      {/* Área Principal de Renderização */}
      <div className="flex-1 w-full h-full min-h-0 relative overflow-hidden">
        {viewMode === "map" ? (
          <div className="relative w-full h-full">
            {/* Barra de Ferramentas de Desenho Flutuante */}
            <PermissionGate permission="network:write">
              <DrawingToolbar
                mode={interactionMode}
                pointKind={pointKind}
                verticesCount={draftCoordinates.length}
                canUndo={historyIndex >= 0}
                canRedo={historyIndex < history.length - 1}
                currentLengthMeters={currentLengthMeters}
                snapCandidate={snapCandidate}
                canEditGeometry={
                  selectedFeature?.geometry.type === "LineString" &&
                  selectedFeature.properties.entity_type === "cable_segment"
                }
                isFinishing={isSavingGeometry}
                onSetMode={handleSetMode}
                onUndo={handleUndo}
                onRedo={handleRedo}
                onCancel={handleCancelDrawing}
                onFinish={handleFinishDrawing}
              />
            </PermissionGate>

            {initialViewReady ? (
              <OperationalMap
                features={features}
                layers={layers}
                selectedFeatureId={selectedFeature?.id ?? null}
                onSelectFeature={handleSelectFeature}
                onViewportChange={handleViewportChange}
                initialLat={initialLat}
                initialLng={initialLng}
                initialZoom={initialZoom}
                mode={interactionMode}
                draftCoordinates={draftCoordinates}
                snapCandidate={snapCandidate}
                onMapClick={handleMapClick}
                onMouseMove={handleMouseMove}
                onDoubleClick={handleFinishDrawing}
                onVertexMove={handleVertexMove}
                onVertexMoveEnd={handleVertexMoveEnd}
              />
            ) : (
              <div className="flex h-full min-h-[400px] items-center justify-center bg-card">
                <LoadingState message="Carregando centro padrão do mapa..." />
              </div>
            )}

            {/* Legenda e Filtro de Camadas */}
            <MapLegend layers={layers} onToggleLayer={toggleLayer} />

            {/* Painel Contextual Lateral do Elemento Clicado */}
            <MapFeatureSheet
              feature={interactionMode === "view" ? selectedFeature : null}
              onClose={() => handleSelectFeature(null)}
              onDelete={handleDeleteFeature}
              onContinueCable={handleContinueCable}
              onStartCable={handleStartCable}
              deleting={isDeletingFeature}
            />

            {/* Modal de Revisão Técnica e Cadastro */}
            <DrawingModal
              open={modalOpen}
              draft={activeDraft}
              onClose={handleCancelDrawing}
              onSuccess={() => {
                setModalOpen(false);
                handleCancelDrawing();
                if (currentBBoxRef.current) {
                  loadFeatures(currentBBoxRef.current, currentZoomRef.current);
                }
              }}
            />
          </div>
        ) : (
          /* Modo Alternativo em Lista para Acessibilidade e Ambientes Sem WebGL */
          <div className="h-full overflow-y-auto p-4 sm:p-6">
            <div className="rounded-xl border border-border bg-card shadow-sm">
              <MapFallbackTable
                features={features}
                onSelectFeature={(feat) => {
                  handleSelectFeature(feat);
                  setViewMode("map");
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
