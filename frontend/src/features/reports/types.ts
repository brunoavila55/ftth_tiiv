import type { components } from "@/lib/api/api-types";

export type { PaginatedResponse } from "@/lib/api/types";
export type CTOOccupancyReportItem = components["schemas"]["CTOOccupancyReportItem"];
export type CableCapacityReportItem = components["schemas"]["CableCapacityReportItem"];
export type InconsistencyReportItem = components["schemas"]["InconsistencyReportItem"];
export type DashboardSummaryResponse = components["schemas"]["DashboardSummaryResponse"];
export type CTOOccupancyBuckets = components["schemas"]["CTOOccupancyBuckets"];
export type GlobalSearchResponse = components["schemas"]["GlobalSearchResponse"];
export type SearchGroup = components["schemas"]["SearchGroup"];
export type SearchResultItem = components["schemas"]["SearchResultItem"];

export interface CTOReportFilters {
  page?: number;
  page_size?: number;
  site_id?: string;
  min_occupancy_pct?: number;
  max_occupancy_pct?: number;
  status?: string;
}

export interface CableReportFilters {
  page?: number;
  page_size?: number;
  status?: string;
  min_usage_pct?: number;
}

export interface InconsistencyReportFilters {
  page?: number;
  page_size?: number;
}

export type ReportTab = "ctos" | "cables" | "inconsistencies";
