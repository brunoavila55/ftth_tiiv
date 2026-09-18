import { describe, expect, it, vi, beforeEach } from "vitest";
import { ApiClient } from "@/lib/api/client";
import { ApiError } from "@/lib/api/types";
import { formatLossDb, formatMeters, formatPowerDbm, formatWavelength } from "@/lib/format/units";
import { hasPermission } from "@/lib/permissions/rbac";

describe("ApiClient & RFC 7807 Problem Details (Critérios de Aceite F01)", () => {
  let client: ApiClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    client = new ApiClient("/api/v1");
  });

  it("trata 401 Unauthorized lançando ApiError tipada e sem engolir erro", async () => {
    const mockProblem = {
      type: "about:blank",
      title: "Não autenticado",
      status: 401,
      detail: "Sessão expirada ou credenciais ausentes",
      code: "unauthorized",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/problem+json" }),
      json: async () => mockProblem,
    });

    await expect(client.get("/sites")).rejects.toThrowError(ApiError);

    try {
      await client.get("/sites");
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(401);
      expect(apiErr.code).toBe("unauthorized");
      expect(apiErr.detail).toBe("Sessão expirada ou credenciais ausentes");
    }
  });

  it("trata 409 Conflict estruturado (ex: topology_revision_conflict ou terminal_already_connected)", async () => {
    const mockProblem = {
      type: "about:blank",
      title: "Conflito de revisão topológica",
      status: 409,
      detail: "A revisão topológica esperada (2) diverge da atual (3).",
      code: "topology_revision_conflict",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      headers: new Headers({ "content-type": "application/problem+json" }),
      json: async () => mockProblem,
    });

    await expect(client.post("/connections/batch", {})).rejects.toThrowError(ApiError);

    try {
      await client.post("/connections/batch", {});
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(409);
      expect(apiErr.code).toBe("topology_revision_conflict");
    }
  });

  it("trata 412 Precondition Failed quando If-Match diverge", async () => {
    const mockProblem = {
      type: "about:blank",
      title: "Precondição falhou",
      status: 412,
      detail: "O recurso foi modificado concorrentemente.",
      code: "precondition_failed",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 412,
      headers: new Headers({ "content-type": "application/problem+json" }),
      json: async () => mockProblem,
    });

    try {
      await client.delete("/connections/123", { headers: { "If-Match": '"1"' } });
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(412);
      expect(apiErr.code).toBe("precondition_failed");
    }
  });

  it("trata 422 Unprocessable Entity preservando a lista de erros por campo", async () => {
    const mockProblem = {
      type: "about:blank",
      title: "Erro de validação",
      status: 422,
      detail: "Dados inválidos",
      code: "validation_error",
      errors: [
        { field: "loss_db", code: "greater_than_equal", message: "Perda deve ser maior ou igual a 0" },
      ],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers({ "content-type": "application/problem+json" }),
      json: async () => mockProblem,
    });

    try {
      await client.post("/connections", { loss_db: -1 });
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(422);
      expect(apiErr.errors).toBeDefined();
      expect(apiErr.errors?.[0].field).toBe("loss_db");
    }
  });

  it("garante cancelamento com AbortSignal sem converter erro em lista vazia", async () => {
    const controller = new AbortController();

    global.fetch = vi.fn().mockImplementation((_url, options) => {
      return new Promise((_, reject) => {
        if (options.signal) {
          options.signal.addEventListener("abort", () => {
            reject(new DOMException("Operação cancelada pelo usuário", "AbortError"));
          });
        }
      });
    });

    const promise = client.get("/map/features", { signal: controller.signal });
    controller.abort();

    await expect(promise).rejects.toThrow("Operação cancelada pelo usuário");
  });

  it("nunca converte falhas de rede em lista vazia silenciosa", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network connection reset"));

    const resultPromise = client.get<unknown[]>("/cables");
    await expect(resultPromise).rejects.toThrow(ApiError);
  });
});

describe("Formatadores de unidades ópticas físicas", () => {
  it("formata metros e quilômetros corretamente", () => {
    expect(formatMeters(150.5)).toContain("150,5");
    expect(formatMeters(2500, { showKm: true })).toContain("2,5");
    expect(formatMeters(null)).toBe("Não informado");
    expect(formatMeters(undefined)).toBe("Não informado");
  });

  it("formata atenuação em dB e potência em dBm", () => {
    expect(formatLossDb(0.1)).toContain("0,10 dB");
    expect(formatLossDb(null)).toBe("Não informado");

    expect(formatPowerDbm(-19.5)).toContain("-19,50 dBm");
    expect(formatPowerDbm(3.0)).toContain("+3,00 dBm");
    expect(formatPowerDbm(null)).toBe("Não informado");
  });

  it("formata comprimento de onda em nanômetros", () => {
    expect(formatWavelength(1310)).toBe("1310 nm");
    expect(formatWavelength(1490)).toBe("1490 nm");
    expect(formatWavelength(null)).toBe("Não informado");
  });
});

describe("Matriz RBAC granular", () => {
  it("valida permissões por papel", () => {
    expect(hasPermission("viewer", "network:read")).toBe(true);
    expect(hasPermission("viewer", "network:write")).toBe(false);

    expect(hasPermission("technician", "network:read")).toBe(true);
    expect(hasPermission("technician", "network:write")).toBe(false);

    expect(hasPermission("engineer", "network:write")).toBe(true);
    expect(hasPermission("admin", "users:write")).toBe(true);
  });
});
