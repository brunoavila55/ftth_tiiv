import { api } from "@/lib/api/client";
import type { PaginatedResponse } from "@/lib/api/types";
import type {
  CableCapacityReportItem,
  CableReportFilters,
  CTOOccupancyReportItem,
  CTOReportFilters,
  DashboardSummaryResponse,
  GlobalSearchResponse,
  InconsistencyReportFilters,
  InconsistencyReportItem,
} from "./types";

export * from "./types";

/**
 * Consulta indicadores consolidados do painel operacional
 */
export async function getDashboardSummary(signal?: AbortSignal): Promise<DashboardSummaryResponse> {
  return api.get<DashboardSummaryResponse>("/dashboard/summary", { signal });
}

/**
 * Realiza busca global textual indexada por código, nome ou identificador
 */
export async function searchGlobal(
  query: string,
  limit: number = 20,
  signal?: AbortSignal
): Promise<GlobalSearchResponse> {
  return api.get<GlobalSearchResponse>("/search", {
    params: {
      q: query,
      limit,
    },
    signal,
  });
}

/**
 * Consulta relatório paginado de capacidade e ocupação de caixas CTO
 */
export async function getCTOOccupancyReport(
  filters?: CTOReportFilters,
  signal?: AbortSignal
): Promise<PaginatedResponse<CTOOccupancyReportItem>> {
  const params: Record<string, string | number> = {};

  if (filters?.page) params.page = filters.page;
  if (filters?.page_size) params.page_size = filters.page_size;
  if (filters?.site_id) params.site_id = filters.site_id;
  if (filters?.status) params.status = filters.status;
  if (filters?.min_occupancy_pct !== undefined) params.min_occupancy_pct = filters.min_occupancy_pct;
  if (filters?.max_occupancy_pct !== undefined) params.max_occupancy_pct = filters.max_occupancy_pct;

  return api.get<PaginatedResponse<CTOOccupancyReportItem>>("/reports/ctos", {
    params,
    signal,
  });
}

/**
 * Consulta relatório paginado de capacidade óptica de cabos
 */
export async function getCableCapacityReport(
  filters?: CableReportFilters,
  signal?: AbortSignal
): Promise<PaginatedResponse<CableCapacityReportItem>> {
  const params: Record<string, string | number> = {};

  if (filters?.page) params.page = filters.page;
  if (filters?.page_size) params.page_size = filters.page_size;
  if (filters?.status) params.status = filters.status;
  if (filters?.min_usage_pct !== undefined) params.min_usage_pct = filters.min_usage_pct;

  return api.get<PaginatedResponse<CableCapacityReportItem>>("/reports/cables", {
    params,
    signal,
  });
}

/**
 * Consulta relatório paginado de inconsistências e anomalias técnicas da rede
 */
export async function getInconsistenciesReport(
  filters?: InconsistencyReportFilters,
  signal?: AbortSignal
): Promise<PaginatedResponse<InconsistencyReportItem>> {
  const params: Record<string, string | number> = {};

  if (filters?.page) params.page = filters.page;
  if (filters?.page_size) params.page_size = filters.page_size;

  return api.get<PaginatedResponse<InconsistencyReportItem>>("/reports/inconsistencies", {
    params,
    signal,
  });
}
