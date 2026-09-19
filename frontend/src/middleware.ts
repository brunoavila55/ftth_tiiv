import { NextResponse, type NextRequest } from "next/server";

/**
 * Content-Security-Policy por resposta, com nonce (SEC-11).
 *
 * script-src NÃO tem 'unsafe-inline' nem 'unsafe-eval': só scripts do próprio site, os que
 * carregam o nonce desta resposta (o Next aplica o nonce aos seus scripts a partir do cabeçalho
 * CSP da requisição) e os carregados por eles ('strict-dynamic'). O MapLibre precisa de workers
 * `blob:`. 'unsafe-eval' só existe em desenvolvimento (React Refresh).
 */
const TILE_HOSTS = "https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com";

export function buildContentSecurityPolicy(nonce: string, isDev: boolean): string {
  const scriptSrc = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"];
  if (isDev) scriptSrc.push("'unsafe-eval'");

  return [
    "default-src 'self'",
    `script-src ${scriptSrc.join(" ")}`,
    "worker-src 'self' blob:",
    "child-src 'self' blob:",
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: ${TILE_HOSTS}`,
    `connect-src 'self' blob: ${TILE_HOSTS}`,
    "font-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
  ].join("; ");
}

export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const csp = buildContentSecurityPolicy(nonce, process.env.NODE_ENV === "development");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
