"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/state-displays";
import { DEFAULT_MAP_VIEW } from "@/features/map/constants";
import { formatBBox } from "@/features/map/api";
import type { MapFeature, MapFeatureCollection } from "@/features/map/types";
import { getAppSettings } from "@/features/settings/api";
import { loadWirelessSites } from "../load-options";
import { getWirelessMapFeatures } from "../map-api";

const WirelessMap = dynamic(
  () => import("./wireless-map").then((module) => module.WirelessMap),
  { ssr: false, loading: () => <LoadingState message="Carregando mapa wireless..." /> }
);

function validCoordinate(value: string | null, min: number, max: number): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : null;
}

function getSiteBounds(sites: Awaited<ReturnType<typeof loadWirelessSites>>) {
  const coordinates = sites.map((site) => site.location?.coordinates).filter((value): value is [number, number] =>
    Array.isArray(value) && value.length === 2
  );
  if (coordinates.length < 2) return null;
  const west = Math.min(...coordinates.map(([longitude]) => longitude));
  const east = Math.max(...coordinates.map(([longitude]) => longitude));
  const south = Math.min(...coordinates.map(([, latitude]) => latitude));
  const north = Math.max(...coordinates.map(([, latitude]) => latitude));
  const padding = 0.001;
  return [
    west === east ? west - padding : west,
    south === north ? south - padding : south,
    west === east ? east + padding : east,
    south === north ? north + padding : north,
  ] as [number, number, number, number];
}

export function WirelessMapView() {
  const searchParams = useSearchParams();
  const urlLat = validCoordinate(searchParams.get("lat"), -90, 90);
  const urlLng = validCoordinate(searchParams.get("lng"), -180, 180);
  const urlZoom = validCoordinate(searchParams.get("zoom"), 1, 22);
  const hasUrlPosition = urlLat !== null && urlLng !== null;
  const settingsQuery = useQuery({ queryKey: ["app-settings"], queryFn: getAppSettings });
  const sitesQuery = useQuery({
    queryKey: ["wireless", "map", "sites"],
    queryFn: loadWirelessSites,
    enabled: !hasUrlPosition,
  });

  const [collection, setCollection] = React.useState<MapFeatureCollection | null>(null);
  const [selected, setSelected] = React.useState<MapFeature | null>(null);
  const [dismissedInitialSelection, setDismissedInitialSelection] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showPops, setShowPops] = React.useState(true);
  const [showTowers, setShowTowers] = React.useState(true);
  const [showLinks, setShowLinks] = React.useState(true);
  const lastBboxRef = React.useRef<string | null>(null);
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const controllerRef = React.useRef<AbortController | null>(null);

  const load = React.useCallback((bbox: string) => {
    lastBboxRef.current = bbox;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    controllerRef.current?.abort();
    debounceRef.current = setTimeout(async () => {
      const controller = new AbortController();
      controllerRef.current = controller;
      setLoading(true);
      setError(null);
      try {
        const response = await getWirelessMapFeatures(bbox, controller.signal);
        if (!controller.signal.aborted) setCollection(response);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Falha ao carregar o mapa wireless.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
  }, []);

  React.useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    controllerRef.current?.abort();
  }, []);

  const initialSelectedId = searchParams.get("selected");
  const initialFeature = dismissedInitialSelection
    ? null
    : collection?.features.find((feature) => feature.properties.entity_id === initialSelectedId) ?? null;
  const selectedFeature = selected ?? initialFeature;
  const visibleFeatures = React.useMemo(() => (collection?.features ?? []).filter((feature) => {
    if (feature.properties.entity_type === "radio_link") return showLinks;
    return feature.properties.extra?.kind === "radio_tower" ? showTowers : showPops;
  }), [collection, showPops, showTowers, showLinks]);

  const siteCoordinates = sitesQuery.data?.map((site) => site.location?.coordinates).filter((coordinates): coordinates is [number, number] =>
    Array.isArray(coordinates) && coordinates.length === 2
  ) ?? [];
  const firstSite = siteCoordinates[0];
  const center: [number, number] = hasUrlPosition
    ? [urlLng, urlLat]
    : firstSite ?? [
        settingsQuery.data?.default_map_center[0] ?? DEFAULT_MAP_VIEW.longitude,
        settingsQuery.data?.default_map_center[1] ?? DEFAULT_MAP_VIEW.latitude,
      ];
  const zoom = urlZoom ?? (firstSite ? 12 : settingsQuery.data?.default_map_zoom ?? DEFAULT_MAP_VIEW.zoom);
  const bounds = hasUrlPosition ? null : getSiteBounds(sitesQuery.data ?? []);
  const ready = hasUrlPosition || (!settingsQuery.isPending && !sitesQuery.isPending);
  const extra = selectedFeature?.properties.extra ?? {};
  const isLink = selectedFeature?.properties.entity_type === "radio_link";

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">Mapa Wireless</h1>
          <p className="text-xs text-muted-foreground">POPs, torres e enlaces de rádio em um mapa separado da rede de fibra.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => lastBboxRef.current && load(lastBboxRef.current)} disabled={!lastBboxRef.current || loading}>
            <RefreshCw className="mr-1.5 h-4 w-4" /> Atualizar
          </Button>
          <Button size="sm" asChild><Link href="/wireless?type=links">Gerenciar enlaces</Link></Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 rounded-lg border border-border bg-card px-4 py-3 text-xs">
        <label className="flex items-center gap-2"><input type="checkbox" checked={showPops} onChange={(event) => setShowPops(event.target.checked)} aria-label="Mostrar POPs wireless" /><span className="h-3 w-3 rounded-full bg-sky-600" /> POPs wireless</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={showTowers} onChange={(event) => setShowTowers(event.target.checked)} aria-label="Mostrar torres de rádio" /><span className="h-3 w-3 rounded-full bg-amber-500" /> Torres</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={showLinks} onChange={(event) => setShowLinks(event.target.checked)} aria-label="Mostrar enlaces de rádio" /><span className="h-1 w-4 bg-cyan-600" /> Enlaces</label>
        <span className="ml-auto text-muted-foreground">{visibleFeatures.length} elemento(s) visíveis</span>
      </div>

      {error && <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">{error}</p>}
      {collection?.truncated && <p className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs"><AlertTriangle className="h-4 w-4" /> Há mais elementos nesta região. Aproxime o mapa para ver todos.</p>}
      {!ready ? <LoadingState message="Preparando mapa wireless..." /> : (
        <div className="h-[min(70vh,760px)] min-h-[500px] w-full">
          <WirelessMap
            features={visibleFeatures}
            selectedId={selectedFeature?.properties.entity_id ?? null}
            onSelect={(feature) => { setDismissedInitialSelection(true); setSelected(feature); }}
            onViewportChange={(viewport) => load(formatBBox(viewport))}
            initialCenter={center}
            initialZoom={zoom}
            initialBounds={bounds ?? undefined}
          />
        </div>
      )}

      {selectedFeature && (
        <div className="rounded-lg border border-border bg-card p-4 text-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{selectedFeature.properties.code}</p>
              <p className="text-xs text-muted-foreground">{String(extra.name ?? (isLink ? "Enlace de rádio" : extra.kind === "radio_tower" ? "Torre de rádio" : "POP wireless"))}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => { setDismissedInitialSelection(true); setSelected(null); }}>Fechar</Button>
          </div>
          {isLink && <p className="mt-2 text-xs text-muted-foreground">{String(extra.site_a_code ?? "Ponta A")} ↔ {String(extra.site_b_code ?? "Ponta B")} · {String(extra.frequency_mhz ?? "—")} MHz · canal {String(extra.channel_width_mhz ?? "—")} MHz</p>}
          <Button variant="outline" size="sm" className="mt-3" asChild>
            <Link href={isLink ? "/wireless?type=links" : `/sites/${selectedFeature.properties.entity_id}`}>
              {isLink ? "Ver enlaces" : "Abrir cadastro"}
            </Link>
          </Button>
        </div>
      )}
    </div>
  );
}
