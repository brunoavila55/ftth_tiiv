import * as React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SplitterFormDialog } from "@/features/splitters/components/splitter-form-dialog";
import { SplittersPanel } from "@/features/splitters/components/splitters-panel";
import * as splitterApi from "@/features/splitters/api";

vi.mock("@/features/auth/auth-context", () => import("./support/auth-context-mock"));
vi.mock("@/features/splitters/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/splitters/api")>();
  return {
    ...actual,
    listSplitters: vi.fn(),
    createSplitter: vi.fn(),
    updateSplitter: vi.fn(),
    deleteSplitter: vi.fn(),
  };
});

const splitter: splitterApi.SplitterRead = {
  id: "10000000-0000-0000-0000-000000000001",
  code: "SPL-CTO-01",
  structure_id: "20000000-0000-0000-0000-000000000001",
  device_id: null,
  ratio: "1:2",
  output_ports_count: 2,
  input_terminal_id: "30000000-0000-0000-0000-000000000001",
  ports: [
    {
      port_number: 0,
      is_input: true,
      terminal_id: "30000000-0000-0000-0000-000000000001",
      loss_1310_db: null,
      loss_1490_db: null,
      loss_1550_db: null,
    },
    {
      port_number: 1,
      is_input: false,
      terminal_id: "30000000-0000-0000-0000-000000000002",
      loss_1310_db: 3.6,
      loss_1490_db: 3.6,
      loss_1550_db: 3.6,
    },
    {
      port_number: 2,
      is_input: false,
      terminal_id: "30000000-0000-0000-0000-000000000003",
      loss_1310_db: 3.7,
      loss_1490_db: 3.7,
      loss_1550_db: 3.7,
    },
  ],
  notes: "Splitter principal",
  version: 1,
  created_at: "2026-09-20T18:00:00Z",
  updated_at: "2026-09-20T18:00:00Z",
};

function renderWithQueryClient(element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
  );
}

describe("gestão de splitters", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(splitterApi.listSplitters).mockResolvedValue({
      items: [splitter],
      total: 1,
      page: 1,
      page_size: 100,
    });
  });

  it("lista razão, saídas e faixa de perda da estrutura", async () => {
    renderWithQueryClient(
      <SplittersPanel structureId="20000000-0000-0000-0000-000000000001" />
    );

    expect(await screen.findByText("SPL-CTO-01")).toBeTruthy();
    expect(screen.getByText("1:2")).toBeTruthy();
    expect(screen.getByText("3.60–3.70 dB")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Editar SPL-CTO-01" })).toBeTruthy();
  });

  it("cadastra splitter balanceado com perdas para todas as saídas", async () => {
    vi.mocked(splitterApi.createSplitter).mockResolvedValue(splitter);
    const onSuccess = vi.fn();
    const onOpenChange = vi.fn();
    renderWithQueryClient(
      <SplitterFormDialog
        open
        onOpenChange={onOpenChange}
        structureId="20000000-0000-0000-0000-000000000001"
        onSuccess={onSuccess}
      />
    );

    fireEvent.change(screen.getByLabelText("Código *"), {
      target: { value: "SPL-CTO-01" },
    });
    fireEvent.change(screen.getByLabelText("Razão"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Cadastrar splitter" }));

    await waitFor(() => expect(splitterApi.createSplitter).toHaveBeenCalledOnce());
    expect(splitterApi.createSplitter).toHaveBeenCalledWith(
      expect.objectContaining({
        code: "SPL-CTO-01",
        ratio: "1:2",
        output_ports_count: 2,
        ports: [
          expect.objectContaining({ port_number: 1, loss_1490_db: 3.6 }),
          expect.objectContaining({ port_number: 2, loss_1490_db: 3.6 }),
        ],
      })
    );
    expect(onSuccess).toHaveBeenCalledWith(splitter);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
