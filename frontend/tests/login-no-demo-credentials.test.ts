import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// R26 (SEC-12): a tela de login não publica credenciais (o seed gera senha aleatória)
describe("login page", () => {
  it("não embute e-mail/senha de demonstração no bundle", () => {
    const source = readFileSync(resolve(__dirname, "../src/app/login/page.tsx"), "utf8");
    expect(source).not.toContain("AdminPass123!");
    expect(source).not.toContain("Credenciais de Demonstração");
    expect(source).not.toContain("admin@provedor.com.br");
  });
});
