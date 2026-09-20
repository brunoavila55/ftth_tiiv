"use client";

import * as React from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/types";
import {
  createSplitter,
  updateSplitter,
  type SplitterPortLoss,
  type SplitterRead,
} from "../api";

interface SplitterFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  structureId: string;
  splitter?: SplitterRead | null;
  onSuccess: (splitter: SplitterRead) => void;
}

const DEFAULT_LOSSES: Record<number, number> = {
  2: 3.6,
  4: 7.2,
  8: 10.5,
  16: 13.7,
  32: 17,
  64: 20.5,
};

function buildLosses(count: number): SplitterPortLoss[] {
  const loss = DEFAULT_LOSSES[count] ?? 10.5;
  return Array.from({ length: count }, (_, index) => ({
    port_number: index + 1,
    loss_1310_db: loss,
    loss_1490_db: loss,
    loss_1550_db: loss,
  }));
}

export function SplitterFormDialog({
  open,
  onOpenChange,
  structureId,
  splitter,
  onSuccess,
}: SplitterFormDialogProps) {
  const [code, setCode] = React.useState("");
  const [outputCount, setOutputCount] = React.useState(8);
  const [notes, setNotes] = React.useState("");
  const [losses, setLosses] = React.useState<SplitterPortLoss[]>(() => buildLosses(8));
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    if (splitter) {
      const outputPorts = splitter.ports.filter((port) => !port.is_input);
      setCode(splitter.code);
      setOutputCount(splitter.output_ports_count);
      setNotes(splitter.notes ?? "");
      setLosses(
        outputPorts.map((port) => ({
          port_number: port.port_number,
          loss_1310_db: port.loss_1310_db ?? 0,
          loss_1490_db: port.loss_1490_db ?? 0,
          loss_1550_db: port.loss_1550_db,
        }))
      );
    } else {
      setCode("");
      setOutputCount(8);
      setNotes("");
      setLosses(buildLosses(8));
    }
    setServerError(null);
  }, [open, splitter]);

  const changeOutputCount = (count: number) => {
    setOutputCount(count);
    setLosses(buildLosses(count));
  };

  const changeLoss = (
    index: number,
    field: "loss_1310_db" | "loss_1490_db" | "loss_1550_db",
    rawValue: string
  ) => {
    setLosses((current) =>
      current.map((loss, lossIndex) => {
        if (lossIndex !== index) return loss;
        if (field === "loss_1550_db" && rawValue === "") return { ...loss, [field]: null };
        return { ...loss, [field]: Number(rawValue) };
      })
    );
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (code.trim().length < 2) {
      setServerError("Informe um código com pelo menos 2 caracteres.");
      return;
    }
    if (
      losses.some(
        (loss) =>
          !Number.isFinite(loss.loss_1310_db) ||
          !Number.isFinite(loss.loss_1490_db) ||
          loss.loss_1310_db < 0 ||
          loss.loss_1490_db < 0 ||
          (loss.loss_1550_db !== null &&
            loss.loss_1550_db !== undefined &&
            (!Number.isFinite(loss.loss_1550_db) || loss.loss_1550_db < 0))
      )
    ) {
      setServerError("As perdas devem ser números maiores ou iguais a zero.");
      return;
    }

    setIsSubmitting(true);
    setServerError(null);
    try {
      const saved = splitter
        ? await updateSplitter(
            splitter.id,
            { notes: notes || null, ports: losses },
            splitter.version
          )
        : await createSplitter({
            code: code.trim(),
            structure_id: structureId,
            ratio: `1:${outputCount}`,
            output_ports_count: outputCount,
            ports: losses,
            notes: notes || null,
          });
      onSuccess(saved);
      onOpenChange(false);
    } catch (error: unknown) {
      setServerError(
        error instanceof ApiError
          ? error.detail || error.message
          : "Não foi possível salvar o splitter."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{splitter ? "Editar splitter" : "Cadastrar splitter"}</DialogTitle>
          <DialogDescription>
            Configure a razão e as perdas de inserção de cada saída óptica.
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="splitter-code">Código *</Label>
              <Input
                id="splitter-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                disabled={Boolean(splitter) || isSubmitting}
                placeholder="SPL-CTO04-1x8"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="splitter-ratio">Razão</Label>
              <select
                id="splitter-ratio"
                value={outputCount}
                onChange={(event) => changeOutputCount(Number(event.target.value))}
                disabled={Boolean(splitter) || isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                {[2, 4, 8, 16, 32, 64].map((count) => (
                  <option key={count} value={count}>{`1:${count}`}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <div>
              <p className="text-sm font-medium">Perdas por saída</p>
              <p className="text-xs text-muted-foreground">Valores em dB; 1550 nm é opcional.</p>
            </div>
            <div className="max-h-72 overflow-auto rounded-md border border-border">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-muted">
                  <tr>
                    <th className="p-2 text-left">Saída</th>
                    <th className="p-2 text-left">1310 nm</th>
                    <th className="p-2 text-left">1490 nm</th>
                    <th className="p-2 text-left">1550 nm</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {losses.map((loss, index) => (
                    <tr key={loss.port_number}>
                      <td className="p-2 font-mono">#{loss.port_number}</td>
                      {(["loss_1310_db", "loss_1490_db", "loss_1550_db"] as const).map(
                        (field) => (
                          <td key={field} className="p-1.5">
                            <Input
                              aria-label={`Saída ${loss.port_number} ${field.replace("loss_", "").replace("_db", " nm")}`}
                              type="number"
                              min="0"
                              step="0.01"
                              value={loss[field] ?? ""}
                              onChange={(event) => changeLoss(index, field, event.target.value)}
                              disabled={isSubmitting}
                              className="h-8 min-w-24 font-mono"
                            />
                          </td>
                        )
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="splitter-notes">Observações</Label>
            <Input
              id="splitter-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              disabled={isSubmitting}
              maxLength={5000}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting} className="gap-2">
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {splitter ? "Salvar alterações" : "Cadastrar splitter"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
