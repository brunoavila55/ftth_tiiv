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
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import type { TerminalRead, BatchOperationItem } from "@/features/connectivity/api";
import { formatTerminalKind } from "./connection-modal";
import { Bookmark, AlertCircle } from "lucide-react";

export interface ReservationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  terminal: TerminalRead | null;
  onAddOperation: (op: BatchOperationItem) => void;
}

export function ReservationDialog({
  open,
  onOpenChange,
  terminal,
  onAddOperation,
}: ReservationDialogProps) {
  const [reason, setReason] = React.useState<string>("");
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setReason("");
      setErrorMsg(null);
    }
  }, [open]);

  if (!terminal) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setErrorMsg("O motivo da reserva técnica é obrigatório.");
      return;
    }

    onAddOperation({
      action: "reserve",
      terminal_a_id: terminal.id,
      reservation_reason: reason.trim(),
    });

    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-primary">
            <Bookmark className="h-5 w-5" />
            <DialogTitle>Reservar Terminal Óptico</DialogTitle>
          </div>
          <DialogDescription>
            Bloqueie o terminal óptico para provisionamento futuro, impedindo sua atribuição indevida.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {errorMsg && (
            <div className="flex items-start gap-2 p-3 text-xs bg-destructive/10 text-destructive rounded-md border border-destructive/20">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="p-3 bg-muted/40 rounded-lg border border-border text-xs space-y-1">
            <p className="font-semibold text-foreground">{terminal.label}</p>
            <p className="text-muted-foreground">
              Tipo: {formatTerminalKind(terminal.kind)} • ID: <span className="font-mono text-[10px]">{terminal.id}</span>
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="reservation-reason" className="text-xs font-semibold">
              Motivo da Reserva *
            </Label>
            <Input
              id="reservation-reason"
              placeholder="Ex: Reserva para projeto corporativo cliente XPTO"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="text-xs"
              required
            />
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
            <Button type="submit" size="sm" disabled={!reason.trim()}>
              Adicionar Reserva ao Lote
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
