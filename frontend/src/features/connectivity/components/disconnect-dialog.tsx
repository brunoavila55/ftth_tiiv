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
import type { ConnectionRead, TerminalRead, BatchOperationItem } from "@/features/connectivity/api";
import { formatTerminalKind } from "./connection-modal";
import { AlertTriangle, Unlink } from "lucide-react";

export interface DisconnectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connection: ConnectionRead | null;
  terminals: TerminalRead[];
  onAddOperation: (op: BatchOperationItem) => void;
}

export function DisconnectDialog({
  open,
  onOpenChange,
  connection,
  terminals,
  onAddOperation,
}: DisconnectDialogProps) {
  if (!connection) return null;

  const termA = terminals.find((t) => t.id === connection.terminal_a_id);
  const termB = terminals.find((t) => t.id === connection.terminal_b_id);

  const handleConfirm = () => {
    onAddOperation({
      action: "disconnect",
      terminal_a_id: connection.terminal_a_id,
      terminal_b_id: connection.terminal_b_id,
    });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <DialogTitle>Desconectar Terminais Ópticos</DialogTitle>
          </div>
          <DialogDescription>
            A desconexão interromperá a continuidade óptica entre os terminais físicos abaixo.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2 text-xs">
          <div className="p-3 bg-muted/40 rounded-lg border border-border space-y-2 font-mono">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground font-sans">Terminal A:</span>
              <span className="font-semibold text-foreground">
                {termA?.label || connection.terminal_a_id} ({termA ? formatTerminalKind(termA.kind) : ""})
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground font-sans">Terminal B:</span>
              <span className="font-semibold text-foreground">
                {termB?.label || connection.terminal_b_id} ({termB ? formatTerminalKind(termB.kind) : ""})
              </span>
            </div>
            <div className="flex justify-between items-center border-t border-border/50 pt-2 font-sans">
              <span className="text-muted-foreground">Tipo de Conexão:</span>
              <span className="font-medium text-foreground capitalize">
                {connection.connection_type.replace("_", " ")}
              </span>
            </div>
            <div className="flex justify-between items-center font-sans">
              <span className="text-muted-foreground">Perda de Inserção:</span>
              <span className="font-medium text-foreground">{connection.loss_db} dB</span>
            </div>
          </div>

          <div className="p-2.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-300">
            <p className="font-semibold">Aviso de Impacto no Circuito:</p>
            <p className="mt-0.5">
              Circuitos ativos ou clientes dependentes desta rota óptica perderão o sinal óptico após a confirmação do lote no servidor.
            </p>
          </div>
        </div>

        <DialogFooter className="pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleConfirm}
          >
            <Unlink className="h-4 w-4 mr-1.5" />
            Adicionar Desconexão ao Lote
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
