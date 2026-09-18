import { api } from "@/lib/api/client";
import type { PaginatedResult } from "@/lib/api/types";
import type {
  CustomerCreate,
  CustomerRead,
  CustomerUpdate,
  CtoPortOccupancy,
  ServiceLinkCreate,
  ServiceLinkRead,
  ServiceLinkUpdate,
} from "./types";
import type { DeviceRead } from "../inventory/api";

// ==============================================================================
// CUSTOMERS (Clientes / Assinantes)
// ==============================================================================

export async function listCustomers(params?: {
  page?: number;
  page_size?: number;
  q?: string | null;
}): Promise<PaginatedResult<CustomerRead>> {
  return api.get<PaginatedResult<CustomerRead>>("/customers", {
    params: {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 50,
      q: params?.q ?? undefined,
    },
  });
}

export async function getCustomer(customerId: string): Promise<CustomerRead> {
  return api.get<CustomerRead>(`/customers/${customerId}`);
}

export async function createCustomer(payload: CustomerCreate): Promise<CustomerRead> {
  return api.post<CustomerRead>("/customers", payload);
}

export async function updateCustomer(
  customerId: string,
  payload: CustomerUpdate,
  version: number
): Promise<CustomerRead> {
  return api.patch<CustomerRead>(`/customers/${customerId}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deleteCustomer(
  customerId: string,
  version: number
): Promise<void> {
  return api.delete<void>(`/customers/${customerId}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

// ==============================================================================
// SERVICE LINKS (Atendimentos Ópticos)
// ==============================================================================

export async function listServiceLinks(params?: {
  page?: number;
  page_size?: number;
  customer_id?: string | null;
  port_id?: string | null;
}): Promise<PaginatedResult<ServiceLinkRead>> {
  return api.get<PaginatedResult<ServiceLinkRead>>("/service-links", {
    params: {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 50,
      customer_id: params?.customer_id ?? undefined,
      port_id: params?.port_id ?? undefined,
    },
  });
}

export async function getServiceLink(linkId: string): Promise<ServiceLinkRead> {
  return api.get<ServiceLinkRead>(`/service-links/${linkId}`);
}

export async function createServiceLink(
  payload: ServiceLinkCreate
): Promise<ServiceLinkRead> {
  return api.post<ServiceLinkRead>("/service-links", payload);
}

export async function updateServiceLink(
  linkId: string,
  payload: ServiceLinkUpdate,
  version: number
): Promise<ServiceLinkRead> {
  return api.patch<ServiceLinkRead>(`/service-links/${linkId}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deactivateServiceLink(
  linkId: string,
  version: number
): Promise<void> {
  return api.delete<void>(`/service-links/${linkId}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

// ==============================================================================
// CTO OCCUPANCY (Ocupação e Portas de CTO)
// ==============================================================================

export async function getCtoOccupancy(
  structureId: string
): Promise<CtoPortOccupancy> {
  return api.get<CtoPortOccupancy>(`/structures/${structureId}/cto-occupancy`);
}

export async function listAvailableOnus(): Promise<PaginatedResult<DeviceRead>> {
  return api.get<PaginatedResult<DeviceRead>>("/devices", {
    params: {
      page: 1,
      page_size: 100,
    },
  });
}
