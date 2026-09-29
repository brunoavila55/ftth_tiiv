import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RadioLinkFormDialog } from "@/features/wireless/components/radio-link-form-dialog";
import type { SiteRead } from "@/lib/api/types";
import type { DeviceRead } from "@/features/inventory/api";
import * as wirelessApi from "@/features/wireless/api";
import { getWirelessMapFeatures } from "@/features/wireless/map-api";
import { api } from "@/lib/api/client";

vi.mock("@/features/wireless/api", () => ({
  createRadioLink: vi.fn(),
  updateRadioLink: vi.fn(),
}));

const sites = [
  { id: "site-a", code: "WPOP-01", name: "POP", kind: "wireless_pop" },
  { id: "site-b", code: "TORRE-01", name: "Torre", kind: "radio_tower" },
] as SiteRead[];
const radios = [
  { id: "radio-a", code: "RADIO-01", manufacturer: "Fabricante", model: "A", site_id: "site-a", kind: "radio" },
  { id: "radio-b", code: "RADIO-02", manufacturer: "Fabricante", model: "B", site_id: "site-b", kind: "radio" },
] as DeviceRead[];

describe("Cadastro de enlace wireless", () => {
  it("consulta as feições na API exclusiva do mapa wireless", async () => {
    const response = { type: "FeatureCollection", features: [], bbox: [-53.01, -30.01, -52.99, -29.99], topology_revision: 1, truncated: false };
    const get = vi.spyOn(api, "get").mockResolvedValueOnce(response);

    await expect(getWirelessMapFeatures("-53.01,-30.01,-52.99,-29.99")).resolves.toEqual(response);
    expect(get).toHaveBeenCalledWith("/map/wireless/features", {
      params: { bbox: "-53.01,-30.01,-52.99,-29.99" },
      signal: undefined,
    });
  });

  it("associa cada rádio ao site da sua ponta e envia frequência em MHz", async () => {
    vi.mocked(wirelessApi.createRadioLink).mockResolvedValueOnce({ id: "link-1" } as Awaited<ReturnType<typeof wirelessApi.createRadioLink>>);
    const onSuccess = vi.fn();
    render(<RadioLinkFormDialog open onOpenChange={vi.fn()} sites={sites} radios={radios} onSuccess={onSuccess} />);

    fireEvent.change(screen.getByLabelText("Código *"), { target: { value: "ENLACE-01" } });
    fireEvent.change(screen.getByLabelText("Nome *"), { target: { value: "Tronco" } });
    fireEvent.change(document.getElementById("link-site-a")!, { target: { value: "site-a" } });
    fireEvent.change(document.getElementById("link-site-b")!, { target: { value: "site-b" } });
    expect((document.getElementById("link-radio-a") as HTMLSelectElement).options.length).toBe(2);
    expect((document.getElementById("link-radio-b") as HTMLSelectElement).options.length).toBe(2);
    fireEvent.change(document.getElementById("link-radio-a")!, { target: { value: "radio-a" } });
    fireEvent.change(document.getElementById("link-radio-b")!, { target: { value: "radio-b" } });
    fireEvent.change(screen.getByLabelText("Frequência (MHz) *"), { target: { value: "5800" } });
    fireEvent.change(screen.getByLabelText("Largura de canal (MHz) *"), { target: { value: "40" } });
    fireEvent.click(screen.getByRole("button", { name: "Cadastrar Enlace" }));

    await waitFor(() => expect(wirelessApi.createRadioLink).toHaveBeenCalledWith(expect.objectContaining({
      code: "ENLACE-01",
      site_a_id: "site-a",
      site_b_id: "site-b",
      radio_a_id: "radio-a",
      radio_b_id: "radio-b",
      frequency_mhz: 5800,
      channel_width_mhz: 40,
    })));
    expect(onSuccess).toHaveBeenCalled();
  });
});
