import { api } from "@/lib/api/client";
import { type PaginatedResponse } from "@/lib/api/types";
import { type Attachment, type AttachmentUploadPayload } from "./types";

export const ALLOWED_MIME_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
] as const;

export const MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function validateAttachmentFile(file: File): { valid: boolean; error?: string } {
  if (!file) {
    return { valid: false, error: "Nenhum arquivo selecionado" };
  }

  const fileType = file.type.toLowerCase();
  const fileName = file.name.toLowerCase();

  // Rejeição estrita de SVG/HTML mesmo que o cliente tente mascarar
  if (
    fileType.includes("svg") ||
    fileType.includes("html") ||
    fileName.endsWith(".svg") ||
    fileName.endsWith(".html") ||
    fileName.endsWith(".htm")
  ) {
    return {
      valid: false,
      error: "Arquivos SVG, scripts ou páginas HTML são proibidos por motivos de segurança.",
    };
  }

  // Verifica tipo permitido
  const isAllowed = ALLOWED_MIME_TYPES.some((mime) => fileType === mime);
  if (!isAllowed) {
    return {
      valid: false,
      error: "Tipo de arquivo não permitido. Apenas imagens (JPEG, PNG, WebP) e documentos PDF são aceitos.",
    };
  }

  // Verifica limite de tamanho
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return {
      valid: false,
      error: `Arquivo excede o limite máximo permitido de ${formatFileSize(MAX_UPLOAD_SIZE_BYTES)}.`,
    };
  }

  return { valid: true };
}

/**
 * Consulta anexos associados a uma entidade ou lista geral paginada
 */
export async function listAttachments(
  entityType?: string,
  entityId?: string,
  page: number = 1,
  pageSize: number = 50,
  signal?: AbortSignal
): Promise<PaginatedResponse<Attachment>> {
  return api.get<PaginatedResponse<Attachment>>("/attachments", {
    params: {
      entity_type: entityType,
      entity_id: entityId,
      page,
      page_size: pageSize,
    },
    signal,
  });
}

/**
 * Realiza upload com validação client-side e envio multipart seguro
 */
export async function uploadAttachment(
  payload: AttachmentUploadPayload,
  signal?: AbortSignal
): Promise<Attachment> {
  const validation = validateAttachmentFile(payload.file);
  if (!validation.valid) {
    throw new Error(validation.error || "Arquivo inválido para upload");
  }

  const formData = new FormData();
  formData.append("entity_id", payload.entity_id);
  formData.append("entity_type", payload.entity_type);
  formData.append("file", payload.file);

  if (payload.caption && payload.caption.trim()) {
    formData.append("caption", payload.caption.trim());
  }

  return api.post<Attachment>("/attachments", formData, { signal });
}

/**
 * Download de arquivo com autenticação, gerando Blob e revogando Object URL para evitar memory leak
 */
export async function downloadAttachmentBlob(attachmentId: string, fileName: string): Promise<void> {
  const response = await fetch(`/api/v1/attachments/${attachmentId}/download`, {
    method: "GET",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Falha no download do anexo (${response.status} ${response.statusText})`);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);

  try {
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = fileName || "anexo";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    // Revoga explicitamente a URL do Blob para liberar a memória
    URL.revokeObjectURL(objectUrl);
  }
}

/**
 * Exclusão de anexo exigindo cabeçalho de controle de versão If-Match
 */
export async function deleteAttachment(
  attachmentId: string,
  version: number,
  signal?: AbortSignal
): Promise<void> {
  await api.delete(`/attachments/${attachmentId}`, {
    headers: {
      "If-Match": String(version),
    },
    signal,
  });
}
