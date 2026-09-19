import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { NAVIGATION_GROUPS } from "@/lib/navigation";
import { PERMISSIONS, ROLE_PERMISSIONS } from "@/lib/permissions/rbac";

// R27 (EST-20): a matriz da UI é gerada do backend; contracts/permissions.json é o contrato.
const backend = JSON.parse(
  readFileSync(resolve(__dirname, "../../contracts/permissions.json"), "utf8")
) as Record<string, string[]>;

describe("paridade de permissões front × back", () => {
  it("cada papel tem exatamente as permissões do backend", () => {
    expect(Object.keys(ROLE_PERMISSIONS).sort()).toEqual(Object.keys(backend).sort());
    for (const [role, permissions] of Object.entries(backend)) {
      expect([...ROLE_PERMISSIONS[role as keyof typeof ROLE_PERMISSIONS]].sort()).toEqual(
        [...permissions].sort()
      );
    }
  });

  it("não existe permissão só no frontend (ex.: telemetry:write)", () => {
    const backendPermissions = new Set(Object.values(backend).flat());
    for (const permission of PERMISSIONS) {
      expect(backendPermissions.has(permission)).toBe(true);
    }
    expect(PERMISSIONS as readonly string[]).not.toContain("telemetry:write");
  });

  it("todo item de navegação declara uma permissão que existe", () => {
    const known = new Set<string>(PERMISSIONS);
    for (const group of NAVIGATION_GROUPS) {
      for (const item of group.items) {
        expect(item.permission, `${item.href} sem permission`).toBeDefined();
        expect(known.has(item.permission as string), `${item.href}: ${item.permission}`).toBe(true);
      }
    }
  });
});
