import { api } from "@/lib/api/client";
import { type PaginatedResponse } from "@/lib/api/types";
import { type AuditEvent, type AuditFilterParams } from "./types";

/**
 * Consulta a trilha append-only de eventos de auditoria com paginação e filtros
 */
export async function listAuditEvents(
  params?: AuditFilterParams,
  signal?: AbortSignal
): Promise<PaginatedResponse<AuditEvent>> {
  return api.get<PaginatedResponse<AuditEvent>>("/audit-events", {
    params: {
      entity_type: params?.entity_type,
      entity_id: params?.entity_id,
      actor_id: params?.actor_id,
      action: params?.action,
      page: params?.page || 1,
      page_size: params?.page_size || 50,
    },
    signal,
  });
}

/**
 * Rótulos humanos e cores temáticas para cada tipo de ação de auditoria
 */
export function formatAuditAction(action: string): {
  label: string;
  variant: "default" | "secondary" | "destructive" | "outline";
} {
  const norm = action.toLowerCase();

  if (norm.includes("create") || norm.includes("upload") || norm.includes("add")) {
    return { label: "Criação / Cadastro", variant: "default" };
  }
  if (norm.includes("delete") || norm.includes("remove") || norm.includes("disconnect")) {
    return { label: "Exclusão / Desconexão", variant: "destructive" };
  }
  if (norm.includes("update") || norm.includes("edit") || norm.includes("modify")) {
    return { label: "Atualização", variant: "secondary" };
  }
  if (norm.includes("connect") || norm.includes("splice") || norm.includes("link")) {
    return { label: "Conexão de Rede", variant: "default" };
  }

  return { label: action, variant: "outline" };
}

/**
 * Rótulos legíveis para tipos de entidades
 */
export function formatAuditEntityType(entityType: string): string {
  const map: Record<string, string> = {
    site: "POP / Site",
    structure: "Estrutura / Caixa",
    cable: "Cabo Óptico",
    connection: "Conexão / Fusão",
    customer: "Cliente",
    service_link: "Atendimento",
    attachment: "Anexo / Foto",
    optical_measurement: "Medição de Potência",
    user: "Usuário",
    device: "Equipamento",
    terminal: "Terminal Óptico",
  };

  return map[entityType.toLowerCase()] || entityType;
}
