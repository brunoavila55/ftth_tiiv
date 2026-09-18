import { ApiError, type ProblemDetails } from "./types";
import { getCsrfToken, setCachedCsrfToken } from "./csrf";

export interface RequestOptions {
  params?: Record<string, string | number | boolean | null | undefined>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  skipCsrf?: boolean;
  timeoutMs?: number;
}

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = "/api/v1") {
    this.baseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  }

  private buildUrl(path: string, params?: Record<string, string | number | boolean | null | undefined>): string {
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    const urlString = `${this.baseUrl}${cleanPath}`;

    if (!params || Object.keys(params).length === 0) {
      return urlString;
    }

    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined) {
        searchParams.append(key, String(value));
      }
    }

    const queryString = searchParams.toString();
    if (!queryString) {
      return urlString;
    }

    const separator = urlString.includes("?") ? "&" : "?";
    return `${urlString}${separator}${queryString}`;
  }

  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = this.buildUrl(path, options.params);
    const headers = new Headers(options.headers || {});

    const isMutation = ["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase());
    if (isMutation && !options.skipCsrf) {
      let csrfToken = getCsrfToken();
      if (!csrfToken && path !== "/auth/csrf") {
        try {
          const csrfData = await this.request<{ csrf_token: string }>(
            "GET",
            "/auth/csrf",
            undefined,
            { skipCsrf: true }
          );
          if (csrfData?.csrf_token) {
            setCachedCsrfToken(csrfData.csrf_token);
            csrfToken = csrfData.csrf_token;
          }
        } catch {
          // Mantém fluxo original em caso de falha de conectividade
        }
      }
      if (csrfToken && !headers.has("X-CSRF-Token")) {
        headers.set("X-CSRF-Token", csrfToken);
      }
    }

    let requestBody: BodyInit | undefined;
    if (body !== undefined && body !== null) {
      if (typeof FormData !== "undefined" && body instanceof FormData) {
        requestBody = body;
      } else if (typeof body === "string") {
        requestBody = body;
        if (!headers.has("Content-Type")) {
          headers.set("Content-Type", "application/json");
        }
      } else {
        requestBody = JSON.stringify(body);
        if (!headers.has("Content-Type")) {
          headers.set("Content-Type", "application/json");
        }
      }
    }

    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let abortListener: (() => void) | undefined;
    const internalController = new AbortController();

    if (options.signal) {
      if (options.signal.aborted) {
        throw new DOMException("Operação cancelada pelo usuário", "AbortError");
      }
      abortListener = () => internalController.abort();
      options.signal.addEventListener("abort", abortListener);
    }

    if (options.timeoutMs && options.timeoutMs > 0) {
      timeoutId = setTimeout(() => {
        internalController.abort();
      }, options.timeoutMs);
    }

    // Bloqueio imediato de mutações quando offline para evitar falso salvamento
    if (
      typeof navigator !== "undefined" &&
      navigator.onLine === false &&
      method !== "GET" &&
      method !== "HEAD"
    ) {
      throw new ApiError(
        0,
        {
          title: "Sem conexão de rede",
          detail:
            "Ação bloqueada: o dispositivo está offline. As alterações e rascunhos foram mantidos em memória para evitar falso salvamento.",
        },
        "Dispositivo offline — alteração bloqueada"
      );
    }

    let response: Response;
    try {
      response = await fetch(url, {
        method,
        headers,
        body: requestBody,
        credentials: "include",
        signal: options.signal || internalController.signal,
      });
    } catch (err: unknown) {
      if (
        (err instanceof DOMException && err.name === "AbortError") ||
        (err as Error)?.name === "AbortError"
      ) {
        throw err;
      }
      const message = err instanceof Error ? err.message : "Erro de conexão de rede";
      throw new ApiError(0, { title: "Falha de rede", detail: message }, message);
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
      if (options.signal && abortListener) {
        options.signal.removeEventListener("abort", abortListener);
      }
    }

    if (!response.ok) {
      const contentType = response.headers.get("content-type") || "";
      let problem: Partial<ProblemDetails> = {};

      if (contentType.includes("json")) {
        try {
          problem = await response.json();
        } catch {
          problem = { title: response.statusText, detail: "Falha ao decodificar resposta JSON" };
        }
      } else {
        const text = await response.text().catch(() => "");
        problem = { title: response.statusText, detail: text || response.statusText };
      }

      throw new ApiError(response.status, problem);
    }

    if (response.status === 204) {
      return undefined as unknown as T;
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("json")) {
      return (await response.json()) as T;
    }

    return (await response.text()) as unknown as T;
  }

  async get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("GET", path, undefined, options);
  }

  async post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, body, options);
  }

  async put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("PUT", path, body, options);
  }

  async patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("PATCH", path, body, options);
  }

  async delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("DELETE", path, undefined, options);
  }
}

export const api = new ApiClient("/api/v1");
