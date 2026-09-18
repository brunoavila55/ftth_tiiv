import { api } from "@/lib/api/client";
import type { PaginatedResult, SiteRead } from "@/lib/api/types";
export type { SiteRead };

// ==============================================================================
// SITES (POPs / Locais Técnicos)
// ==============================================================================

export interface ListSitesParams {
  page?: number;
  page_size?: number;
  kind?: string | null;
  q?: string | null;
}

export interface CreateSitePayload {
  code: string;
  name: string;
  kind?: string;
  location: {
    type: "Point";
    coordinates: [number, number];
  };
  status?: string;
  address?: string | null;
  notes?: string | null;
}

export interface UpdateSitePayload {
  name?: string;
  kind?: string;
  location?: {
    type: "Point";
    coordinates: [number, number];
  };
  status?: string;
  address?: string | null;
  notes?: string | null;
}

export async function listSites(params?: ListSitesParams): Promise<PaginatedResult<SiteRead>> {
  const queryParams: Record<string, string | number | boolean | undefined | null> = {};
  if (params?.page) queryParams.page = params.page;
  if (params?.page_size) queryParams.page_size = params.page_size;
  if (params?.kind) queryParams.kind = params.kind;
  if (params?.q) queryParams.q = params.q;

  return api.get<PaginatedResult<SiteRead>>("/sites", {
    params: queryParams,
  });
}

export async function getSite(id: string): Promise<SiteRead> {
  return api.get<SiteRead>(`/sites/${id}`);
}

export async function createSite(payload: CreateSitePayload): Promise<SiteRead> {
  return api.post<SiteRead>("/sites", payload);
}

export async function updateSite(
  id: string,
  payload: UpdateSitePayload,
  version: number
): Promise<SiteRead> {
  return api.patch<SiteRead>(`/sites/${id}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deleteSite(id: string, version: number): Promise<void> {
  return api.delete<void>(`/sites/${id}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

// ==============================================================================
// STRUCTURES (Postes, CEOs, CTOs, Caixas subterrâneas)
// ==============================================================================

export interface StructureRead {
  id: string;
  code: string;
  kind: "pole" | "ceo" | "cto" | "manhole" | "pedestal" | string;
  location: {
    type: "Point";
    coordinates: [number, number];
  };
  capacity: number;
  status: "planned" | "installed" | "retired" | string;
  condition: "ok" | "degraded" | "damaged" | string;
  notes?: string | null;
  site_id?: string | null;
  version: number;
  created_at?: string;
  updated_at?: string;
}

export interface ListStructuresParams {
  page?: number;
  page_size?: number;
  kind?: string | null;
  q?: string | null;
}

export interface CreateStructurePayload {
  code: string;
  kind: string;
  location: {
    type: "Point";
    coordinates: [number, number];
  };
  capacity?: number;
  status?: string;
  condition?: string;
  notes?: string | null;
  site_id?: string | null;
}

export interface UpdateStructurePayload {
  location?: {
    type: "Point";
    coordinates: [number, number];
  };
  capacity?: number;
  status?: string;
  condition?: string;
  notes?: string | null;
  site_id?: string | null;
}

export interface StructureConnectivityResponse {
  structure_id: string;
  structure_code: string;
  topology_revision: number;
  terminated_cables: Array<{
    cable_id: string;
    cable_code: string;
    fiber_count: number;
    segment_id: string;
  }>;
  connections: Array<{
    id: string;
    connection_type: string;
    source_fiber_id?: string;
    target_fiber_id?: string;
    attenuation_db?: number;
  }>;
}

export async function listStructures(
  params?: ListStructuresParams
): Promise<PaginatedResult<StructureRead>> {
  const queryParams: Record<string, string | number | boolean | undefined | null> = {};
  if (params?.page) queryParams.page = params.page;
  if (params?.page_size) queryParams.page_size = params.page_size;
  if (params?.kind) queryParams.kind = params.kind;
  if (params?.q) queryParams.q = params.q;

  return api.get<PaginatedResult<StructureRead>>("/structures", {
    params: queryParams,
  });
}

export async function getStructure(id: string): Promise<StructureRead> {
  return api.get<StructureRead>(`/structures/${id}`);
}

export async function createStructure(payload: CreateStructurePayload): Promise<StructureRead> {
  return api.post<StructureRead>("/structures", payload);
}

export async function updateStructure(
  id: string,
  payload: UpdateStructurePayload,
  version: number
): Promise<StructureRead> {
  return api.patch<StructureRead>(`/structures/${id}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deleteStructure(id: string, version: number): Promise<void> {
  return api.delete<void>(`/structures/${id}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function getStructureConnectivity(
  structureId: string
): Promise<StructureConnectivityResponse> {
  return api.get<StructureConnectivityResponse>(`/structures/${structureId}/connectivity`);
}

// ==============================================================================
// DEVICES (OLT, DIO, ONU, Switch, EDFA)
// ==============================================================================

export interface DeviceRead {
  id: string;
  code: string;
  kind: "olt" | "dio" | "onu" | "switch" | string;
  manufacturer: string;
  model: string;
  serial_number?: string | null;
  site_id?: string | null;
  structure_id?: string | null;
  status: "planned" | "installed" | "retired" | string;
  condition: "ok" | "degraded" | "damaged" | string;
  notes?: string | null;
  version: number;
  created_at?: string;
  updated_at?: string;
}

export interface ListDevicesParams {
  page?: number;
  page_size?: number;
  kind?: string | null;
  q?: string | null;
  site_id?: string | null;
  structure_id?: string | null;
}

export interface CreateDevicePayload {
  code: string;
  kind: string;
  manufacturer: string;
  model: string;
  serial_number?: string | null;
  site_id?: string | null;
  structure_id?: string | null;
  status?: string;
  condition?: string;
  notes?: string | null;
}

export interface UpdateDevicePayload {
  manufacturer?: string;
  model?: string;
  serial_number?: string | null;
  site_id?: string | null;
  structure_id?: string | null;
  status?: string;
  condition?: string;
  notes?: string | null;
}

export async function listDevices(
  params?: ListDevicesParams
): Promise<PaginatedResult<DeviceRead>> {
  const queryParams: Record<string, string | number | boolean | undefined | null> = {};
  if (params?.page) queryParams.page = params.page;
  if (params?.page_size) queryParams.page_size = params.page_size;
  if (params?.kind) queryParams.kind = params.kind;
  if (params?.q) queryParams.q = params.q;

  const result = await api.get<PaginatedResult<DeviceRead>>("/devices", {
    params: queryParams,
  });

  // Filtragem no cliente para site_id e structure_id caso fornecido
  if (params?.site_id || params?.structure_id) {
    const filteredItems = result.items.filter((d) => {
      if (params.site_id && d.site_id !== params.site_id) return false;
      if (params.structure_id && d.structure_id !== params.structure_id) return false;
      return true;
    });
    return {
      ...result,
      items: filteredItems,
      total: filteredItems.length,
    };
  }

  return result;
}

export async function getDevice(id: string): Promise<DeviceRead> {
  return api.get<DeviceRead>(`/devices/${id}`);
}

export async function createDevice(payload: CreateDevicePayload): Promise<DeviceRead> {
  return api.post<DeviceRead>("/devices", payload);
}

export async function updateDevice(
  id: string,
  payload: UpdateDevicePayload,
  version: number
): Promise<DeviceRead> {
  return api.patch<DeviceRead>(`/devices/${id}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deleteDevice(id: string, version: number): Promise<void> {
  return api.delete<void>(`/devices/${id}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

// ==============================================================================
// PORTS (Portas de dispositivos ou estruturas)
// ==============================================================================

export interface PortRead {
  id: string;
  name: string;
  role: "pon" | "uplink" | "client_access" | "pass_through" | "internal" | string;
  device_id?: string | null;
  structure_id?: string | null;
  has_internal_pass_through: boolean;
  connector_type: string;
  notes?: string | null;
  version: number;
  created_at?: string;
  updated_at?: string;
}

export interface ListPortsParams {
  page?: number;
  page_size?: number;
  device_id?: string | null;
  structure_id?: string | null;
}

export interface CreatePortPayload {
  name: string;
  role: string;
  device_id?: string | null;
  structure_id?: string | null;
  has_internal_pass_through?: boolean;
  connector_type?: string;
  notes?: string | null;
}

export interface UpdatePortPayload {
  name?: string;
  role?: string;
  connector_type?: string;
  notes?: string | null;
}

export async function listPorts(params?: ListPortsParams): Promise<PaginatedResult<PortRead>> {
  const queryParams: Record<string, string | number | boolean | undefined | null> = {};
  if (params?.page) queryParams.page = params.page;
  if (params?.page_size) queryParams.page_size = params.page_size;
  if (params?.device_id) queryParams.device_id = params.device_id;
  if (params?.structure_id) queryParams.structure_id = params.structure_id;

  return api.get<PaginatedResult<PortRead>>("/ports", {
    params: queryParams,
  });
}

export async function getPort(id: string): Promise<PortRead> {
  return api.get<PortRead>(`/ports/${id}`);
}

export async function createPort(payload: CreatePortPayload): Promise<PortRead> {
  return api.post<PortRead>("/ports", payload);
}

export async function updatePort(
  id: string,
  payload: UpdatePortPayload,
  version: number
): Promise<PortRead> {
  return api.patch<PortRead>(`/ports/${id}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deletePort(id: string, version: number): Promise<void> {
  return api.delete<void>(`/ports/${id}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}
