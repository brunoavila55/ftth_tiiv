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
import { ApiError } from "@/lib/api/types";
import { Loader2, AlertTriangle, Info } from "lucide-react";

export interface DependencyItem {
  label: string;
  count: number;
}

export interface DeactivationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  entityName: string;
  entityTypeLabel: string;
  version: number;
  dependencies?: DependencyItem[];
  onConfirm: () => Promise<void>;
  onSuccess: () => void;
}

export function DeactivationDialog({
  open,
  onOpenChange,
  title,
  entityName,
  entityTypeLabel,
  version,
  dependencies = [],
  onConfirm,
  onSuccess,
}: DeactivationDialogProps) {
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setErrorMessage(null);
      setIsSubmitting(false);
    }
  }, [open]);

  const hasBlockingDependencies = dependencies.some((d) => d.count > 0);

  const handleConfirm = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await onConfirm();
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.code === "referenced_entity_conflict" || err.status === 409) {
          setErrorMessage(
            `Operação bloqueada por integridade referencial: Este ${entityTypeLabel.toLowerCase()} possui dependências ativas associadas. Desvincule ou transfira os elementos vinculados antes de desativar.`
          );
        } else if (err.status === 412) {
          setErrorMessage(
            "Conflito de versão (412): Os dados foram modificados concorrentemente por outro operador. Recarregue a página antes de prosseguir."
          );
        } else {
          setErrorMessage(err.detail || err.message || "Falha ao desativar registro.");
        }
      } else {
        setErrorMessage("Erro inesperado de comunicação ao desativar o registro.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-destructive mb-1">
            <AlertTriangle className="h-5 w-5" />
            <DialogTitle>{title}</DialogTitle>
          </div>
          <DialogDescription>
            Confirme a desativação de <strong className="text-foreground">{entityName}</strong> (versão v{version}).
            Esta operação arquiva ou remove o registro do inventário ativo.
          </DialogDescription>
        </DialogHeader>

        {/* Verificação e Exibição de Dependências */}
        {dependencies.length > 0 && (
          <div className="rounded-md border border-border bg-muted/40 p-3 space-y-2 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <Info className="h-4 w-4 text-muted-foreground" />
              <span>Verificação de Vínculos e Dependências:</span>
            </div>
            <ul className="space-y-1 pl-5 list-disc text-muted-foreground">
              {dependencies.map((dep, idx) => (
                <li key={idx} className={dep.count > 0 ? "text-destructive font-medium" : ""}>
                  {dep.label}: <strong>{dep.count}</strong>
                </li>
              ))}
            </ul>
            {hasBlockingDependencies && (
              <p className="text-[11px] text-destructive pt-1">
                ⚠️ Existem vínculos ativos. A remoção será rejeitada pelo servidor para proteger a integridade da rede.
              </p>
            )}
          </div>
        )}

        {/* Mensagem de Erro Orientada */}
        {errorMessage && (
          <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive space-y-1">
            <p className="font-semibold">Não foi possível prosseguir:</p>
            <p>{errorMessage}</p>
          </div>
        )}

        <DialogFooter className="gap-2 pt-2 sm:space-x-0">
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
            variant="destructive"
            onClick={handleConfirm}
            disabled={isSubmitting}
            className="gap-1.5"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Confirmar Desativação
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
