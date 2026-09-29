"use client";

import * as React from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { listSites } from "@/features/inventory/api";
import { DataTable } from "@/components/ui/data-table/data-table";
import { DataTableFilterBar } from "@/components/ui/data-table/data-table-filter-bar";
import { EntityLink } from "@/components/ui/entity-link";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/state-displays";
import { formatPtBrNumber } from "@/lib/format/numbers";
import type { SiteRead } from "@/lib/api/types";
import { Plus, Eye, Edit } from "lucide-react";
import Link from "next/link";
import { SiteFormDialog } from "@/features/inventory/components/site-form-dialog";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useAuth } from "@/features/auth/auth-context";

const SITE_KIND_LABELS: Record<string, string> = {
  pop: "POP de Telecom",
  wireless_pop: "POP Wireless",
  radio_tower: "Torre de Rádio",
  technical_facility: "Instalação Técnica",
  central_office: "Central Telefônica",
  datacenter: "Data Center",
  cabinet: "Armário de Rua",
  pole_box: "Caixa em Poste",
  customer_building: "Edifício do Assinante",
};

export interface SitesTableProps {
  fixedKind?: "wireless_pop" | "radio_tower";
}

export function SitesTable({ fixedKind }: SitesTableProps = {}) {
  const { hasPermission } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Leitura de parâmetros de busca e paginação a partir da URL
  const page = Number(searchParams.get("page")) || 1;
  const pageSize = Number(searchParams.get("page_size")) || 20;
  const searchQuery = searchParams.get("q") || "";
  const kindFilter = fixedKind ?? searchParams.get("kind") ?? "";

  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [formDialogOpen, setFormDialogOpen] = React.useState(false);
  const [editingSite, setEditingSite] = React.useState<SiteRead | null>(null);

  // Atualiza parâmetros na URL mantendo histórico de navegação
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
    queryKey: ["inventory", "sites", { page, pageSize, q: searchQuery, kind: kindFilter }],
    queryFn: () =>
      listSites({
        page,
        page_size: pageSize,
        q: searchQuery || null,
        kind: kindFilter || null,
      }),
  });

  const columns = React.useMemo<ColumnDef<SiteRead, unknown>[]>(
    () => [
      {
        id: "identification",
        header: "Identificação",
        cell: ({ row }) => (
          <EntityLink
            type="site"
            id={row.original.id}
            code={row.original.code}
            name={row.original.name}
          />
        ),
      },
      {
        id: "kind",
        header: "Tipo de Site",
        cell: ({ row }) => {
          const kind = row.original.kind;
          const label = SITE_KIND_LABELS[kind] || kind;
          return (
            <Badge variant="outline" className="text-[11px] font-normal">
              {label}
            </Badge>
          );
        },
      },
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
          <div className="flex items-center gap-1.5">
            <Button variant="ghost" size="sm" asChild className="h-7 px-2 text-xs gap-1">
              <Link href={`/sites/${row.original.id}`}>
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
                  setEditingSite(row.original);
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

  const isFiltered = Boolean(searchQuery || (!fixedKind && kindFilter));

  if (error) {
    return (
      <div className="py-6">
        <ErrorState
          title="Falha ao carregar catálogo de Sites"
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
          searchPlaceholder={fixedKind === "radio_tower" ? "Buscar torre por código ou nome..." : "Buscar por código ou nome do POP..."}
          isFiltered={isFiltered}
          onClearFilters={() => updateQueryParams({ q: null, kind: null, page: 1 })}
        >
          {/* Seletor de Tipo de Site */}
          {!fixedKind && <select
            value={kindFilter}
            onChange={(e) => updateQueryParams({ kind: e.target.value || null, page: 1 })}
            className="h-9 rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label="Filtrar por tipo de site"
          >
            <option value="">Todos os tipos</option>
            <option value="pop">POP de Telecom</option>
            <option value="wireless_pop">POP Wireless</option>
            <option value="radio_tower">Torre de Rádio</option>
            <option value="cabinet">Armário de Rua</option>
            <option value="technical_facility">Instalação Técnica</option>
          </select>}
        </DataTableFilterBar>

        <PermissionGate permission="network:write">
          <Button
            size="sm"
            className="gap-1.5 flex-shrink-0"
            onClick={() => {
              setEditingSite(null);
              setFormDialogOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            <span>{fixedKind === "radio_tower" ? "Nova Torre" : fixedKind ? "Novo POP Wireless" : "Novo Site"}</span>
          </Button>
        </PermissionGate>
      </div>

      {/* Tabela de Dados Paginada no Servidor */}
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
        idAccessor={(site) => site.id}
        isFiltered={isFiltered}
        onClearFilters={() => updateQueryParams({ q: null, kind: null, page: 1 })}
        emptyTitle={fixedKind === "radio_tower" ? "Nenhuma torre de rádio cadastrada" : fixedKind ? "Nenhum POP wireless cadastrado" : "Nenhum POP ou Site cadastrado"}
        emptyDescription={fixedKind ? "Cadastre a localização e os dados deste ponto wireless." : "Comece cadastrando a primeira estação de telecomunicações ou central técnica."}
        emptyActionLabel={hasPermission("network:write") ? fixedKind === "radio_tower" ? "Cadastrar Torre" : fixedKind ? "Cadastrar POP Wireless" : "Cadastrar Novo Site" : undefined}
        onEmptyAction={hasPermission("network:write") ? () => {
          setEditingSite(null);
          setFormDialogOpen(true);
        } : undefined}
      />

      {/* Modal de Criação / Edição */}
      <SiteFormDialog
        open={formDialogOpen}
        onOpenChange={setFormDialogOpen}
        site={editingSite}
        defaultKind={fixedKind}
        allowedKinds={fixedKind ? [fixedKind] : undefined}
        onSuccess={() => refetch()}
      />
    </div>
  );
}
