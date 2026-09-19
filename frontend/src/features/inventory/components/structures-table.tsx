"use client";

import * as React from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { listStructures, type StructureRead } from "@/features/inventory/api";
import { DataTable } from "@/components/ui/data-table/data-table";
import { DataTableFilterBar } from "@/components/ui/data-table/data-table-filter-bar";
import { EntityLink } from "@/components/ui/entity-link";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/state-displays";
import { formatPtBrNumber } from "@/lib/format/numbers";
import { StructureFormDialog } from "@/features/inventory/components/structure-form-dialog";
import { Plus, Eye, Map, Edit } from "lucide-react";
import Link from "next/link";
import { PermissionGate } from "@/components/auth/permission-gate";

const STRUCTURE_KIND_LABELS: Record<string, string> = {
  pole: "Poste",
  ceo: "Caixa CEO",
  cto: "Caixa CTO",
  manhole: "Caixa Subterrânea",
  pedestal: "Pedestal",
};

export interface StructuresTableProps {
  fixedKind?: "pole" | "ceo" | "cto" | "manhole" | "pedestal";
  title?: string;
}

export function StructuresTable({ fixedKind, title }: StructuresTableProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = Number(searchParams.get("page")) || 1;
  const pageSize = Number(searchParams.get("page_size")) || 20;
  const searchQuery = searchParams.get("q") || "";
  const kindFilter = fixedKind || searchParams.get("kind") || "";

  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [formDialogOpen, setFormDialogOpen] = React.useState(false);
  const [editingStructure, setEditingStructure] = React.useState<StructureRead | null>(null);

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
    queryKey: ["inventory", "structures", { page, pageSize, q: searchQuery, kind: kindFilter }],
    queryFn: () =>
      listStructures({
        page,
        page_size: pageSize,
        q: searchQuery || null,
        kind: kindFilter || null,
      }),
  });

  const columns = React.useMemo<ColumnDef<StructureRead, unknown>[]>(
    () => [
      {
        id: "identification",
        header: "Identificação",
        cell: ({ row }) => (
          <EntityLink
            type="structure"
            id={row.original.id}
            code={row.original.code}
            name={STRUCTURE_KIND_LABELS[row.original.kind] || row.original.kind}
          />
        ),
      },
      ...(!fixedKind
        ? [
            {
              id: "kind",
              header: "Tipo",
              cell: ({ row }: { row: { original: StructureRead } }) => (
                <Badge variant="outline" className="text-[11px] font-normal">
                  {STRUCTURE_KIND_LABELS[row.original.kind] || row.original.kind}
                </Badge>
              ),
            },
          ]
        : []),
      {
        id: "coordinates",
        header: "Coordenadas (WGS-84)",
        cell: ({ row }) => {
          const coords = row.original.location?.coordinates;
          if (!coords || coords.length < 2) return <span className="text-muted-foreground">—</span>;
          const [lon, lat] = coords;
          return (
            <span className="font-mono text-xs text-muted-foreground">
              {formatPtBrNumber(lat, { minDecimals: 5, maxDecimals: 5 })},{" "}
              {formatPtBrNumber(lon, { minDecimals: 5, maxDecimals: 5 })}
            </span>
          );
        },
      },
      {
        id: "capacity",
        header: "Capacidade",
        cell: ({ row }) => {
          const cap = row.original.capacity;
          const isCto = row.original.kind === "cto";
          const isCeo = row.original.kind === "ceo";
          const unit = isCto ? "portas" : isCeo ? "fusões" : "unid.";
          return (
            <span className="font-mono text-xs">
              {cap} {unit}
            </span>
          );
        },
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
        id: "condition",
        header: "Condição Física",
        cell: ({ row }) => {
          const cond = row.original.condition;
          const variant = cond === "ok" ? "secondary" : "destructive";
          const label = cond === "ok" ? "OK" : cond === "degraded" ? "Degradado" : "Danificado";
          return (
            <Badge variant={variant} className="text-[10px] font-medium">
              {label}
            </Badge>
          );
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
        cell: ({ row }) => {
          const coords = row.original.location?.coordinates;
          const detailHref = `/${row.original.kind === "pole" ? "poles" : row.original.kind === "ceo" ? "ceos" : row.original.kind === "cto" ? "ctos" : "structures"}/${row.original.id}`;
          return (
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" asChild className="h-7 px-2 text-xs gap-1">
                <Link href={detailHref}>
                  <Eye className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Detalhes</span>
                </Link>
              </Button>
              {coords && (
                <Button variant="ghost" size="sm" asChild className="h-7 px-2 text-xs text-muted-foreground">
                  <Link href={`/map?lat=${coords[1]}&lng=${coords[0]}&zoom=17&selected=${row.original.id}`}>
                    <Map className="h-3.5 w-3.5" />
                    <span className="sr-only">Ver no Mapa</span>
                  </Link>
                </Button>
              )}
              <PermissionGate permission="network:write">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs text-muted-foreground"
                  onClick={() => {
                    setEditingStructure(row.original);
                    setFormDialogOpen(true);
                  }}
                >
                  <Edit className="h-3.5 w-3.5" />
                  <span className="sr-only">Editar</span>
                </Button>
              </PermissionGate>
            </div>
          );
        },
      },
    ],
    [fixedKind]
  );

  const isFiltered = Boolean(searchQuery || (!fixedKind && kindFilter));

  const kindDisplayName =
    title ||
    (fixedKind
      ? STRUCTURE_KIND_LABELS[fixedKind] || fixedKind
      : "Estruturas Físicas");

  if (error) {
    return (
      <div className="py-6">
        <ErrorState
          title={`Falha ao carregar catálogo de ${kindDisplayName}`}
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Barra superior de ações e filtros */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <DataTableFilterBar
          searchValue={searchQuery}
          onSearchChange={(newQ) => updateQueryParams({ q: newQ, page: 1 })}
          searchPlaceholder={`Buscar por código de ${kindDisplayName.toLowerCase()}...`}
          isFiltered={isFiltered}
          onClearFilters={() => updateQueryParams({ q: null, kind: null, page: 1 })}
        >
          {!fixedKind && (
            <select
              value={kindFilter}
              onChange={(e) => updateQueryParams({ kind: e.target.value || null, page: 1 })}
              className="h-9 rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              aria-label="Filtrar por tipo de estrutura"
            >
              <option value="">Todos os tipos</option>
              <option value="pole">Postes</option>
              <option value="ceo">Caixas CEO</option>
              <option value="cto">Caixas CTO</option>
              <option value="manhole">Caixas Subterrâneas</option>
              <option value="pedestal">Pedestais</option>
            </select>
          )}
        </DataTableFilterBar>

        <PermissionGate permission="network:write">
          <Button
            size="sm"
            className="gap-1.5 flex-shrink-0"
            onClick={() => {
              setEditingStructure(null);
              setFormDialogOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            <span>Nova {fixedKind ? STRUCTURE_KIND_LABELS[fixedKind] : "Estrutura"}</span>
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
        idAccessor={(st) => st.id}
        isFiltered={isFiltered}
        onClearFilters={() => updateQueryParams({ q: null, kind: null, page: 1 })}
        emptyTitle={`Nenhum registro de ${kindDisplayName.toLowerCase()} encontrado`}
        emptyDescription="Cadastre uma nova estrutura pelo botão acima ou usando o botão de Novo Ponto no Mapa Operacional."
        emptyActionLabel={`Cadastrar Nova ${fixedKind ? STRUCTURE_KIND_LABELS[fixedKind] : "Estrutura"}`}
        onEmptyAction={() => {
          setEditingStructure(null);
          setFormDialogOpen(true);
        }}
      />

      {/* Modal de Criação / Edição */}
      <StructureFormDialog
        open={formDialogOpen}
        onOpenChange={setFormDialogOpen}
        structure={editingStructure}
        defaultKind={fixedKind || "pole"}
        onSuccess={() => refetch()}
      />
    </div>
  );
}
