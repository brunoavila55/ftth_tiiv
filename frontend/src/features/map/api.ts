import { api } from "@/lib/api/client";
import type { MapFeatureCollection } from "./types";

export interface GetMapFeaturesParams {
  bbox: string; // "minLon,minLat,maxLon,maxLat"
  layers?: string; // "sites,structures,cables"
  zoom?: number;
}

/**
 * Converte 4 coordenadas de envelope em string de bounding box WGS84 válida
 */
export function formatBBox(bounds: {
  west: number;
  south: number;
  east: number;
  north: number;
}): string {
  const minLon = bounds.west.toFixed(6);
  const minLat = bounds.south.toFixed(6);
  const maxLon = bounds.east.toFixed(6);
  const maxLat = bounds.north.toFixed(6);
  return `${minLon},${minLat},${maxLon},${maxLat}`;
}

/**
 * Consulta feições espaciais dentro de uma Bounding Box com suporte a cancelamento via AbortSignal
 */
export async function getMapFeatures(
  params: GetMapFeaturesParams,
  signal?: AbortSignal
): Promise<MapFeatureCollection> {
  return api.get<MapFeatureCollection>("/map/features", {
    params: {
      bbox: params.bbox,
      layers: params.layers ?? "sites,structures,cables",
      zoom: params.zoom ?? 14,
    },
    signal,
  });
}
