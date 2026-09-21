"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { Edit, Eye, Plus, Split, Trash2 } from "lucide-react";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable } from "@/components/ui/data-table/data-table";
import { EntityLink } from "@/components/ui/entity-link";
import { ErrorState } from "@/components/ui/state-displays";
import {
  deleteSplitter,
  listAllSplitters,
  type SplitterRead,
} from "../api";
import { SplitterFormDialog } from "./splitter-form-dialog";

function formatLossRange(splitter: SplitterRead): string {
  const losses = splitter.ports
    .filter((port) => !port.is_input && port.loss_1490_db != null)
    .map((port) => port.loss_1490_db as number);

  if (!losses.length) return "—";
  const minimum = Math.min(...losses).toFixed(2);
  const maximum = Math.max(...losses).toFixed(2);
  return minimum === maximum ? `${minimum} dB` : `${minimum}–${maximum} dB`;
}

export function SplittersCatalog() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(20);
  const [editing, setEditing] = React.useState<SplitterRead | null>(null);
  const [deleting, setDeleting] = React.useState<SplitterRead | null>(null);
  const queryKey = ["splitters", "catalog", { page, pageSize }] as const;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: () => listAllSplitters({ page, page_size: pageSize }),
  });

  const deleteMutation = useMutation({
    mutationFn: (splitter: SplitterRead) => deleteSplitter(splitter.id, splitter.version),
    onSuccess: async () => {
      setDeleting(null);
      await queryClient.invalidateQueries({ queryKey: ["splitters"] });
    },
  });

  const columns = React.useMemo<ColumnDef<SplitterRead, unknown>[]>(
    () => [
      {
        id: "code",
        header: "Splitter",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Split className="h-4 w-4 shrink-0 text-primary" />
            <div className="min-w-0">
              <p className="font-mono font-semibold text-foreground">{row.original.code}</p>
              {row.original.notes && (
                <p className="max-w-64 truncate text-muted-foreground" title={row.original.notes}>
                  {row.original.notes}
                </p>
              )}
            </div>
          </div>
        ),
      },
      {
        id: "location",
        header: "Alojamento",
        cell: ({ row }) => {
          const splitter = row.original;
          if (splitter.device_id) {
            return (
              <EntityLink
                type="device"
                id={splitter.device_id}
                name={`Dispositivo #${splitter.device_id.slice(0, 8)}…`}
              />
            );
          }
          if (splitter.structure_id) {
            return (
              <EntityLink
                type="structure"
                id={splitter.structure_id}
                name={`Estrutura #${splitter.structure_id.slice(0, 8)}…`}
              />
            );
          }
          return <span className="text-muted-foreground">Não informado</span>;
        },
      },
      {
        id: "ratio",
        header: "Razão",
        cell: ({ row }) => <Badge variant="outline">{row.original.ratio}</Badge>,
      },
      {
        id: "outputs",
        header: "Saídas",
        cell: ({ row }) => (
          <span className="font-mono">{row.original.output_ports_count}</span>
        ),
      },
      {
        id: "loss",
        header: "Perda em 1490 nm",
        cell: ({ row }) => <span className="font-mono">{formatLossRange(row.original)}</span>,
      },
      {
        id: "version",
        header: "Revisão",
        cell: ({ row }) => <Badge variant="secondary">v{row.original.version}</Badge>,
      },
      {
        id: "actions",
        header: "Ações",
        cell: ({ row }) => {
          const splitter = row.original;
          const locationHref = splitter.device_id
            ? `/devices/${splitter.device_id}`
            : splitter.structure_id
              ? `/structures/${splitter.structure_id}`
              : null;

          return (
            <div className="flex items-center justify-end gap-1">
              {locationHref && (
                <Button variant="ghost" size="sm" asChild className="h-8 gap-1 px-2 text-xs">
                  <Link href={locationHref}>
                    <Eye className="h-3.5 w-3.5" />
                    <span className="hidden lg:inline">Gerenciar</span>
                  </Link>
                </Button>
              )}
              <PermissionGate permission="splitters:write">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setEditing(splitter)}
                  aria-label={`Editar ${splitter.code}`}
                >
                  <Edit className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive"
                  onClick={() => setDeleting(splitter)}
                  aria-label={`Excluir ${splitter.code}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </PermissionGate>
            </div>
          );
        },
      },
    ],
    []
  );

  if (error) {
    return (
      <ErrorState
        title="Falha ao carregar o catálogo de splitters"
        error={error}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-3xl text-xs text-muted-foreground">
          O alojamento físico define os terminais disponíveis. Cadastre novos splitters pela ficha
          da CTO ou CEO onde eles serão instalados.
        </p>
        <PermissionGate permission="splitters:write">
          <Button size="sm" asChild className="shrink-0 gap-1.5">
            <Link href="/ctos">
              <Plus className="h-4 w-4" />
              Cadastrar em uma caixa
            </Link>
          </Button>
        </PermissionGate>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        total={data?.total ?? 0}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(nextPageSize) => {
          setPageSize(nextPageSize);
          setPage(1);
        }}
        isLoading={isLoading}
        emptyTitle="Nenhum splitter cadastrado"
        emptyDescription="Abra uma CTO ou CEO para cadastrar o primeiro splitter óptico."
      />

      <SplitterFormDialog
        open={Boolean(editing)}
        onOpenChange={(open) => !open && setEditing(null)}
        structureId={editing?.structure_id ?? ""}
        splitter={editing}
        onSuccess={async () => {
          setEditing(null);
          await queryClient.invalidateQueries({ queryKey: ["splitters"] });
        }}
      />

      <ConfirmDialog
        open={Boolean(deleting)}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Excluir splitter"
        description={
          deleting
            ? `O splitter ${deleting.code} e seus terminais livres serão removidos. Portas com vínculos ópticos impedem a exclusão.`
            : ""
        }
        confirmLabel="Excluir splitter"
        verificationText={deleting?.code}
        isLoading={deleteMutation.isPending}
        onConfirm={async () => {
          if (deleting) await deleteMutation.mutateAsync(deleting);
        }}
      />
    </div>
  );
}
