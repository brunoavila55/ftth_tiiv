"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw } from "lucide-react";

export interface TopologyConflictDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  expectedRevision: number;
  serverRevision?: number | null;
  draftOperationsCount: number;
  onReconcile: () => void;
}

export function TopologyConflictDialog({
  open,
  onOpenChange,
  expectedRevision,
  serverRevision,
  draftOperationsCount,
  onReconcile,
}: TopologyConflictDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-amber-500">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <DialogTitle>Conflito de Revisão Topológica (409)</DialogTitle>
          </div>
          <DialogDescription>
            A topologia física desta estrutura foi modificada por outro operador ou processo concorrente enquanto você editava.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2 text-xs">
          <div className="p-3 bg-muted/50 rounded-md border border-border space-y-1.5 font-mono">
            <div className="flex justify-between">
              <span className="text-muted-foreground font-sans">Sua Revisão Base:</span>
              <span className="font-semibold text-foreground">rev #{expectedRevision}</span>
            </div>
            {serverRevision !== undefined && serverRevision !== null && (
              <div className="flex justify-between">
                <span className="text-muted-foreground font-sans">Revisão no Servidor:</span>
                <span className="font-semibold text-amber-600 dark:text-amber-400">rev #{serverRevision}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-border/50 pt-1.5 font-sans">
              <span className="text-muted-foreground">Operações Locais em Rascunho:</span>
              <span className="font-semibold text-primary">{draftOperationsCount} ações preservadas</span>
            </div>
          </div>

          <p className="text-muted-foreground">
            Suas propostas de fusão/conexão <strong>não foram perdidas</strong>. Ao continuar, os dados mais recentes de ocupação e conexões serão recarregados do servidor para que você possa revalidar os terminais e aplicar o lote com segurança.
          </p>
        </div>

        <DialogFooter className="pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Fechar e Revisar Rascunho
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => {
              onReconcile();
              onOpenChange(false);
            }}
          >
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Recarregar e Reconciliar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
