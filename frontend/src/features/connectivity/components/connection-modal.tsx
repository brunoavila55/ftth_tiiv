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
import { UnitInput } from "@/components/ui/unit-input";
import type {
  TerminalRead,
  ConnectionType,
  BatchOperationItem,
  TerminalKind,
} from "@/features/connectivity/api";
import { Zap, ArrowRight, AlertCircle } from "lucide-react";

export interface ConnectionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  terminals: TerminalRead[];
  initialTerminalAId?: string | null;
  occupiedTerminalIds: Set<string>;
  onAddOperation: (op: BatchOperationItem) => void;
}

export function formatTerminalKind(kind: TerminalKind): string {
  switch (kind) {
    case "fiber_endpoint":
      return "Ponta de Fibra";
    case "port_front":
      return "Porta (Frente)";
    case "port_back":
      return "Porta (Traseira)";
    case "splitter_input":
      return "Splitter (Entrada)";
    case "splitter_output":
      return "Splitter (Saída)";
    default:
      return kind;
  }
}

export function ConnectionModal({
  open,
  onOpenChange,
  terminals,
  initialTerminalAId,
  occupiedTerminalIds,
  onAddOperation,
}: ConnectionModalProps) {
  const [terminalAId, setTerminalAId] = React.useState<string>("");
  const [terminalBId, setTerminalBId] = React.useState<string>("");
  const [connectionType, setConnectionType] = React.useState<ConnectionType>("fusion_splice");
  const [lossDb, setLossDb] = React.useState<number>(0.1);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setErrorMsg(null);
      if (initialTerminalAId) {
        setTerminalAId(initialTerminalAId);
      } else {
        // Encontra o primeiro terminal livre disponível
        const firstFree = terminals.find((t) => !occupiedTerminalIds.has(t.id));
        setTerminalAId(firstFree?.id || "");
      }
      setTerminalBId("");
    }
  }, [open, initialTerminalAId, terminals, occupiedTerminalIds]);

  // Atualiza perda padrão ao trocar tipo de conexão
  const handleTypeChange = (type: ConnectionType) => {
    setConnectionType(type);
    if (type === "fusion_splice") setLossDb(0.1);
    else if (type === "patch_cord") setLossDb(0.2);
    else if (type === "internal_continuity") setLossDb(0.0);
  };

  const terminalA = terminals.find((t) => t.id === terminalAId);
  const terminalB = terminals.find((t) => t.id === terminalBId);

  // Lista de terminais B compatíveis (livres e diferentes de A)
  const availableTerminalsForB = React.useMemo(() => {
    return terminals.filter(
      (t) => t.id !== terminalAId && !occupiedTerminalIds.has(t.id)
    );
  }, [terminals, terminalAId, occupiedTerminalIds]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!terminalAId) {
      setErrorMsg("Selecione o terminal de origem (Terminal A).");
      return;
    }
    if (!terminalBId) {
      setErrorMsg("Selecione o terminal de destino compatível (Terminal B).");
      return;
    }
    if (terminalAId === terminalBId) {
      setErrorMsg("Os terminais de origem e destino devem ser distintos.");
      return;
    }
    if (occupiedTerminalIds.has(terminalAId)) {
      setErrorMsg(`O Terminal A (${terminalA?.label || terminalAId}) já está ocupado.`);
      return;
    }
    if (occupiedTerminalIds.has(terminalBId)) {
      setErrorMsg(`O Terminal B (${terminalB?.label || terminalBId}) já está ocupado.`);
      return;
    }

    onAddOperation({
      action: "connect",
      terminal_a_id: terminalAId,
      terminal_b_id: terminalBId,
      connection_type: connectionType,
      loss_db: lossDb,
    });

    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            <DialogTitle>Nova Conexão Óptica</DialogTitle>
          </div>
          <DialogDescription>
            Conecte dois terminais ópticos livres através de fusão, cordão (patch) ou continuidade interna.
            A operação será adicionada ao rascunho de lote.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {errorMsg && (
            <div className="flex items-start gap-2 p-3 text-xs bg-destructive/10 text-destructive rounded-md border border-destructive/20">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Terminal A */}
          <div className="space-y-1.5">
            <Label htmlFor="terminal-a-select" className="text-xs font-semibold">
              Terminal de Origem (Terminal A) *
            </Label>
            <select
              id="terminal-a-select"
              value={terminalAId}
              onChange={(e) => {
                setTerminalAId(e.target.value);
                if (e.target.value === terminalBId) setTerminalBId("");
              }}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring font-mono"
            >
              <option value="">Selecione o terminal A...</option>
              {terminals.map((t) => {
                const isOccupied = occupiedTerminalIds.has(t.id);
                return (
                  <option key={t.id} value={t.id} disabled={isOccupied}>
                    {t.label} ({formatTerminalKind(t.kind)}) {isOccupied ? "— [Ocupado]" : "— [Livre]"}
                  </option>
                );
              })}
            </select>
            {terminalA && (
              <div className="p-2 rounded bg-muted/40 text-[11px] text-muted-foreground flex items-center justify-between">
                <span>Tipo: <strong>{formatTerminalKind(terminalA.kind)}</strong></span>
                <span className="font-mono text-[10px] truncate max-w-[150px]">ID: {terminalA.id}</span>
              </div>
            )}
          </div>

          <div className="flex justify-center my-1 text-muted-foreground">
            <ArrowRight className="h-4 w-4" />
          </div>

          {/* Terminal B */}
          <div className="space-y-1.5">
            <Label htmlFor="terminal-b-select" className="text-xs font-semibold">
              Terminal de Destino (Terminal B) *
            </Label>
            <select
              id="terminal-b-select"
              value={terminalBId}
              onChange={(e) => setTerminalBId(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring font-mono"
            >
              <option value="">Selecione o terminal B compatível...</option>
              {availableTerminalsForB.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label} ({formatTerminalKind(t.kind)})
                </option>
              ))}
            </select>
            {terminalB && (
              <div className="p-2 rounded bg-muted/40 text-[11px] text-muted-foreground flex items-center justify-between">
                <span>Tipo: <strong>{formatTerminalKind(terminalB.kind)}</strong></span>
                <span className="font-mono text-[10px] truncate max-w-[150px]">ID: {terminalB.id}</span>
              </div>
            )}
            {availableTerminalsForB.length === 0 && (
              <p className="text-[11px] text-amber-600 dark:text-amber-400">
                Não há outros terminais livres nesta estrutura para conectar com o Terminal A.
              </p>
            )}
          </div>

          {/* Tipo de Conexão */}
          <div className="space-y-1.5">
            <Label htmlFor="conn-type-select" className="text-xs font-semibold">
              Tipo de Conexão Física *
            </Label>
            <select
              id="conn-type-select"
              value={connectionType}
              onChange={(e) => handleTypeChange(e.target.value as ConnectionType)}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="fusion_splice">Fusão Óptica (Fusion Splice) — Padrão 0.10 dB</option>
              <option value="patch_cord">Cordão Óptico / Acoplador (Patch Cord) — Padrão 0.20 dB</option>
              <option value="internal_continuity">Continuidade Interna (Pass-Through) — 0.00 dB</option>
            </select>
          </div>

          {/* Perda de Inserção */}
          <div className="space-y-1.5">
            <Label htmlFor="loss-db-input" className="text-xs font-semibold">
              Perda de Inserção Prevista *
            </Label>
            <UnitInput
              id="loss-db-input"
              unit="dB"
              type="number"
              step="0.01"
              min="0"
              max="10"
              value={lossDb}
              onChange={(val) => setLossDb(Number(val))}
              required
            />
            <span className="text-[10px] text-muted-foreground">
              A atenuação individual configurada impactará o orçamento óptico fim a fim e rastreamento OTDR.
            </span>
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
              type="submit"
              size="sm"
              disabled={!terminalAId || !terminalBId || availableTerminalsForB.length === 0}
            >
              Adicionar ao Lote
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
