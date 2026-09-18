export interface PointGeometry {
  type: "Point";
  coordinates: [number, number]; // [longitude, latitude]
}

export interface LineStringGeometry {
  type: "LineString";
  coordinates: [number, number][]; // [[lon, lat], [lon, lat], ...]
}

export interface FeatureProperties {
  entity_id: string;
  entity_type: string;
  code: string;
  status: string;
  version: number;
  occupancy?: Record<string, number> | null;
  extra?: Record<string, unknown> | null;
}

export interface MapFeature {
  id: string;
  type: "Feature";
  geometry: PointGeometry | LineStringGeometry;
  properties: FeatureProperties;
}

export interface MapFeatureCollection {
  type: "FeatureCollection";
  features: MapFeature[];
  bbox: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  topology_revision: number;
  truncated: boolean;
}

export interface LayerFilters {
  sites: boolean;
  structures: boolean;
  ctos: boolean;
  cables: boolean;
}

export interface MapViewport {
  lat: number;
  lng: number;
  zoom: number;
}

export type MapInteractionMode =
  | "view"
  | "draw_point"
  | "draw_cable"
  | "edit_geometry";

export type PointKind = "site" | "cto" | "ceo" | "pole";

export interface DrawingDraft {
  mode: MapInteractionMode;
  pointKind?: PointKind;
  coordinates: [number, number][]; // Vértices desenhados
  originStructureId?: string | null;
  destinationStructureId?: string | null;
  originStructureCode?: string | null;
  destinationStructureCode?: string | null;
}

