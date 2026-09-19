"use client";

import * as React from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { listCables, type CableRead } from "@/features/cables/api";
import { DataTable } from "@/components/ui/data-table/data-table";
import { DataTableFilterBar } from "@/components/ui/data-table/data-table-filter-bar";
import { EntityLink } from "@/components/ui/entity-link";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/state-displays";
import { CableFormDialog } from "@/features/cables/components/cable-form-dialog";
import { Plus, Eye, Edit } from "lucide-react";
import Link from "next/link";
import { PermissionGate } from "@/components/auth/permission-gate";

export function CablesTable() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = Number(searchParams.get("page")) || 1;
  const pageSize = Number(searchParams.get("page_size")) || 20;
  const searchQuery = searchParams.get("q") || "";

  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [formDialogOpen, setFormDialogOpen] = React.useState(false);
  const [editingCable, setEditingCable] = React.useState<CableRead | null>(null);

  const updateQueryParams = React.useCallback(
    (updates: Record<string, string | number | null>) => {
      const params = new URLSearchParams(searchParams.toString());

      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === "" || (key === "page" && value === 1)) {
          params.delete(key);
        } else {
          params.set(key, String(value));
        }
      }

      router.push(`${pathname}?${params.toString()}`);
    },
    [router, pathname, searchParams]
  );

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["cables", "list", { page, pageSize, q: searchQuery }],
    queryFn: () =>
      listCables({
        page,
        page_size: pageSize,
        q: searchQuery || null,
      }),
  });

  const columns = React.useMemo<ColumnDef<CableRead, unknown>[]>(
    () => [
      {
        id: "identification",
        header: "Cabo Óptico",
        cell: ({ row }) => (
          <EntityLink
            type="cable"
            id={row.original.id}
            code={row.original.code}
            name={row.original.model}
          />
        ),
      },
      {
        id: "model",
        header: "Modelo Comercial",
        cell: ({ row }) => (
          <span className="text-xs text-foreground font-medium">{row.original.model}</span>
        ),
      },
      {
        id: "capacity",
        header: "Capacidade Fibras / Tubos",
        cell: ({ row }) => (
          <div className="flex items-center gap-1.5 font-mono text-xs">
            <span className="font-bold text-foreground">{row.original.fiber_count} FO</span>
            <span className="text-muted-foreground">
              ({row.original.tube_count} {row.original.tube_count === 1 ? "tubo" : "tubos"})
            </span>
          </div>
        ),
      },
      {
        id: "color_standard",
        header: "Norma de Cores",
        cell: ({ row }) => (
          <Badge variant="outline" className="text-[11px] font-mono">
            {row.original.color_standard}
          </Badge>
        ),
      },
      {
        id: "status",
        header: "Situação",
        cell: ({ row }) => {
          const status = row.original.status;
          const opticalStatus =
            status === "installed" ? "free" : status === "planned" ? "reserved" : "damaged";
          return <StatusBadge status={opticalStatus} />;
        },
      },
      {
        id: "version",
        header: "Revisão",
        cell: ({ row }) => (
          <Badge variant="secondary" className="font-mono text-[10px]">
            v{row.original.version}
          </Badge>
        ),
      },
      {
        id: "actions",
        header: "Ações",
        cell: ({ row }) => (
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" asChild className="h-7 px-2 text-xs gap-1">
              <Link href={`/cables/${row.original.id}`}>
                <Eye className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Detalhes</span>
              </Link>
            </Button>
            <PermissionGate permission="network:write">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-muted-foreground"
                onClick={() => {
                  setEditingCable(row.original);
                  setFormDialogOpen(true);
                }}
              >
                <Edit className="h-3.5 w-3.5" />
                <span className="sr-only">Editar</span>
              </Button>
            </PermissionGate>
          </div>
        ),
      },
    ],
    []
  );

  const isFiltered = Boolean(searchQuery);

  if (error) {
    return (
      <div className="py-6">
        <ErrorState
          title="Falha ao carregar catálogo de Cabos Ópticos"
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Barra superior de ações e busca */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <DataTableFilterBar
          searchValue={searchQuery}
          onSearchChange={(newQ) => updateQueryParams({ q: newQ, page: 1 })}
          searchPlaceholder="Buscar por código ou modelo de cabo..."
          isFiltered={isFiltered}
          onClearFilters={() => updateQueryParams({ q: null, page: 1 })}
        />

        <PermissionGate permission="network:write">
          <Button
            size="sm"
            className="gap-1.5 flex-shrink-0"
            onClick={() => {
              setEditingCable(null);
              setFormDialogOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            <span>Novo Cabo</span>
          </Button>
        </PermissionGate>
      </div>

      {/* Tabela de Dados */}
      <DataTable
        columns={columns}
        data={data?.items || []}
        total={data?.total || 0}
        page={page}
        pageSize={pageSize}
        onPageChange={(newPage) => updateQueryParams({ page: newPage })}
        onPageSizeChange={(newPageSize) => updateQueryParams({ page_size: newPageSize, page: 1 })}
        isLoading={isLoading}
        selectedIds={selectedIds}
        onSelectionChange={setSelectedIds}
        idAccessor={(c) => c.id}
        isFiltered={isFiltered}
        onClearFilters={() => updateQueryParams({ q: null, page: 1 })}
        emptyTitle="Nenhum cabo óptico cadastrado"
        emptyDescription="Cadastre os cabos de rede troncal, distribuição ou atendimento."
        emptyActionLabel="Cadastrar Novo Cabo"
        onEmptyAction={() => {
          setEditingCable(null);
          setFormDialogOpen(true);
        }}
      />

      {/* Modal de Criação / Edição */}
      <CableFormDialog
        open={formDialogOpen}
        onOpenChange={setFormDialogOpen}
        cable={editingCable}
        onSuccess={() => refetch()}
      />
    </div>
  );
}
