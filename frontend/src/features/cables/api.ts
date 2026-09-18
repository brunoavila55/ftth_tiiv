import { api } from "@/lib/api/client";
import type { PaginatedResult } from "@/lib/api/types";
import type { LineStringGeometry } from "../map/types";

// ==============================================================================
// CABLES (Cabos Ópticos)
// ==============================================================================

export interface CableRead {
  id: string;
  code: string;
  model: string;
  fiber_count: number;
  tube_count: number;
  color_standard: string;
  status: "planned" | "installed" | "retired" | string;
  notes?: string | null;
  version: number;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCablePayload {
  code: string;
  model: string;
  fiber_count: number;
  tube_count?: number;
  color_standard?: string;
  status?: string;
  notes?: string | null;
}

export interface UpdateCablePayload {
  status?: string;
  notes?: string | null;
}

export async function listCables(params?: {
  page?: number;
  page_size?: number;
  q?: string | null;
}): Promise<PaginatedResult<CableRead>> {
  return api.get<PaginatedResult<CableRead>>("/cables", {
    params: {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 50,
      q: params?.q ?? undefined,
    },
  });
}

export async function getCable(cableId: string): Promise<CableRead> {
  return api.get<CableRead>(`/cables/${cableId}`);
}

export async function createCable(payload: CreateCablePayload): Promise<CableRead> {
  return api.post<CableRead>("/cables", payload);
}

export async function updateCable(
  cableId: string,
  payload: UpdateCablePayload,
  version: number
): Promise<CableRead> {
  return api.patch<CableRead>(`/cables/${cableId}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deleteCable(cableId: string, version: number): Promise<void> {
  return api.delete<void>(`/cables/${cableId}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

// ==============================================================================
// CABLE SEGMENTS (Trechos de cabos entre estruturas)
// ==============================================================================

export interface CableSegmentRead {
  id: string;
  cable_id: string;
  origin_structure_id: string;
  destination_structure_id: string;
  geometry: LineStringGeometry;
  map_length_m: number;
  measured_length_m: number | null;
  slack_length_m: number;
  effective_length_m: number;
  length_source: "measured" | "calculated";
  version: number;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCableSegmentPayload {
  cable_id: string;
  origin_structure_id: string;
  destination_structure_id: string;
  geometry: LineStringGeometry;
  measured_length_m?: number | null;
  slack_length_m?: number;
}

export interface UpdateCableSegmentPayload {
  geometry?: LineStringGeometry | null;
  measured_length_m?: number | null;
  slack_length_m?: number | null;
}

export async function listCableSegments(params?: {
  cable_id?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<CableSegmentRead>> {
  return api.get<PaginatedResult<CableSegmentRead>>("/cable-segments", {
    params: {
      cable_id: params?.cable_id ?? undefined,
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 50,
    },
  });
}

export async function getCableSegment(segmentId: string): Promise<CableSegmentRead> {
  return api.get<CableSegmentRead>(`/cable-segments/${segmentId}`);
}

export async function createCableSegment(
  payload: CreateCableSegmentPayload
): Promise<CableSegmentRead> {
  return api.post<CableSegmentRead>("/cable-segments", payload);
}

export async function updateCableSegment(
  segmentId: string,
  payload: UpdateCableSegmentPayload,
  version: number
): Promise<CableSegmentRead> {
  return api.patch<CableSegmentRead>(`/cable-segments/${segmentId}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deleteCableSegment(segmentId: string, version: number): Promise<void> {
  return api.delete<void>(`/cable-segments/${segmentId}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

// ==============================================================================
// FIBERS & SEGMENT SPLIT (Fibras e Divisão de Trechos)
// ==============================================================================

export interface FiberSegmentRead {
  id: string;
  cable_segment_id: string;
  fiber_id: string;
  fiber_number: number;
  terminal_a_id: string;
  terminal_b_id: string;
  occupancy: "free" | "reserved" | "connected" | string;
}

export async function listSegmentFibers(
  segmentId: string,
  params?: { page?: number; page_size?: number }
): Promise<PaginatedResult<FiberSegmentRead>> {
  return api.get<PaginatedResult<FiberSegmentRead>>(`/cable-segments/${segmentId}/fibers`, {
    params: {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 100,
    },
  });
}

export interface SegmentSplitRequest {
  access_structure_id: string;
  split_coordinates?: [number, number] | null;
  cut_fiber_ids?: string[];
  segment_1_slack_m?: number;
  segment_2_slack_m?: number;
}

export interface SegmentSplitPreviewResponse {
  original_segment_id: string;
  access_structure_id: string;
  total_fibers_count: number;
  cut_fibers_count: number;
  pass_through_fibers_count: number;
  segment_1_map_length_m: number;
  segment_2_map_length_m: number;
  warnings: string[];
}

export interface SegmentSplitResponse {
  success: boolean;
  original_segment_id: string;
  segment_1: CableSegmentRead;
  segment_2: CableSegmentRead;
  pass_through_continuities_count: number;
  cut_terminals_count: number;
  new_topology_revision: number;
}

export async function previewSegmentSplit(
  segmentId: string,
  payload: SegmentSplitRequest
): Promise<SegmentSplitPreviewResponse> {
  return api.post<SegmentSplitPreviewResponse>(
    `/cable-segments/${segmentId}/split/preview`,
    payload
  );
}

export async function splitSegment(
  segmentId: string,
  payload: SegmentSplitRequest
): Promise<SegmentSplitResponse> {
  return api.post<SegmentSplitResponse>(`/cable-segments/${segmentId}/split`, payload);
}
