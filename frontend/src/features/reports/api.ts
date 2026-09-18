import { api } from "@/lib/api/client";

export interface CTOOccupancyBuckets {
  empty_0_pct: number;
  low_1_to_50_pct: number;
  high_51_to_99_pct: number;
  full_100_pct: number;
}

export interface DashboardSummaryResponse {
  total_sites: number;
  total_structures: number;
  total_cables: number;
  total_customers: number;
  total_active_service_links: number;
  ctos_occupancy: CTOOccupancyBuckets;
  incomplete_documentation_alerts: string[];
  topology_revision: number;
}

export interface SearchResultItem {
  id: string;
  entity_type: string;
  code: string;
  name: string | null;
  status: string | null;
}

export interface SearchGroup {
  entity_type: string;
  items: SearchResultItem[];
}

export interface GlobalSearchResponse {
  query: string;
  total_results: number;
  groups: SearchGroup[];
}

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
