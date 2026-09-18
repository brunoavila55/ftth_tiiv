// ==============================================================================
// TOPOLOGY & OPTICAL PATH TRACING TYPES (Contratos F12 / B09)
// ==============================================================================

export type TraceDirection = "downstream" | "upstream";

export type TraceStatus =
  | "complete"
  | "incomplete"
  | "ambiguous"
  | "cycle_detected"
  | "limit_exceeded";

export interface TraceRequest {
  start_terminal_id: string;
  direction?: TraceDirection;
  max_results?: number;
}

export interface TraceStep {
  step_number: number;
  element_type: string;
  element_id: string;
  element_code?: string | null;
  input_terminal_id?: string | null;
  output_terminal_id?: string | null;
  length_m: number;
  loss_db: number;
  accumulated_length_m: number;
  accumulated_loss_db: number;
  location_code?: string | null;
}

export interface TracePath {
  path_id: string;
  origin_terminal_id: string;
  destination_terminal_id?: string | null;
  total_length_m: number;
  total_loss_db: number;
  steps: TraceStep[];
}

export interface TraceResponse {
  topology_revision: number;
  status: TraceStatus;
  paths: TracePath[];
  warnings: string[];
  unresolved_terminals: string[];
}
