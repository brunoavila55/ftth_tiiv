"use client";

import * as React from "react";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { DataTablePagination } from "@/components/ui/data-table/data-table-pagination";
import { LoadingState, EmptyState } from "@/components/ui/state-displays";
import { cn } from "@/lib/utils";

export interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  isLoading?: boolean;
  selectedIds?: string[];
  onSelectionChange?: (selectedIds: string[]) => void;
  idAccessor?: (row: TData) => string;
  isFiltered?: boolean;
  onClearFilters?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
  className?: string;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  isLoading = false,
  selectedIds,
  onSelectionChange,
  idAccessor,
  isFiltered = false,
  onClearFilters,
  emptyTitle,
  emptyDescription,
  emptyActionLabel,
  onEmptyAction,
  className,
}: DataTableProps<TData, TValue>) {
  // Configuração das colunas com suporte a seleção explícita de linha
  const tableColumns = React.useMemo(() => {
    if (!onSelectionChange || !idAccessor) {
      return columns;
    }

    const selectionColumn: ColumnDef<TData, unknown> = {
      id: "select",
      header: () => {
        const isAllPageSelected =
          data.length > 0 &&
          data.every((row) => selectedIds?.includes(idAccessor(row)));
        const isSomePageSelected =
          data.some((row) => selectedIds?.includes(idAccessor(row))) &&
          !isAllPageSelected;

        return (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input text-primary focus:ring-ring"
            checked={isAllPageSelected}
            ref={(el) => {
              if (el) el.indeterminate = isSomePageSelected;
            }}
            onChange={(e) => {
              const checked = e.target.checked;
              const pageIds = data.map(idAccessor);
              if (checked) {
                // Adiciona IDs desta página aos já selecionados
                const combined = Array.from(new Set([...(selectedIds || []), ...pageIds]));
                onSelectionChange(combined);
              } else {
                // Remove apenas os IDs desta página
                const remaining = (selectedIds || []).filter((id) => !pageIds.includes(id));
                onSelectionChange(remaining);
              }
            }}
            aria-label="Selecionar todas as linhas desta página"
            title="Selecionar todas as linhas desta página"
          />
        );
      },
      cell: ({ row }) => {
        const id = idAccessor(row.original);
        const isChecked = selectedIds?.includes(id) ?? false;

        return (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input text-primary focus:ring-ring"
            checked={isChecked}
            onChange={(e) => {
              const checked = e.target.checked;
              if (checked) {
                onSelectionChange([...(selectedIds || []), id]);
              } else {
                onSelectionChange((selectedIds || []).filter((item) => item !== id));
              }
            }}
            aria-label={`Selecionar linha ${id}`}
          />
        );
      },
      enableSorting: false,
      enableHiding: false,
    };

    return [selectionColumn, ...columns];
  }, [columns, onSelectionChange, idAccessor, data, selectedIds]);

  const table = useReactTable({
    data,
    columns: tableColumns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
  });

  const currentPageSelectedCount = React.useMemo(() => {
    if (!selectedIds || !idAccessor) return undefined;
    return data.filter((row) => selectedIds.includes(idAccessor(row))).length;
  }, [selectedIds, idAccessor, data]);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="relative overflow-hidden rounded-lg border border-border bg-card">
        {/* Indicador de carregamento sutil sobre os dados existentes */}
        {isLoading && data.length > 0 && (
          <div className="absolute inset-x-0 top-0 h-1 bg-primary/20 overflow-hidden z-10">
            <div className="h-full bg-primary animate-pulse" />
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 text-muted-foreground border-b border-border">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-3.5 py-3 font-semibold text-foreground whitespace-nowrap"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>

            <tbody className="divide-y divide-border">
              {isLoading && data.length === 0 ? (
                <tr>
                  <td colSpan={tableColumns.length} className="py-12">
                    <LoadingState message="Carregando registros de rede..." />
                  </td>
                </tr>
              ) : data.length === 0 ? (
                <tr>
                  <td colSpan={tableColumns.length} className="py-12 px-4">
                    {isFiltered ? (
                      <EmptyState
                        title="Nenhum resultado encontrado"
                        description="Nenhum item corresponde aos critérios de busca ou filtros selecionados."
                        actionLabel="Limpar Filtros"
                        onAction={onClearFilters}
                      />
                    ) : (
                      <EmptyState
                        title={emptyTitle || "Nenhum cadastro encontrado"}
                        description={emptyDescription || "Esta entidade ainda não possui elementos registrados."}
                        actionLabel={emptyActionLabel}
                        onAction={onEmptyAction}
                      />
                    )}
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => {
                  const isSelected = idAccessor && selectedIds?.includes(idAccessor(row.original));

                  return (
                    <tr
                      key={row.id}
                      className={cn(
                        "transition-colors hover:bg-muted/40",
                        isSelected && "bg-primary/5 font-medium"
                      )}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-3.5 py-2.5">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Paginação inferior */}
        <DataTablePagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
          selectedCount={currentPageSelectedCount}
          pageItemCount={data.length}
        />
      </div>
    </div>
  );
}
