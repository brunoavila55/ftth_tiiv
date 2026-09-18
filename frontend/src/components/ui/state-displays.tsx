"use client";

import * as React from "react";
import Link from "next/link";
import {
  Loader2,
  Inbox,
  TriangleAlert,
  Construction,
  RefreshCw,
  ArrowLeft,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApiError } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------------------
 * LoadingState
 * ------------------------------------------------------------------------- */
export interface LoadingStateProps {
  message?: string;
  description?: string;
  className?: string;
  size?: "sm" | "default" | "lg";
}

export function LoadingState({
  message = "Carregando dados ópticos...",
  description,
  className,
  size = "default",
}: LoadingStateProps) {
  const iconSize = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-8 w-8" : "h-6 w-6";
  const padding = size === "sm" ? "py-4" : size === "lg" ? "py-16" : "py-10";

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("flex flex-col items-center justify-center text-center", padding, className)}
    >
      <Loader2 className={cn("animate-spin text-primary", iconSize)} aria-hidden="true" />
      <p className="mt-3 text-sm font-medium text-foreground">{message}</p>
      {description && <p className="mt-1 text-xs text-muted-foreground max-w-sm">{description}</p>}
      <span className="sr-only">Carregando...</span>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * EmptyState
 * ------------------------------------------------------------------------- */
export interface EmptyStateProps {
  icon?: LucideIcon;
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionHref?: string;
  className?: string;
}

export function EmptyState({
  icon: Icon = Inbox,
  title = "Nenhum registro encontrado",
  description = "Não há elementos cadastrados ou correspondentes aos filtros aplicados.",
  actionLabel,
  onAction,
  actionHref,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border p-8 text-center",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground mb-4">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1.5 text-sm text-muted-foreground max-w-md">{description}</p>
      )}
      {(actionLabel && (onAction || actionHref)) && (
        <div className="mt-5">
          {actionHref ? (
            <Button asChild size="sm">
              <Link href={actionHref}>{actionLabel}</Link>
            </Button>
          ) : (
            <Button size="sm" onClick={onAction}>
              {actionLabel}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * ErrorState
 * ------------------------------------------------------------------------- */
export interface ErrorStateProps {
  title?: string;
  error?: Error | ApiError | string | null;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Ocorreu uma falha na operação",
  error,
  onRetry,
  className,
}: ErrorStateProps) {
  let detailMessage = "Não foi possível completar a requisição. Tente novamente mais tarde.";
  let statusCode: number | undefined;
  let requestId: string | undefined;

  if (error instanceof ApiError) {
    detailMessage = error.detail || error.message;
    statusCode = error.status;
    requestId = error.requestId;
  } else if (error instanceof Error) {
    detailMessage = error.message;
  } else if (typeof error === "string") {
    detailMessage = error;
  }

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-destructive/20 bg-destructive/5 p-8 text-center",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive mb-4">
        <TriangleAlert className="h-6 w-6" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="mt-1.5 text-sm text-muted-foreground max-w-md">{detailMessage}</p>

      {(statusCode || requestId) && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          {statusCode && (
            <span className="font-mono bg-muted px-1.5 py-0.5 rounded">HTTP {statusCode}</span>
          )}
          {requestId && (
            <span className="font-mono bg-muted px-1.5 py-0.5 rounded">ID: {requestId}</span>
          )}
        </div>
      )}

      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-5 gap-1.5">
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Tentar novamente</span>
        </Button>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * DevFeatureState (Para rotas em desenvolvimento)
 * ------------------------------------------------------------------------- */
export interface DevFeatureStateProps {
  title: string;
  stageName?: string;
  description?: string;
  className?: string;
}

export function DevFeatureState({
  title,
  stageName = "Em desenvolvimento",
  description = "Este módulo está planejado na matriz de implementação do FTTH Manager e respeita rigorosamente os contratos da API.",
  className,
}: DevFeatureStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-border bg-card p-10 text-center shadow-sm",
        className
      )}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary mb-4">
        <Construction className="h-7 w-7" aria-hidden="true" />
      </div>

      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-xl font-bold text-foreground">{title}</h2>
        <Badge variant="secondary">{stageName}</Badge>
      </div>

      <p className="text-sm text-muted-foreground max-w-lg mb-6">{description}</p>

      <Button variant="outline" asChild size="sm">
        <Link href="/" className="gap-1.5">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Voltar ao Início</span>
        </Link>
      </Button>
    </div>
  );
}
