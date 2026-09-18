import type { components } from "@/lib/api/api-types";

export type UserRead = components["schemas"]["UserRead"];
export type UserCreate = components["schemas"]["UserCreate"];
export type UserUpdate = components["schemas"]["UserUpdate"];
export type UserRole = components["schemas"]["UserRole"];

export type { PaginatedResponse, PaginatedResult } from "@/lib/api/types";

export interface UserFilters {
  page?: number;
  page_size?: number;
  q?: string;
}

export const USER_ROLE_LABELS: Record<UserRole, { label: string; description: string }> = {
  admin: {
    label: "Administrador",
    description: "Acesso total à rede, inventário, configurações, auditoria e gestão de usuários.",
  },
  engineer: {
    label: "Engenheiro",
    description: "Criação e edição de topologia, fusões, orçamentos ópticos, clientes e medições.",
  },
  technician: {
    label: "Técnico de Campo",
    description: "Registro de medições ópticas, envio de fotos de campo e leitura do mapa.",
  },
  viewer: {
    label: "Visualizador",
    description: "Apenas consulta ao mapa operacional, cabos, caixas e relatórios consolidados.",
  },
};
