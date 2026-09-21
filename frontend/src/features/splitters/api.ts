import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/api-types";
import type { PaginatedResult } from "@/lib/api/types";

export type SplitterRead = components["schemas"]["SplitterRead"];
export type SplitterPortLoss = components["schemas"]["SplitterPortLoss"];

export interface SplitterCreatePayload {
  code: string;
  structure_id?: string | null;
  device_id?: string | null;
  ratio: string;
  output_ports_count: number;
  ports: SplitterPortLoss[];
  notes?: string | null;
}

export interface SplitterUpdatePayload {
  notes?: string | null;
  ports?: SplitterPortLoss[];
}

export async function listSplitters(
  structureId: string,
  pageSize = 100
): Promise<PaginatedResult<SplitterRead>> {
  return api.get<PaginatedResult<SplitterRead>>("/splitters", {
    params: { structure_id: structureId, page_size: pageSize },
  });
}

export async function listAllSplitters(params: {
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResult<SplitterRead>> {
  return api.get<PaginatedResult<SplitterRead>>("/splitters", { params });
}

export async function createSplitter(payload: SplitterCreatePayload): Promise<SplitterRead> {
  return api.post<SplitterRead>("/splitters", payload);
}

export async function updateSplitter(
  id: string,
  payload: SplitterUpdatePayload,
  version: number
): Promise<SplitterRead> {
  return api.patch<SplitterRead>(`/splitters/${id}`, payload, {
    headers: { "If-Match": `"${version}"` },
  });
}

export async function deleteSplitter(id: string, version: number): Promise<void> {
  return api.delete<void>(`/splitters/${id}`, {
    headers: { "If-Match": `"${version}"` },
  });
}
