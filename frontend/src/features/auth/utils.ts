/**
 * Valida e sanitiza um caminho de retorno (returnUrl / redirect) para evitar vulnerabilidades de Open Redirect.
 *
 * Regras:
 * - Deve começar com uma barra única `/`
 * - Não pode começar com `//` (evita protocol-relative URLs)
 * - Não pode conter esquemas como `http:`, `https:`, `javascript:`, `data:`
 * - Se for inválido, vazio ou suspeito, retorna o fallback seguro `/`
 */
export function sanitizeReturnUrl(returnUrl?: string | null, fallback = "/"): string {
  if (!returnUrl || typeof returnUrl !== "string") {
    return fallback;
  }

  const trimmed = returnUrl.trim();

  // Verifica se começa com uma barra única
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return fallback;
  }

  // Verifica se contém ":" antes da primeira barra seguinte ou parâmetros perigosos
  if (trimmed.includes("://") || trimmed.includes("javascript:") || trimmed.includes("data:")) {
    return fallback;
  }

  try {
    // Valida parsing relativo garantindo que o host permaneça localhost/dummy
    const parsed = new URL(trimmed, "http://localhost");
    if (parsed.origin !== "http://localhost") {
      return fallback;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}
