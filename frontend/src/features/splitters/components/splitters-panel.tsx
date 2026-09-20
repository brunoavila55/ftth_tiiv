"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Edit, Plus, Split, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PermissionGate } from "@/components/auth/permission-gate";
import { ApiError } from "@/lib/api/types";
import { deleteSplitter, listSplitters, type SplitterRead } from "../api";
import { SplitterFormDialog } from "./splitter-form-dialog";

interface SplittersPanelProps {
  structureId: string;
}

export function SplittersPanel({ structureId }: SplittersPanelProps) {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = React.useState(false);
  const [selected, setSelected] = React.useState<SplitterRead | null>(null);
  const [deleting, setDeleting] = React.useState<SplitterRead | null>(null);

  const queryKey = ["splitters", "structure", structureId] as const;
  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => listSplitters(structureId),
  });
  const deleteMutation = useMutation({
    mutationFn: (splitter: SplitterRead) => deleteSplitter(splitter.id, splitter.version),
    onSuccess: async () => {
      setDeleting(null);
      await queryClient.invalidateQueries({ queryKey });
      await queryClient.invalidateQueries({
        queryKey: ["inventory", "structures", structureId, "connectivity"],
      });
    },
  });

  const openCreate = () => {
    setSelected(null);
    setFormOpen(true);
  };
  const openEdit = (splitter: SplitterRead) => {
    setSelected(splitter);
    setFormOpen(true);
  };

  return (
    <section className="space-y-3" aria-label="Splitters ópticos">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Splitters ópticos</h3>
          <p className="text-xs text-muted-foreground">
            Entradas, saídas e perdas usadas pelo rastreamento e orçamento óptico.
          </p>
        </div>
        <PermissionGate permission="splitters:write">
          <Button size="sm" onClick={openCreate} className="gap-1.5 text-xs">
            <Plus className="h-4 w-4" />
            Novo splitter
          </Button>
        </PermissionGate>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-border bg-muted/50 text-[10px] uppercase text-muted-foreground">
            <tr>
              <th className="p-3">Código</th>
              <th className="p-3">Razão</th>
              <th className="p-3">Saídas</th>
              <th className="p-3">Perdas 1490 nm</th>
              <th className="p-3">Versão</th>
              <th className="p-3 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">Carregando splitters...</td></tr>
            ) : error ? (
              <tr>
                <td colSpan={6} className="p-6 text-center text-destructive">
                  {error instanceof ApiError ? error.detail : "Falha ao carregar splitters."}
                </td>
              </tr>
            ) : data?.items.length ? (
              data.items.map((splitter) => {
                const outputs = splitter.ports.filter((port) => !port.is_input);
                const losses = outputs.map((port) => port.loss_1490_db).filter((loss) => loss != null);
                const range = losses.length
                  ? `${Math.min(...losses).toFixed(2)}–${Math.max(...losses).toFixed(2)} dB`
                  : "—";
                return (
                  <tr key={splitter.id} className="hover:bg-muted/30">
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <Split className="h-4 w-4 text-primary" />
                        <div>
                          <p className="font-mono font-semibold">{splitter.code}</p>
                          {splitter.notes && <p className="max-w-48 truncate text-muted-foreground">{splitter.notes}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="p-3"><Badge variant="outline">{splitter.ratio}</Badge></td>
                    <td className="p-3 font-mono">{splitter.output_ports_count}</td>
                    <td className="p-3 font-mono">{range}</td>
                    <td className="p-3"><Badge variant="secondary">v{splitter.version}</Badge></td>
                    <td className="p-3">
                      <PermissionGate permission="splitters:write">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(splitter)} aria-label={`Editar ${splitter.code}`}>
                            <Edit className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => setDeleting(splitter)} aria-label={`Excluir ${splitter.code}`}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </PermissionGate>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">Nenhum splitter instalado nesta estrutura.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <SplitterFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        structureId={structureId}
        splitter={selected}
        onSuccess={async () => {
          await queryClient.invalidateQueries({ queryKey });
          await queryClient.invalidateQueries({
            queryKey: ["inventory", "structures", structureId, "connectivity"],
          });
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
    </section>
  );
}
