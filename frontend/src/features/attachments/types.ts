export interface Attachment {
  id: string;
  entity_id: string;
  entity_type: string;
  file_name: string;
  mime_type: string;
  file_size_bytes: number;
  download_url: string;
  thumbnail_url: string | null;
  caption: string | null;
  checksum_sha256: string | null;
  user_id: string | null;
  version: number;
  created_at: string;
}

export interface AttachmentUploadPayload {
  entity_id: string;
  entity_type: string;
  caption?: string;
  file: File;
}

export interface AttachmentReconciliationResponse {
  total_disk_files: number;
  total_db_records: number;
  orphans_removed: string[];
  missing_disk_files: string[];
}
