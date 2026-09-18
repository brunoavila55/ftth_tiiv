import { describe, it, expect, vi } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  parsePtBrNumber,
  formatPtBrNumber,
  isStrictZero,
  NumberFormatError,
} from "@/lib/format/numbers";
import { StatusBadge } from "@/components/ui/status-badge";
import { EntityLink } from "@/components/ui/entity-link";
import { UnitInput } from "@/components/ui/unit-input";
import { CoordinateInput } from "@/components/ui/coordinate-input";
import { ConflictDialog } from "@/components/ui/conflict-dialog";
import { DataTable } from "@/components/ui/data-table/data-table";
import type { ColumnDef } from "@tanstack/react-table";

describe("Conversão e Formatação Numérica pt-BR (F04)", () => {
  it("converte strings com vírgula para número float padrão", () => {
    expect(parsePtBrNumber("12,5")).toBe(12.5);
    expect(parsePtBrNumber("0,35")).toBe(0.35);
    expect(parsePtBrNumber("-23,5505")).toBe(-23.5505);
  });

  it("aceita strings com ponto decimal padrão", () => {
    expect(parsePtBrNumber("12.5")).toBe(12.5);
    expect(parsePtBrNumber("100.0")).toBe(100);
  });

  it("aceita formato brasileiro com ponto de milhar e vírgula decimal", () => {
    expect(parsePtBrNumber("1.234,56")).toBe(1234.56);
    expect(parsePtBrNumber("10.500,75")).toBe(10500.75);
  });

  it("distingue estritamente zero (0) de nulo, indefinido e NaN", () => {
    expect(parsePtBrNumber("0")).toBe(0);
    expect(parsePtBrNumber("0,0")).toBe(0);
    expect(parsePtBrNumber(0)).toBe(0);

    expect(isStrictZero(0)).toBe(true);
    expect(isStrictZero("0")).toBe(true);
    expect(isStrictZero("0,00")).toBe(true);

    expect(isStrictZero(null)).toBe(false);
    expect(isStrictZero(undefined)).toBe(false);
    expect(isStrictZero(NaN)).toBe(false);
    expect(isStrictZero("")).toBe(false);

    // parsePtBrNumber retorna null apenas para ausência real de valor
    expect(parsePtBrNumber(null)).toBeNull();
    expect(parsePtBrNumber(undefined)).toBeNull();
    expect(parsePtBrNumber("")).toBeNull();
    expect(parsePtBrNumber("   ")).toBeNull();
  });

  it("rejeita formatos ambíguos ou inválidos com NumberFormatError", () => {
    expect(() => parsePtBrNumber("1.2.3")).toThrow(NumberFormatError);
    expect(() => parsePtBrNumber("12,34,56")).toThrow(NumberFormatError);
    expect(() => parsePtBrNumber("abc")).toThrow(NumberFormatError);
  });

  it("formata números em pt-BR com vírgula e casas decimais configuráveis", () => {
    expect(formatPtBrNumber(12.5)).toBe("12,5");
    expect(formatPtBrNumber(12.5, { minDecimals: 2, maxDecimals: 2 })).toBe("12,50");
    expect(formatPtBrNumber(null)).toBe("—");
    expect(formatPtBrNumber(undefined)).toBe("—");
    expect(formatPtBrNumber(0)).toBe("0");
  });
});

describe("StatusBadge Óptico Semântico", () => {
  it("renderiza corretamente os rótulos e variantes de status óptico", () => {
    const { rerender } = render(<StatusBadge status="free" />);
    expect(screen.getByText("Livre")).toBeDefined();

    rerender(<StatusBadge status="connected" />);
    expect(screen.getByText("Conectada")).toBeDefined();

    rerender(<StatusBadge status="reserved" />);
    expect(screen.getByText("Reservada")).toBeDefined();

    rerender(<StatusBadge status="damaged" />);
    expect(screen.getByText("Danificada")).toBeDefined();

    rerender(<StatusBadge status="unknown" />);
    expect(screen.getByText("Não documentada")).toBeDefined();
  });
});

describe("EntityLink", () => {
  it("renderiza link para entidade com rota padronizada e texto legível", () => {
    render(
      <EntityLink
        type="site"
        id="11111111-1111-1111-1111-111111111111"
        code="POP-CENTRO"
        name="POP Central"
      />
    );

    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("/sites/11111111-1111-1111-1111-111111111111");
    expect(screen.getByText("POP-CENTRO — POP Central")).toBeDefined();
  });
});

describe("UnitInput", () => {
  it("renderiza input com unidade física visível e aria-describedby", () => {
    const handleChange = vi.fn();
    render(
      <UnitInput
        unit="dB"
        value="3,25"
        onChange={handleChange}
        placeholder="0,00"
      />
    );

    expect(screen.getByText("dB")).toBeDefined();
    const input = screen.getByDisplayValue("3,25");
    expect(input.getAttribute("aria-describedby")).toContain("unit");

    fireEvent.change(input, { target: { value: "3,50" } });
    expect(handleChange).toHaveBeenCalledWith("3,50");
  });
});

describe("CoordinateInput", () => {
  it("valida latitude e longitude e permite inversão rápida", () => {
    const handleChange = vi.fn();
    render(
      <CoordinateInput
        value={{ lat: -23.55052, lon: -46.6333 }}
        onChange={handleChange}
      />
    );

    expect(screen.getByDisplayValue("-23.55052")).toBeDefined();
    expect(screen.getByDisplayValue("-46.6333")).toBeDefined();

    const invertBtn = screen.getByRole("button", { name: /inverter/i });
    fireEvent.click(invertBtn);

    expect(handleChange).toHaveBeenCalledWith({ lat: -46.6333, lon: -23.55052 });
  });

  it("processa paste combinado de coordenadas com vírgula ou espaço", () => {
    const handleChange = vi.fn();
    render(<CoordinateInput onChange={handleChange} />);

    const latInput = screen.getByLabelText(/Latitude/i);

    fireEvent.paste(latInput, {
      clipboardData: {
        getData: () => "-23.5505, -46.6333",
      },
    });

    expect(handleChange).toHaveBeenCalledWith({ lat: -23.5505, lon: -46.6333 });
  });
});

describe("ConflictDialog (Concorrência Otimista 412/409)", () => {
  it("exibe comparativo entre rascunho local e versão remota e executa onReloadRemote", async () => {
    const handleReload = vi.fn().mockResolvedValue(undefined);

    render(
      <ConflictDialog
        open={true}
        onOpenChange={vi.fn()}
        entityName="POP Central"
        currentVersion={2}
        remoteVersion={3}
        differences={[
          {
            fieldName: "name",
            fieldLabel: "Nome do Site",
            draftValue: "POP Central Rascunho",
            remoteValue: "POP Central Servidor",
          },
        ]}
        onReloadRemote={handleReload}
      />
    );

    expect(screen.getByText("Conflito de Alteração Concorrente")).toBeDefined();
    expect(screen.getByText("Sua versão: 2")).toBeDefined();
    expect(screen.getByText("Versão no servidor: 3")).toBeDefined();
    expect(screen.getByText("POP Central Rascunho")).toBeDefined();
    expect(screen.getByText("POP Central Servidor")).toBeDefined();

    const reloadBtn = screen.getByRole("button", { name: /recarregar do servidor/i });
    fireEvent.click(reloadBtn);

    await waitFor(() => {
      expect(handleReload).toHaveBeenCalledTimes(1);
    });
  });

  it("executa onOverwriteWithDraft ao clicar em forçar sobrescrita", async () => {
    const handleOverwrite = vi.fn().mockResolvedValue(undefined);

    render(
      <ConflictDialog
        open={true}
        onOpenChange={vi.fn()}
        entityName="POP Central"
        currentVersion={2}
        remoteVersion={3}
        onReloadRemote={vi.fn()}
        onOverwriteWithDraft={handleOverwrite}
      />
    );

    const overwriteBtn = screen.getByRole("button", { name: /forçar sobrescrita/i });
    fireEvent.click(overwriteBtn);

    await waitFor(() => {
      expect(handleOverwrite).toHaveBeenCalledTimes(1);
    });
  });
});

describe("DataTable (Paginação e Seleção)", () => {
  interface SampleRow {
    id: string;
    code: string;
    name: string;
  }

  const sampleData: SampleRow[] = [
    { id: "1", code: "SITE-01", name: "POP Alpha" },
    { id: "2", code: "SITE-02", name: "POP Beta" },
  ];

  const columns: ColumnDef<SampleRow, unknown>[] = [
    {
      accessorKey: "code",
      header: "Código",
    },
    {
      accessorKey: "name",
      header: "Nome",
    },
  ];

  it("renderiza tabela paginada com dados e suporte a seleção de linha", () => {
    const handleSelection = vi.fn();
    const handlePageChange = vi.fn();

    render(
      <DataTable
        columns={columns}
        data={sampleData}
        total={25}
        page={1}
        pageSize={10}
        onPageChange={handlePageChange}
        onPageSizeChange={vi.fn()}
        selectedIds={["1"]}
        onSelectionChange={handleSelection}
        idAccessor={(row) => row.id}
      />
    );

    expect(screen.getByText("SITE-01")).toBeDefined();
    expect(screen.getByText("POP Alpha")).toBeDefined();
    expect(screen.getByText("SITE-02")).toBeDefined();
    expect(screen.getByText("POP Beta")).toBeDefined();

    // Contador explícito de seleção da página
    expect(screen.getByText(/1 de 2 linha\(s\) selecionada\(s\) nesta página/i)).toBeDefined();
    expect(screen.getByText(/Total de/i)).toBeDefined();

    // Checkbox de seleção
    const selectAllCheckbox = screen.getByLabelText("Selecionar todas as linhas desta página") as HTMLInputElement;
    fireEvent.click(selectAllCheckbox);

    // Deve selecionar os IDs da página atual
    expect(handleSelection).toHaveBeenCalledWith(["1", "2"]);
  });

  it("distingue empty state filtrado de empty state geral", () => {
    const handleClear = vi.fn();

    const { rerender } = render(
      <DataTable
        columns={columns}
        data={[]}
        total={0}
        page={1}
        pageSize={10}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
        isFiltered={true}
        onClearFilters={handleClear}
      />
    );

    expect(screen.getByText("Nenhum resultado encontrado")).toBeDefined();
    const clearBtn = screen.getByRole("button", { name: /limpar filtros/i });
    fireEvent.click(clearBtn);
    expect(handleClear).toHaveBeenCalledTimes(1);

    // Sem filtros
    rerender(
      <DataTable
        columns={columns}
        data={[]}
        total={0}
        page={1}
        pageSize={10}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
        isFiltered={false}
        emptyTitle="Nenhum POP cadastrado"
      />
    );

    expect(screen.getByText("Nenhum POP cadastrado")).toBeDefined();
  });
});
