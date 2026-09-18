import { api } from "@/lib/api/client";
import type {
  MeasurementComparisonResponse,
  MeasurementCreate,
  MeasurementRead,
  MeasurementUpdate,
} from "./types";

export interface ListMeasurementsParams {
  service_link_id?: string;
  terminal_id?: string;
  page?: number;
  page_size?: number;
}

export async function listMeasurements(
  params?: ListMeasurementsParams
): Promise<{ items: MeasurementRead[]; total: number }> {
  return api.get<{ items: MeasurementRead[]; total: number }>("/measurements", {
    params: params as Record<string, string | number | boolean | null | undefined>,
  });
}

export async function createMeasurement(payload: MeasurementCreate): Promise<MeasurementRead> {
  return api.post<MeasurementRead>("/measurements", payload);
}

export async function getMeasurement(id: string): Promise<MeasurementRead> {
  return api.get<MeasurementRead>(`/measurements/${id}`);
}

export async function updateMeasurement(
  id: string,
  payload: MeasurementUpdate,
  version: number
): Promise<MeasurementRead> {
  return api.patch<MeasurementRead>(`/measurements/${id}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function deleteMeasurement(id: string, version: number): Promise<void> {
  return api.delete<void>(`/measurements/${id}`, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

export async function compareMeasurement(
  id: string,
  toleranceDb: number = 2.0
): Promise<MeasurementComparisonResponse> {
  return api.get<MeasurementComparisonResponse>(`/measurements/${id}/compare`, {
    params: {
      tolerance_db: toleranceDb,
    },
  });
}
