import { api } from "@/lib/api/client";
import type { PaginatedResult } from "@/lib/api/types";

export type TerminalKind =
  | "fiber_endpoint"
  | "port_front"
  | "port_back"
  | "splitter_input"
  | "splitter_output";

export type ConnectionType = "fusion_splice" | "patch_cord" | "internal_continuity";

export type BatchOperationType = "connect" | "disconnect" | "reserve" | "release";

export interface TerminalRead {
  id: string;
  kind: TerminalKind;
  entity_id: string;
  entity_type: string;
  label: string;
  is_occupied: boolean;
}

export interface ConnectionRead {
  id: string;
  terminal_a_id: string;
  terminal_b_id: string;
  connection_type: ConnectionType;
  loss_db: number;
  structure_id: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TerminalReservationRead {
  id: string;
  terminal_id: string;
  reason: string;
  reserved_by_id: string | null;
  expires_at: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
}

export interface InternalEdgeRead {
  id: string;
  terminal_a_id: string;
  terminal_b_id: string;
  edge_type: string;
  entity_type: string;
  entity_id: string;
  loss_db: number;
  is_bidirectional: boolean;
}

export interface StructureConnectivityResponse {
  structure_id: string;
  topology_revision: number;
  terminals: TerminalRead[];
  connections: ConnectionRead[];
  reservations: TerminalReservationRead[];
  internal_edges: InternalEdgeRead[];
}

export interface BatchOperationItem {
  action: BatchOperationType;
  terminal_a_id: string;
  terminal_b_id?: string | null;
  connection_type?: ConnectionType | null;
  loss_db?: number | null;
  reservation_reason?: string | null;
}

export interface ConnectionBatchRequest {
  expected_topology_revision: number;
  structure_id: string;
  operations: BatchOperationItem[];
}

export interface ConnectionBatchResponse {
  success: boolean;
  applied_operations_count: number;
  new_topology_revision: number;
}

export interface ConnectionCreate {
  terminal_a_id: string;
  terminal_b_id: string;
  connection_type: ConnectionType;
  loss_db?: number;
  structure_id?: string | null;
  notes?: string | null;
}

export interface ListConnectionsParams {
  structure_id?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export async function getStructureConnectivity(
  structureId: string
): Promise<StructureConnectivityResponse> {
  return api.get<StructureConnectivityResponse>(
    `/structures/${structureId}/connectivity`
  );
}

export async function executeBatchConnections(
  payload: ConnectionBatchRequest
): Promise<ConnectionBatchResponse> {
  return api.post<ConnectionBatchResponse>("/connections/batch", payload);
}

export async function createConnection(
  payload: ConnectionCreate
): Promise<ConnectionRead> {
  return api.post<ConnectionRead>("/connections", payload);
}

export async function deleteConnection(
  connectionId: string,
  version?: number | string
): Promise<void> {
  const headers: Record<string, string> = {};
  if (version !== undefined) {
    headers["If-Match"] = `"${version}"`;
  }
  return api.delete<void>(`/connections/${connectionId}`, { headers });
}

export async function listConnections(
  params: ListConnectionsParams = {}
): Promise<PaginatedResult<ConnectionRead>> {
  const query = new URLSearchParams();
  if (params.structure_id) query.set("structure_id", params.structure_id);
  if (params.is_active !== undefined) query.set("is_active", String(params.is_active));
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));

  const qs = query.toString();
  return api.get<PaginatedResult<ConnectionRead>>(`/connections${qs ? `?${qs}` : ""}`);
}
