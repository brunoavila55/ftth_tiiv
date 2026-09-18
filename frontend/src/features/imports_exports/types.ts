export type ImportFormat = "geojson" | "kml" | "csv";
export type ExportFormat = ImportFormat;

export type CollisionStrategy = "error" | "skip" | "replace";

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface ImportPreviewItem {
  line_number: number;
  entity_type: string;
  entity_code?: string | null;
  validation_status: "valid" | "error" | "collision" | string;
  message?: string | null;
}

export interface ImportPreviewResponse {
  import_id: string;
  file_hash: string;
  format: ImportFormat;
  total_records: number;
  valid_records: number;
  error_records: number;
  collision_records: number;
  sample_preview: ImportPreviewItem[];
}

export interface ImportCommitRequest {
  collision_strategy?: CollisionStrategy;
}

export interface ImportCommitResponse {
  job_id: string;
  message: string;
  status: string;
}

export interface ExportRequest {
  format: ImportFormat;
  layers: string[];
}

export interface ExportResponse {
  job_id: string;
  message: string;
}

export interface JobRead {
  id: string;
  type: string;
  status: JobStatus;
  progress_percentage: number;
  error_message?: string | null;
  result_url?: string | null;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
}
