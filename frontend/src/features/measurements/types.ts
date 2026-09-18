export type MeasurementOrigin = "manual_entry" | "field_power_meter" | "otdr";

export type MeasurementDirection = "downstream" | "upstream";

export interface MeasurementRead {
  id: string;
  terminal_id: string;
  service_link_id: string | null;
  power_dbm: number;
  wavelength_nm: number;
  direction: MeasurementDirection;
  origin: MeasurementOrigin;
  instrument_model: string | null;
  measured_at: string;
  user_id: string | null;
  predicted_power_dbm: number | null;
  excess_loss_db: number | null;
  topology_revision: number | null;
  notes: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MeasurementCreate {
  terminal_id: string;
  service_link_id?: string | null;
  power_dbm: number;
  wavelength_nm: number;
  direction: MeasurementDirection;
  origin?: MeasurementOrigin;
  instrument_model?: string | null;
  measured_at?: string | null;
  notes?: string | null;
}

export interface MeasurementUpdate {
  notes?: string | null;
}

export interface MeasurementComparisonResponse {
  measurement_id: string;
  measured_power_dbm: number;
  predicted_power_dbm: number | null;
  excess_loss_db: number | null;
  wavelength_nm: number;
  direction: MeasurementDirection;
  tolerance_db: number;
  is_within_tolerance: boolean;
  is_compatible: boolean;
  incompatibility_reason: string | null;
  topology_revision: number | null;
}
