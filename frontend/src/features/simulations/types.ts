import type { BudgetCalculationResponse, OpticalDirection } from "../optical/types";

export type OverrideType = "loss_db" | "length_m" | "splitter_ratio";

export interface SimulationOverrideItem {
  element_id: string;
  override_type: OverrideType;
  new_value: number;
}

export interface OpticalSimulationRequest {
  service_link_id: string;
  direction?: OpticalDirection;
  engineering_margin_db?: number;
  overrides: SimulationOverrideItem[];
}

export interface OpticalSimulationResponse {
  baseline: BudgetCalculationResponse;
  simulated: BudgetCalculationResponse;
  delta_loss_db: number;
  delta_predicted_rx_dbm: number;
}

export interface ImpactAnalysisRequest {
  cable_segment_ids: string[];
  expected_topology_revision: number;
}

export interface ImpactedCustomerItem {
  customer_id: string;
  customer_code: string;
  service_link_id: string;
  onu_device_code: string;
  cto_code: string;
}

export interface ImpactAnalysisResponse {
  topology_revision: number;
  broken_segments_count: number;
  impacted_customers: ImpactedCustomerItem[];
  unaffected_customers_count: number;
  previously_disconnected_count: number;
  unknown_status_count: number;
  impacted_ctos: string[];
  impacted_pon_ports: string[];
}
