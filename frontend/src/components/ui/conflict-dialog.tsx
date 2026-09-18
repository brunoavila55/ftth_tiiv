"use client";

import * as React from "react";
import { GitCompare, RefreshCw, AlertTriangle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ConflictFieldComparison {
  fieldName: string;
  fieldLabel: string;
  draftValue: unknown;
  remoteValue: unknown;
}

export interface ConflictDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entityName?: string;
  currentVersion?: string | number | null;
  remoteVersion?: string | number | null;
  differences?: ConflictFieldComparison[];
  onReloadRemote: () => void | Promise<void>;
  onOverwriteWithDraft?: () => void | Promise<void>;
  onCancel?: () => void;
}

export function ConflictDialog({
  open,
  onOpenChange,
  entityName = "Registro de Rede",
  currentVersion,
  remoteVersion,
  differences = [],
  onReloadRemote,
  onOverwriteWithDraft,
  onCancel,
}: ConflictDialogProps) {
  const [isLoading, setIsLoading] = React.useState(false);

  if (!open) return null;

  const handleReload = async () => {
    setIsLoading(true);
    try {
      await onReloadRemote();
      onOpenChange(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOverwrite = async () => {
    if (!onOverwriteWithDraft) return;
    setIsLoading(true);
    try {
      await onOverwriteWithDraft();
      onOpenChange(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDismiss = () => {
    onCancel?.();
    onOpenChange(false);
  };

  const formatDisplayValue = (val: unknown) => {
    if (val === null || val === undefined) return <span className="text-muted-foreground italic">—</span>;
    if (typeof val === "boolean") return val ? "Sim" : "Não";
    if (typeof val === "object") return JSON.stringify(val);
    return String(val);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="conflict-dialog-title"
      aria-describedby="conflict-dialog-desc"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={handleDismiss}
        aria-hidden="true"
      />

      {/* Conteúdo */}
      <div className="relative z-50 w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-2xl animate-in fade-in-0 zoom-in-95">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <GitCompare className="h-6 w-6" aria-hidden="true" />
          </div>

          <div className="flex-1 min-w-0">
            <h2 id="conflict-dialog-title" className="text-lg font-bold text-foreground">
              Conflito de Alteração Concorrente
            </h2>
            <p id="conflict-dialog-desc" className="mt-1 text-xs text-muted-foreground">
              O registro <span className="font-semibold text-foreground">{entityName}</span> foi modificado por outro operador ou processo no servidor (HTTP 412 / 409).
            </p>

            {(currentVersion || remoteVersion) && (
              <div className="mt-2.5 flex items-center gap-3 text-xs font-mono">
                <span className="bg-muted px-2 py-0.5 rounded text-muted-foreground">
                  Sua versão: {String(currentVersion || "inicial")}
                </span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <span className="bg-amber-500/10 text-amber-700 dark:text-amber-400 px-2 py-0.5 rounded font-semibold">
                  Versão no servidor: {String(remoteVersion || "atualizada")}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Comparativo de Campos */}
        {differences.length > 0 ? (
          <div className="mt-5 max-h-60 overflow-y-auto rounded-md border border-border">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/60 text-muted-foreground font-semibold border-b border-border">
                <tr>
                  <th className="p-2.5">Campo</th>
                  <th className="p-2.5">Seu Rascunho</th>
                  <th className="p-2.5">No Servidor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {differences.map((diff) => (
                  <tr key={diff.fieldName} className="hover:bg-accent/40">
                    <td className="p-2.5 font-medium text-foreground">{diff.fieldLabel}</td>
                    <td className="p-2.5 text-blue-600 dark:text-blue-400">
                      {formatDisplayValue(diff.draftValue)}
                    </td>
                    <td className="p-2.5 text-amber-600 dark:text-amber-400 font-semibold">
                      {formatDisplayValue(diff.remoteValue)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="mt-4 rounded-lg bg-muted/40 p-3 text-xs text-muted-foreground">
            O servidor possui dados mais recentes que a sua visualização atual. O FTTH Manager não sobrescreve dados concorrentes de forma silenciosa para garantir a integridade da planta física.
          </div>
        )}

        {/* Ações */}
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-end gap-2 sm:gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleDismiss}
            disabled={isLoading}
            className="w-full sm:w-auto"
          >
            Manter Rascunho na Tela
          </Button>

          {onOverwriteWithDraft && (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={handleOverwrite}
              disabled={isLoading}
              className="w-full sm:w-auto gap-1.5"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>Forçar Sobrescrita</span>
            </Button>
          )}

          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={handleReload}
            disabled={isLoading}
            className="w-full sm:w-auto gap-1.5"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
            <span>Recarregar do Servidor</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
