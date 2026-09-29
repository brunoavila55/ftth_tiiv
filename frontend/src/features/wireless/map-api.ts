import { api } from "@/lib/api/client";
import type { MapFeatureCollection } from "@/features/map/types";

export function getWirelessMapFeatures(
  bbox: string,
  signal?: AbortSignal
): Promise<MapFeatureCollection> {
  return api.get<MapFeatureCollection>("/map/wireless/features", {
    params: { bbox },
    signal,
  });
}
