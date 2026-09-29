"use client";

import * as React from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useTheme } from "next-themes";
import type { MapFeature } from "@/features/map/types";
import { MAP_ATTRIBUTION, MAP_STYLE_DARK_URL, MAP_STYLE_LIGHT_URL } from "@/features/map/map-style";

maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

interface WirelessMapProps {
  features: MapFeature[];
  selectedId: string | null;
  onSelect: (feature: MapFeature | null) => void;
  onViewportChange: (bounds: { west: number; south: number; east: number; north: number }) => void;
  initialCenter: [number, number];
  initialZoom: number;
  initialBounds?: [number, number, number, number];
}

const SOURCE_ID = "wireless-features";
const LINK_LAYER = "wireless-links";
const PLANNED_LINK_LAYER = "wireless-planned-links";
const POINT_LAYER = "wireless-sites";

export function WirelessMap({
  features,
  selectedId,
  onSelect,
  onViewportChange,
  initialCenter,
  initialZoom,
  initialBounds,
}: WirelessMapProps) {
  const { resolvedTheme } = useTheme();
  const styleUrl = resolvedTheme === "dark" ? MAP_STYLE_DARK_URL : MAP_STYLE_LIGHT_URL;
  const containerRef = React.useRef<HTMLDivElement>(null);
  const mapRef = React.useRef<maplibregl.Map | null>(null);
  const callbacksRef = React.useRef({ onSelect, onViewportChange });
  const featuresRef = React.useRef(features);
  const selectedRef = React.useRef(selectedId);
  const focusedIdRef = React.useRef<string | null>(null);
  const appliedStyleRef = React.useRef(styleUrl);
  const [mapError, setMapError] = React.useState<string | null>(null);

  callbacksRef.current = { onSelect, onViewportChange };
  featuresRef.current = features;
  selectedRef.current = selectedId;

  const updateSource = React.useCallback(() => {
    const map = mapRef.current;
    if (!map?.getSource(SOURCE_ID)) return;
    const collection = {
      type: "FeatureCollection" as const,
      features: featuresRef.current.map((feature) => ({
        ...feature,
        properties: {
          ...feature.properties,
          kind: feature.properties.extra?.kind ?? "",
          selected: feature.properties.entity_id === selectedRef.current,
        },
      })),
    };
    (map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource).setData(
      collection as Parameters<maplibregl.GeoJSONSource["setData"]>[0]
    );
  }, []);

  React.useEffect(() => {
    if (!containerRef.current) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: styleUrl,
        center: initialCenter,
        zoom: initialZoom,
        attributionControl: false,
      });
    } catch {
      setMapError("Não foi possível iniciar o mapa. Verifique se o navegador permite WebGL.");
      return;
    }
    mapRef.current = map;
    map.addControl(new maplibregl.AttributionControl({ customAttribution: MAP_ATTRIBUTION }), "bottom-right");
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const setupLayers = () => {
      if (map.getSource(SOURCE_ID)) {
        updateSource();
        return;
      }
      map.addSource(SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: LINK_LAYER,
        type: "line",
        source: SOURCE_ID,
        filter: ["all", ["==", ["geometry-type"], "LineString"], ["!=", ["get", "status"], "planned"]],
        paint: {
          "line-color": ["case", ["get", "selected"], "#f43f5e", "#0891b2"],
          "line-width": ["case", ["get", "selected"], 5, 3],
          "line-opacity": 0.85,
        },
      });
      map.addLayer({
        id: PLANNED_LINK_LAYER,
        type: "line",
        source: SOURCE_ID,
        filter: ["all", ["==", ["geometry-type"], "LineString"], ["==", ["get", "status"], "planned"]],
        paint: {
          "line-color": ["case", ["get", "selected"], "#f43f5e", "#0891b2"],
          "line-width": 3,
          "line-dasharray": [2, 2],
        },
      });
      map.addLayer({
        id: POINT_LAYER,
        type: "circle",
        source: SOURCE_ID,
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": ["case", ["get", "selected"], 11, 8],
          "circle-color": [
            "case",
            ["get", "selected"], "#f43f5e",
            ["==", ["get", "kind"], "radio_tower"], "#f59e0b",
            "#0284c7",
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });
      updateSource();
    };

    const notifyViewport = () => {
      const bounds = map.getBounds();
      callbacksRef.current.onViewportChange({
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
      });
    };
    const handleClick = (event: maplibregl.MapMouseEvent) => {
      if (!map.getLayer(POINT_LAYER)) return;
      const hit = map.queryRenderedFeatures(event.point, {
        layers: [POINT_LAYER, LINK_LAYER, PLANNED_LINK_LAYER],
      })[0];
      const id = hit?.properties?.entity_id;
      callbacksRef.current.onSelect(
        typeof id === "string"
          ? featuresRef.current.find((feature) => feature.properties.entity_id === id) ?? null
          : null
      );
    };

    const handleLoad = () => {
      if (initialBounds) {
        map.fitBounds(
          [[initialBounds[0], initialBounds[1]], [initialBounds[2], initialBounds[3]]],
          { padding: 60, maxZoom: 14 }
        );
      } else {
        notifyViewport();
      }
    };
    map.on("style.load", setupLayers);
    map.on("load", handleLoad);
    map.on("moveend", notifyViewport);
    map.on("click", handleClick);
    return () => {
      map.off("style.load", setupLayers);
      map.off("load", handleLoad);
      map.off("moveend", notifyViewport);
      map.off("click", handleClick);
      map.remove();
      mapRef.current = null;
    };
    // Centro e zoom são valores iniciais; mudanças posteriores vêm da interação com o mapa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    const map = mapRef.current;
    if (map && appliedStyleRef.current !== styleUrl) {
      appliedStyleRef.current = styleUrl;
      map.setStyle(styleUrl);
    }
  }, [styleUrl]);

  React.useEffect(() => {
    updateSource();
    const feature = features.find((item) => item.properties.entity_id === selectedId);
    const map = mapRef.current;
    if (!map || !feature || selectedId === focusedIdRef.current) return;
    focusedIdRef.current = selectedId;
    const center: [number, number] = feature.geometry.type === "Point"
      ? feature.geometry.coordinates
      : feature.geometry.coordinates[Math.floor(feature.geometry.coordinates.length / 2)];
    map.flyTo({ center, zoom: Math.max(map.getZoom(), 12) });
  }, [features, selectedId, updateSource]);

  return (
    <div className="relative h-full min-h-[480px] w-full overflow-hidden rounded-lg bg-card">
      <div ref={containerRef} className="h-full w-full" aria-label="Mapa wireless" />
      {mapError && (
        <div role="alert" className="absolute inset-0 flex items-center justify-center bg-card p-6 text-center text-sm text-destructive">
          {mapError}
        </div>
      )}
    </div>
  );
}
