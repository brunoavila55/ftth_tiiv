/**
 * Tipos e modelos para o módulo de Orçamento Óptico e Balanço de Potência (F13).
 */

export type OpticalDirection = "downstream" | "upstream";

export type BudgetAssessment =
  | "pass"
  | "low_margin"
  | "below_sensitivity"
  | "overload"
  | "unknown";

export interface OpticalProfileRead {
  id: string;
  name: string;
  technology: string;
  wavelength_nm: number;
  tx_min_dbm: number;
  tx_max_dbm: number;
  rx_sensitivity_dbm: number;
  rx_overload_dbm: number;
  default_attenuation_db_per_km: number;
  notes?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface BudgetCalculationRequest {
  service_link_id?: string | null;
  start_terminal_id?: string | null;
  direction: OpticalDirection;
  profile_id?: string | null;
  engineering_margin_db: number;
}

export interface BudgetLossStep {
  step_number: number;
  element_type: string;
  element_name: string;
  parameter_source: string;
  unit: string;
  individual_value: number;
  loss_db: number;
  accumulated_loss_db: number;
}

export interface BudgetCalculationResponse {
  status: "complete" | "insufficient_data" | string;
  direction: OpticalDirection;
  wavelength_nm?: number | null;
  topology_revision: number;
  assumptions: string[];
  missing_fields: string[];
  steps: BudgetLossStep[];
  total_loss_db?: number | null;
  tx_dbm?: number | null;
  predicted_rx_dbm?: number | null;
  rx_min_dbm?: number | null;
  rx_max_dbm?: number | null;
  engineering_margin_db: number;
  remaining_margin_db?: number | null;
  overload_headroom_db?: number | null;
  assessment: BudgetAssessment;
}
