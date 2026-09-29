import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/types";
import { CableDetailView } from "@/features/cables/components/cable-detail-view";
import * as cablesApi from "@/features/cables/api";

vi.mock("@/features/auth/auth-context", () => import("./support/auth-context-mock"));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/inventory/api", () => ({
  listStructures: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}));
vi.mock("@/features/cables/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/cables/api")>()),
  getCable: vi.fn().mockResolvedValue({
    id: "cable-1",
    code: "CAB-01",
    model: "Cabo 12F",
    fiber_count: 12,
    tube_count: 1,
    color_standard: "NBR",
    status: "installed",
    version: 1,
  }),
  listCableSegments: vi.fn().mockResolvedValue({
    items: [{
      id: "segment-1",
      cable_id: "cable-1",
      origin_structure_id: "structure-1",
      destination_structure_id: "structure-2",
      geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] },
      map_length_m: 100,
      measured_length_m: null,
      slack_length_m: 0,
      effective_length_m: 100,
      length_source: "calculated",
      version: 1,
    }],
    total: 1,
  }),
  deleteCableSegment: vi.fn(),
}));

describe("Exclusão de trecho de cabo", () => {
  it("mostra o motivo retornado pela API quando há conexões ativas", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(cablesApi.deleteCableSegment).mockRejectedValueOnce(
      new ApiError(409, {
        detail: "Não é possível remover o trecho pois existem conexões ópticas ativas em suas fibras.",
      })
    );

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <CableDetailView cableId="cable-1" />
      </QueryClientProvider>
    );

    fireEvent.click(await screen.findByRole("button", { name: /Segmentos \(Trechos\)/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Excluir Trecho" }));

    await waitFor(() => {
      expect(cablesApi.deleteCableSegment).toHaveBeenCalledWith("segment-1", 1);
      expect(screen.getByRole("alert").textContent).toContain("conexões ópticas ativas");
    });
  });
});
