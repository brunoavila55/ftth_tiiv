import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/types";
import { StructureDetailView } from "@/features/inventory/components/structure-detail-view";
import * as inventoryApi from "@/features/inventory/api";

vi.mock("@/features/auth/auth-context", () => import("./support/auth-context-mock"));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/splitters/components/splitters-panel", () => ({ SplittersPanel: () => null }));
vi.mock("@/features/customers/components/cto-ports-grid", () => ({ CtoPortsGrid: () => null }));
vi.mock("@/features/connectivity/components/fusion-editor", () => ({ FusionEditor: () => null }));
vi.mock("@/features/inventory/components/devices-table", () => ({ DevicesTable: () => null }));
vi.mock("@/features/inventory/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/inventory/api")>()),
  getStructure: vi.fn().mockResolvedValue({
    id: "cto-1",
    code: "CTO-01",
    kind: "cto",
    location: { type: "Point", coordinates: [-53, -30] },
    capacity: 8,
    status: "installed",
    condition: "ok",
    version: 1,
  }),
  listPorts: vi.fn().mockResolvedValue({
    items: [{ id: "port-1", name: "P1", role: "client_access", version: 3 }],
    total: 1,
  }),
  listDevices: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  deletePort: vi.fn(),
}));

describe("Exclusão de porta da CTO", () => {
  it("oferece a ação e explica quando a porta ainda está vinculada", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(inventoryApi.deletePort).mockRejectedValueOnce(
      new ApiError(409, { detail: "A porta possui conexões ópticas ativas." })
    );

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <StructureDetailView structureId="cto-1" />
      </QueryClientProvider>
    );

    fireEvent.click(await screen.findByRole("button", { name: /Portas de Atendimento/i }));
    fireEvent.click(await screen.findByText(/Gerenciar portas cadastradas/i));
    fireEvent.click(screen.getByRole("button", { name: "Excluir porta P1" }));

    await waitFor(() => {
      expect(inventoryApi.deletePort).toHaveBeenCalledWith("port-1", 3);
      expect(screen.getByRole("alert").textContent).toContain("conexões ópticas ativas");
    });
  });
});
