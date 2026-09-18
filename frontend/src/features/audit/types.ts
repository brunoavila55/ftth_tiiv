export interface AuditEvent {
  id: string;
  actor_id: string | null;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  changes: Record<string, unknown>;
  reason: string | null;
  request_id: string | null;
  created_at: string;
}

export interface AuditFilterParams {
  entity_type?: string;
  entity_id?: string;
  actor_id?: string;
  action?: string;
  page?: number;
  page_size?: number;
}
