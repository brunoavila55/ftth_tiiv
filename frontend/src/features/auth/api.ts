import { api } from "@/lib/api/client";
import type {
  LoginRequest,
  LoginResponse,
  MeResponse,
  ChangePasswordRequest,
} from "@/lib/api/types";

/**
 * Obtém token CSRF do backend e configura cookie de segurança
 */
export async function getCsrf(): Promise<{ csrf_token: string }> {
  return api.get<{ csrf_token: string }>("/auth/csrf", { skipCsrf: true });
}

/**
 * Autentica usuário com e-mail e senha, define cookie HttpOnly de sessão e rotaciona CSRF
 */
export async function login(payload: LoginRequest): Promise<LoginResponse> {
  return api.post<LoginResponse>("/auth/login", payload);
}

/**
 * Invalida a sessão ativa no banco de dados e limpa os cookies seguros
 */
export async function logout(): Promise<void> {
  return api.post<void>("/auth/logout", {});
}

/**
 * Obtém os dados e permissões da sessão atualmente autenticada
 */
export async function getMe(): Promise<MeResponse> {
  return api.get<MeResponse>("/auth/me");
}

/**
 * Altera a senha do usuário atual mediante validação da senha atual
 */
export async function changePassword(payload: ChangePasswordRequest): Promise<void> {
  return api.post<void>("/auth/change-password", payload);
}
