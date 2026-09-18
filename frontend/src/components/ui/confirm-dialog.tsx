"use client";

import * as React from "react";
import { Loader2, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "destructive" | "default";
  isLoading?: boolean;
  /** Se informado, o usuário precisará digitar exatamente este texto para habilitar o botão de confirmação */
  verificationText?: string;
  onConfirm: () => void | Promise<void>;
  onCancel?: () => void;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  variant = "destructive",
  isLoading = false,
  verificationText,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [typedVerification, setTypedVerification] = React.useState("");
  const dialogRef = React.useRef<HTMLDivElement>(null);
  const previousActiveElement = React.useRef<HTMLElement | null>(null);

  // Guarda elemento focado ao abrir e restaura ao fechar
  React.useEffect(() => {
    if (open) {
      previousActiveElement.current = document.activeElement as HTMLElement;
      setTypedVerification("");
    } else {
      previousActiveElement.current?.focus();
    }
  }, [open]);

  const handleCancel = React.useCallback(() => {
    if (isLoading) return;
    onCancel?.();
    onOpenChange(false);
  }, [isLoading, onCancel, onOpenChange]);

  // Tecla Escape para fechar
  React.useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isLoading) {
        handleCancel();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, isLoading, handleCancel]);

  if (!open) return null;

  const isVerificationSatisfied =
    !verificationText || typedVerification.trim() === verificationText.trim();

  const handleConfirm = async () => {
    if (!isVerificationSatisfied || isLoading) return;
    await onConfirm();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-desc"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={handleCancel}
        aria-hidden="true"
      />

      {/* Conteúdo do Modal */}
      <div
        ref={dialogRef}
        className={cn(
          "relative z-50 w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-xl animate-in fade-in-0 zoom-in-95"
        )}
      >
        <div className="flex items-start gap-4">
          {variant === "destructive" && (
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <TriangleAlert className="h-5 w-5" aria-hidden="true" />
            </div>
          )}

          <div className="flex-1">
            <h2 id="confirm-dialog-title" className="text-lg font-semibold text-foreground">
              {title}
            </h2>
            <div id="confirm-dialog-desc" className="mt-2 text-sm text-muted-foreground">
              {description}
            </div>

            {verificationText && (
              <div className="mt-4 space-y-2">
                <Label htmlFor="verification-input" className="text-xs text-muted-foreground">
                  Para confirmar, digite <span className="font-semibold text-foreground">{verificationText}</span> abaixo:
                </Label>
                <Input
                  id="verification-input"
                  value={typedVerification}
                  onChange={(e) => setTypedVerification(e.target.value)}
                  placeholder={verificationText}
                  autoComplete="off"
                  disabled={isLoading}
                />
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={isLoading}
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={variant === "destructive" ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={!isVerificationSatisfied || isLoading}
            className="gap-2"
          >
            {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            <span>{confirmLabel}</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
