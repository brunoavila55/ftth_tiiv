import { api } from "@/lib/api/client";
import type { PaginatedResult } from "@/lib/api/types";
import type { UserCreate, UserFilters, UserRead, UserUpdate } from "./types";

export * from "./types";

/**
 * Lista usuários cadastrados com suporte a paginação e busca textual
 */
export async function listUsers(
  params?: UserFilters,
  signal?: AbortSignal
): Promise<PaginatedResult<UserRead>> {
  const queryParams: Record<string, string | number> = {};
  if (params?.page) queryParams.page = params.page;
  if (params?.page_size) queryParams.page_size = params.page_size;
  if (params?.q) queryParams.q = params.q;

  return api.get<PaginatedResult<UserRead>>("/users", {
    params: queryParams,
    signal,
  });
}

/**
 * Consulta um usuário específico por ID
 */
export async function getUser(id: string, signal?: AbortSignal): Promise<UserRead> {
  return api.get<UserRead>(`/users/${id}`, { signal });
}

/**
 * Cadastra um novo operador ou administrador no sistema
 */
export async function createUser(payload: UserCreate): Promise<UserRead> {
  return api.post<UserRead>("/users", payload);
}

/**
 * Atualiza os dados de um usuário existente com controle de concorrência otimista (If-Match)
 */
export async function updateUser(
  id: string,
  payload: UserUpdate,
  version: number
): Promise<UserRead> {
  return api.patch<UserRead>(`/users/${id}`, payload, {
    headers: {
      "If-Match": `"${version}"`,
    },
  });
}

/**
 * Desativa/exclui logicamente um usuário do sistema
 */
export async function deleteUser(id: string): Promise<void> {
  return api.delete<void>(`/users/${id}`);
}
