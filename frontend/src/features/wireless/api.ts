import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/api-types";
import type { PaginatedResult } from "@/lib/api/types";

export type RadioLinkRead = components["schemas"]["RadioLinkRead"];

export interface RadioLinkCreatePayload {
  code: string;
  name: string;
  site_a_id: string;
  site_b_id: string;
  radio_a_id: string;
  radio_b_id: string;
  frequency_mhz: number;
  channel_width_mhz: number;
  status: "planned" | "installed" | "retired";
  notes?: string | null;
}

export type RadioLinkUpdatePayload = Pick<
  RadioLinkCreatePayload,
  "name" | "frequency_mhz" | "channel_width_mhz" | "status" | "notes"
>;

export async function listRadioLinks(params: {
  page?: number;
  page_size?: number;
  site_id?: string;
  q?: string;
} = {}): Promise<PaginatedResult<RadioLinkRead>> {
  return api.get<PaginatedResult<RadioLinkRead>>("/radio-links", { params });
}

export async function createRadioLink(payload: RadioLinkCreatePayload): Promise<RadioLinkRead> {
  return api.post<RadioLinkRead>("/radio-links", payload);
}

export async function updateRadioLink(
  id: string,
  payload: RadioLinkUpdatePayload,
  version: number
): Promise<RadioLinkRead> {
  return api.patch<RadioLinkRead>(`/radio-links/${id}`, payload, {
    headers: { "If-Match": `"${version}"` },
  });
}

export async function deleteRadioLink(id: string, version: number): Promise<void> {
  return api.delete<void>(`/radio-links/${id}`, {
    headers: { "If-Match": `"${version}"` },
  });
}
