import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
import { buildContentSecurityPolicy, middleware, config } from "@/middleware";

function directive(csp: string, name: string): string {
  const found = csp.split(";").map((d) => d.trim()).find((d) => d.startsWith(`${name} `));
  return found ?? "";
}

describe("CSP com nonce (SEC-11)", () => {
  it("script-src não permite unsafe-inline nem unsafe-eval em produção", () => {
    const csp = buildContentSecurityPolicy("abc123", false);
    const scriptSrc = directive(csp, "script-src");
    expect(scriptSrc).toContain("'nonce-abc123'");
    expect(scriptSrc).toContain("'strict-dynamic'");
    expect(scriptSrc).not.toContain("'unsafe-inline'");
    expect(scriptSrc).not.toContain("'unsafe-eval'");
    expect(csp).not.toContain("unsafe-eval");
  });

  it("mantém workers blob: (MapLibre) e apenas os hosts de tiles autorizados", () => {
    const csp = buildContentSecurityPolicy("n", false);
    expect(directive(csp, "worker-src")).toContain("blob:");
    expect(directive(csp, "connect-src")).toContain("https://*.tile.openstreetmap.org");
    expect(directive(csp, "connect-src")).toContain("https://*.basemaps.cartocdn.com");
    expect(directive(csp, "img-src")).toContain("https://*.basemaps.cartocdn.com");
    expect(directive(csp, "object-src")).toContain("'none'");
    expect(directive(csp, "frame-ancestors")).toContain("'self'");
  });

  it("unsafe-eval só existe em desenvolvimento (React Refresh)", () => {
    expect(directive(buildContentSecurityPolicy("n", true), "script-src")).toContain("'unsafe-eval'");
  });

  it("gera nonce único por resposta e o repassa ao Next na requisição", () => {
    const first = middleware(new NextRequest("http://localhost/login"));
    const second = middleware(new NextRequest("http://localhost/login"));
    const csp1 = first.headers.get("Content-Security-Policy") ?? "";
    const csp2 = second.headers.get("Content-Security-Policy") ?? "";
    const nonce = (csp: string) => /'nonce-([^']+)'/.exec(csp)?.[1];
    expect(nonce(csp1)).toBeTruthy();
    expect(nonce(csp1)).not.toBe(nonce(csp2));
    // o cabeçalho da requisição encaminhada carrega o mesmo CSP/nonce (o Next lê dele)
    expect(first.headers.get("x-middleware-request-content-security-policy")).toBe(csp1);
    expect(first.headers.get("x-middleware-request-x-nonce")).toBe(nonce(csp1));
  });

  it("não se aplica à API nem a assets estáticos", () => {
    const source = (config.matcher[0] as { source: string }).source;
    const re = new RegExp(`^${source}$`);
    expect(re.test("/login")).toBe(true);
    expect(re.test("/map")).toBe(true);
    expect(re.test("/api/v1/sites")).toBe(false);
    expect(re.test("/_next/static/chunk.js")).toBe(false);
  });
});
