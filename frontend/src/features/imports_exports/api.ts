import { api } from "@/lib/api/client";
import type {
  CollisionStrategy,
  ExportRequest,
  ExportResponse,
  ImportCommitResponse,
  ImportPreviewResponse,
  JobRead,
} from "./types";

/**
 * Envia arquivo (GeoJSON, KML ou CSV) para pré-visualização e detecção de colisões
 */
export async function createImportPreview(
  file: File,
  signal?: AbortSignal
): Promise<ImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return api.post<ImportPreviewResponse>("/imports/preview", formData, {
    signal,
  });
}

/**
 * Consulta resultado detalhado de uma prévia de importação pelo ID
 */
export async function getImportPreview(
  importId: string,
  signal?: AbortSignal
): Promise<ImportPreviewResponse> {
  return api.get<ImportPreviewResponse>(`/imports/${importId}`, { signal });
}

/**
 * Confirma a importação de dados gerando um job assíncrono idempotente
 */
export async function commitImport(
  importId: string,
  collisionStrategy: CollisionStrategy,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<ImportCommitResponse> {
  return api.post<ImportCommitResponse>(
    `/imports/${importId}/commit`,
    { collision_strategy: collisionStrategy },
    {
      headers: {
        "Idempotency-Key": idempotencyKey,
      },
      signal,
    }
  );
}

/**
 * Consulta status atualizado de um job assíncrono no backend
 */
export async function getJob(jobId: string, signal?: AbortSignal): Promise<JobRead> {
  return api.get<JobRead>(`/jobs/${jobId}`, { signal });
}

/**
 * Solicita o cancelamento gracioso de um job assíncrono em execução
 */
export async function cancelJob(jobId: string, signal?: AbortSignal): Promise<JobRead> {
  return api.post<JobRead>(`/jobs/${jobId}/cancel`, {}, { signal });
}

/**
 * Registra solicitação de exportação de dados vetoriais/cadastrais
 */
export async function requestExport(
  payload: ExportRequest,
  signal?: AbortSignal
): Promise<ExportResponse> {
  return api.post<ExportResponse>("/exports", payload, { signal });
}

/**
 * Consulta status da exportação pelo exportId (alias para o job da exportação)
 */
export async function getExportStatus(
  exportId: string,
  signal?: AbortSignal
): Promise<JobRead> {
  return api.get<JobRead>(`/exports/${exportId}`, { signal });
}

/**
 * Realiza download autorizado do arquivo exportado com revogação imediata de Object URL
 */
export async function downloadExportBlob(
  exportId: string,
  fallbackFilename?: string
): Promise<void> {
  const response = await fetch(`/api/v1/exports/${exportId}/download`, {
    method: "GET",
    credentials: "include",
  });

  if (response.status === 410) {
    throw new Error("O arquivo exportado expirou ou foi removido do servidor.");
  }

  if (!response.ok) {
    throw new Error(
      `Falha ao baixar arquivo de exportação (${response.status} ${response.statusText})`
    );
  }

  // Tenta extrair filename do Content-Disposition
  let filename = fallbackFilename || `export_${exportId.slice(0, 8)}`;
  const disposition = response.headers.get("content-disposition");
  if (disposition && disposition.includes("filename=")) {
    const match = disposition.match(/filename=["']?([^"';]+)["']?/);
    if (match?.[1]) {
      filename = match[1];
    }
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    URL.revokeObjectURL(downloadUrl);
  }
}
