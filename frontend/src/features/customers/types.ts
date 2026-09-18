// ==============================================================================
// CUSTOMERS & SERVICE LINKS TYPES (Contratos F11 / B08)
// ==============================================================================

export type ServiceLinkStatus = "active" | "deactivated" | "suspended";

export type CtoPortStatus =
  | "free"
  | "customer_connected"
  | "connected_no_customer"
  | "reserved";

export interface CustomerRead {
  id: string;
  code: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreate {
  code: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
}

export interface CustomerUpdate {
  name?: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
}

export interface ServiceLinkRead {
  id: string;
  customer_id: string;
  onu_device_id: string;
  port_id: string;
  status: ServiceLinkStatus;
  activated_at: string;
  deactivated_at?: string | null;
  notes?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ServiceLinkCreate {
  customer_id: string;
  onu_device_id: string;
  port_id: string;
  notes?: string | null;
}

export interface ServiceLinkUpdate {
  status?: ServiceLinkStatus;
  notes?: string | null;
}

export interface CtoPortCustomerSummary {
  id: string;
  code: string;
  name: string;
  phone?: string | null;
  email?: string | null;
}

export interface CtoPortOnuSummary {
  id: string;
  code: string;
  serial_number?: string | null;
  model?: string | null;
}

export interface CtoPortReservationSummary {
  id: string;
  reason: string;
  reserved_by?: string | null;
  expires_at?: string | null;
}

export interface CtoPortServiceLinkSummary {
  id: string;
  status: string;
  activated_at: string;
  version: number;
  notes?: string | null;
}

export interface CtoPortDetail {
  id: string;
  name: string;
  role: string;
  connector_type: string;
  status: CtoPortStatus;
  is_damaged: boolean;
  terminal_id?: string | null;
  notes?: string | null;
  service_link?: CtoPortServiceLinkSummary | null;
  customer?: CtoPortCustomerSummary | null;
  onu?: CtoPortOnuSummary | null;
  reservation?: CtoPortReservationSummary | null;
}

export interface CtoPortOccupancy {
  structure_id: string;
  total_ports: number;
  occupied_ports: number;
  reserved_ports: number;
  free_ports: number;
  connected_without_customer: number;
  ports: CtoPortDetail[];
}
