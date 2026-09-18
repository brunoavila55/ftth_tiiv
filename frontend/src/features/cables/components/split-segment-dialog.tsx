"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/types";
import {
  previewSegmentSplit,
  splitSegment,
  type CableSegmentRead,
  type SegmentSplitPreviewResponse,
} from "@/features/cables/api";
import { listStructures, type StructureRead } from "@/features/inventory/api";
import { Loader2, Scissors, AlertTriangle } from "lucide-react";

export interface SplitSegmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  segment: CableSegmentRead | null;
  totalFibers: number;
  onSuccess: () => void;
}

export function SplitSegmentDialog({
  open,
  onOpenChange,
  segment,
  totalFibers,
  onSuccess,
}: SplitSegmentDialogProps) {
  const [structures, setStructures] = React.useState<StructureRead[]>([]);
  const [selectedStructureId, setSelectedStructureId] = React.useState<string>("");
  const [cutFiberNumbers, setCutFiberNumbers] = React.useState<number[]>([]);
  const [segment1Slack, setSegment1Slack] = React.useState<string>("10");
  const [segment2Slack, setSegment2Slack] = React.useState<string>("10");

  const [preview, setPreview] = React.useState<SegmentSplitPreviewResponse | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  // Carrega estruturas para escolha do local de acesso
  React.useEffect(() => {
    if (open) {
      listStructures({ page_size: 100 })
        .then((res) => {
          setStructures(res.items);
          if (res.items.length > 0) {
            setSelectedStructureId(res.items[0].id);
          }
        })
        .catch(() => {});
      setCutFiberNumbers([]);
      setPreview(null);
      setErrorMessage(null);
    }
  }, [open]);

  // Atualiza pré-visualização quando estrutura ou parâmetros mudam
  React.useEffect(() => {
    if (!segment || !selectedStructureId || !open) return;

    const timer = setTimeout(() => {
      setIsPreviewLoading(true);
      setErrorMessage(null);

      previewSegmentSplit(segment.id, {
        access_structure_id: selectedStructureId,
        cut_fiber_ids: cutFiberNumbers.map((n) => String(n)),
        segment_1_slack_m: Number(segment1Slack) || 0,
        segment_2_slack_m: Number(segment2Slack) || 0,
      })
        .then((res) => setPreview(res))
        .catch((err) => {
          if (err instanceof ApiError) {
            setErrorMessage(err.detail || err.message);
          }
        })
        .finally(() => setIsPreviewLoading(false));
    }, 250);

    return () => clearTimeout(timer);
  }, [segment, selectedStructureId, cutFiberNumbers, segment1Slack, segment2Slack, open]);

  const toggleFiberCut = (fiberNum: number) => {
    setCutFiberNumbers((prev) =>
      prev.includes(fiberNum) ? prev.filter((n) => n !== fiberNum) : [...prev, fiberNum]
    );
  };

  const handleSelectAllFibers = () => {
    const all = [];
    for (let i = 1; i <= totalFibers; i++) all.push(i);
    setCutFiberNumbers(all);
  };

  const handleClearAllFibers = () => {
    setCutFiberNumbers([]);
  };

  const handleConfirmSplit = async () => {
    if (!segment || !selectedStructureId) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await splitSegment(segment.id, {
        access_structure_id: selectedStructureId,
        cut_fiber_ids: cutFiberNumbers.map((n) => String(n)),
        segment_1_slack_m: Number(segment1Slack) || 0,
        segment_2_slack_m: Number(segment2Slack) || 0,
      });
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail || err.message || "Falha ao dividir trecho de cabo.");
      } else {
        setErrorMessage("Erro inesperado na operação de divisão.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!segment) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2 text-primary">
            <Scissors className="h-5 w-5" />
            <DialogTitle>Dividir Trecho de Cabo Óptico</DialogTitle>
          </div>
          <DialogDescription>
            Interrompa o trecho em uma estrutura física (caixa CEO/CTO). Defina quais fibras serão
            sangradas/cortadas para atendimento e quais permanecerão passantes contínuas.
          </DialogDescription>
        </DialogHeader>

        {errorMessage && (
          <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <p>{errorMessage}</p>
          </div>
        )}

        <div className="space-y-4 py-2 text-xs">
          {/* Estrutura de Acesso Intermediária */}
          <div className="space-y-1.5">
            <Label htmlFor="split-structure">Estrutura de Acesso (Ponto de Divisão) *</Label>
            <select
              id="split-structure"
              value={selectedStructureId}
              onChange={(e) => setSelectedStructureId(e.target.value)}
              disabled={isSubmitting}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {structures.map((st) => (
                <option key={st.id} value={st.id}>
                  {st.code} ({st.kind.toUpperCase()})
                </option>
              ))}
            </select>
          </div>

          {/* Reservas Técnicas */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="slack-1">Reserva Trecho 1 (metros)</Label>
              <Input
                id="slack-1"
                type="number"
                value={segment1Slack}
                onChange={(e) => setSegment1Slack(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="slack-2">Reserva Trecho 2 (metros)</Label>
              <Input
                id="slack-2"
                type="number"
                value={segment2Slack}
                onChange={(e) => setSegment2Slack(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
          </div>

          {/* Seleção de Fibras Cortadas vs Passantes */}
          <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-foreground">Plano de Sangria de Fibras</p>
                <p className="text-[11px] text-muted-foreground">
                  Fibras selecionadas (vermelho) serão cortadas. Fibras não selecionadas permanecem
                  passantes contínuas.
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleSelectAllFibers}
                  className="h-6 text-[10px] px-2"
                >
                  Cortar Todas
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleClearAllFibers}
                  className="h-6 text-[10px] px-2"
                >
                  Todas Passantes
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-12 gap-1.5 pt-2">
              {Array.from({ length: totalFibers }, (_, i) => i + 1).map((fiberNum) => {
                const isCut = cutFiberNumbers.includes(fiberNum);
                return (
                  <button
                    key={fiberNum}
                    type="button"
                    onClick={() => toggleFiberCut(fiberNum)}
                    className={`h-8 rounded flex items-center justify-center font-mono font-bold text-[11px] border transition-all ${
                      isCut
                        ? "bg-destructive text-destructive-foreground border-destructive shadow-sm"
                        : "bg-background text-foreground border-border hover:bg-muted"
                    }`}
                    title={isCut ? `Fibra #${fiberNum}: CORTADA` : `Fibra #${fiberNum}: PASSANTE`}
                  >
                    {fiberNum}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Painel de Pré-visualização do Impacto */}
          {isPreviewLoading ? (
            <div className="p-4 text-center text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Calculando novo traçado e impacto óptico...</span>
            </div>
          ) : preview ? (
            <div className="rounded-lg border border-border bg-card p-3 space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold text-foreground border-b border-border/50 pb-1.5">
                <span>Pré-visualização do Novo Traçado</span>
                <span className="text-primary font-mono font-bold">
                  {cutFiberNumbers.length} cortadas / {totalFibers - cutFiberNumbers.length} passantes
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded border border-border bg-muted/20 p-2">
                  <p className="font-bold text-foreground">Novo Trecho 1</p>
                  <p className="text-muted-foreground">
                    Extensão: ~{preview.segment_1_map_length_m.toFixed(1)} m
                  </p>
                </div>
                <div className="rounded border border-border bg-muted/20 p-2">
                  <p className="font-bold text-foreground">Novo Trecho 2</p>
                  <p className="text-muted-foreground">
                    Extensão: ~{preview.segment_2_map_length_m.toFixed(1)} m
                  </p>
                </div>
              </div>

              {preview.warnings && preview.warnings.length > 0 && (
                <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2 space-y-1">
                  <p className="text-amber-600 font-semibold text-[11px]">Avisos Operacionais:</p>
                  <ul className="list-disc pl-4 text-[10px] text-amber-700">
                    {preview.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : null}
        </div>

        <DialogFooter className="pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={handleConfirmSplit}
            disabled={isSubmitting || !selectedStructureId}
            className="gap-1.5"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Confirmar Divisão do Trecho
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
