import { api } from "@/lib/api/client";
import type { TraceRequest, TraceResponse } from "./types";
import { listServiceLinks } from "../customers/api";

export async function traceOpticalPath(payload: TraceRequest): Promise<TraceResponse> {
  return api.post<TraceResponse>("/topology/trace", payload);
}

/**
 * Busca o terminal associado a um cliente através do service_link ativo dele
 */
export async function findTerminalForCustomer(customerId: string): Promise<string | null> {
  const links = await listServiceLinks({ customer_id: customerId, page_size: 1 });
  if (!links.items || links.items.length === 0) return null;
  const activeLink = links.items.find((l) => l.status === "active") || links.items[0];
  if (!activeLink) return null;

  // O port_id do atendimento é a porta da CTO
  return activeLink.port_id;
}
