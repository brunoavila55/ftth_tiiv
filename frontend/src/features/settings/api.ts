import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/api-types";

export type AppSettingsRead = components["schemas"]["AppSettingsRead"];
export type AppSettingsUpdate = components["schemas"]["AppSettingsUpdate"];

export async function getAppSettings(): Promise<AppSettingsRead> {
  return api.get<AppSettingsRead>("/settings");
}

export async function updateAppSettings(
  payload: AppSettingsUpdate,
  version: number
): Promise<AppSettingsRead> {
  return api.patch<AppSettingsRead>("/settings", payload, {
    headers: { "If-Match": `"${version}"` },
  });
}
