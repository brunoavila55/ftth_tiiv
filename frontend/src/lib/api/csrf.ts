const CSRF_COOKIE_NAME = "ftth_csrf_token";

let cachedCsrfToken: string | null = null;

export function getCsrfTokenFromCookie(): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const match = document.cookie.match(new RegExp(`(^|;\\s*)(${CSRF_COOKIE_NAME})=([^;]*)`));
  return match ? decodeURIComponent(match[3]) : null;
}

export function setCachedCsrfToken(token: string | null): void {
  cachedCsrfToken = token;
}

export function getCsrfToken(): string | null {
  return getCsrfTokenFromCookie() || cachedCsrfToken;
}
