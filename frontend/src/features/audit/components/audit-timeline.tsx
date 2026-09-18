"use client";

import * as React from "react";
import { History, Loader2, RefreshCw, User, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { type AuditEvent } from "../types";
import { formatAuditAction, formatAuditEntityType, listAuditEvents } from "../api";

interface AuditTimelineProps {
  entityType?: string;
  entityId?: string;
  actorId?: string;
  action?: string;
  title?: string;
  description?: string;
}

export function AuditTimeline({
  entityType,
  entityId,
  actorId,
  action,
  title = "Histórico de Auditoria",
  description = "Registro append-only de mutações, conexões e operações técnicas",
}: AuditTimelineProps) {
  const [events, setEvents] = React.useState<AuditEvent[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [expandedEvents, setExpandedEvents] = React.useState<Record<string, boolean>>({});

  const fetchEvents = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await listAuditEvents({
        entity_type: entityType,
        entity_id: entityId,
        actor_id: actorId,
        action,
        page: 1,
        page_size: 50,
      });
      setEvents(resp.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Falha ao carregar trilha de auditoria";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [entityType, entityId, actorId, action]);

  React.useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const toggleExpand = (id: string) => {
    setExpandedEvents((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const formatDate = (isoString: string) => {
    try {
      return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "medium",
      }).format(new Date(isoString));
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b pb-3">
        <div>
          <h3 className="text-base font-semibold flex items-center gap-2">
            <History className="h-4 w-4 text-primary" />
            {title}
          </h3>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchEvents}
          disabled={loading}
          className="h-8 text-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
          Atualizar
        </Button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center p-8 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin text-primary mb-2" />
          <p className="text-sm">Consultando histórico imutável...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive font-medium mb-2">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchEvents}>
            Tentar novamente
          </Button>
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center bg-muted/10">
          <History className="h-8 w-8 text-muted-foreground/60 mb-2" />
          <h4 className="text-sm font-medium">Nenhum registro de auditoria</h4>
          <p className="text-xs text-muted-foreground max-w-sm mt-1">
            As alterações realizadas neste elemento serão registradas aqui de forma imutável.
          </p>
        </div>
      ) : (
        <div className="relative pl-6 border-l-2 border-muted space-y-6 ml-2">
          {events.map((ev) => {
            const actionInfo = formatAuditAction(ev.action);
            const isExpanded = !!expandedEvents[ev.id];
            const hasChanges = Object.keys(ev.changes || {}).length > 0;

            return (
              <div key={ev.id} className="relative group">
                {/* Marcador na linha */}
                <div className="absolute -left-[31px] top-1 h-3.5 w-3.5 rounded-full border-2 border-background bg-primary shadow" />

                <div className="rounded-lg border bg-card p-3.5 shadow-sm space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant={actionInfo.variant} className="text-xs font-semibold">
                        {actionInfo.label}
                      </Badge>
                      <span className="text-xs text-muted-foreground font-mono">
                        {ev.action}
                      </span>
                      {(!entityType || !entityId) && (
                        <span className="text-xs font-medium text-foreground/80 bg-muted px-2 py-0.5 rounded">
                          {formatAuditEntityType(ev.entity_type)}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground">{formatDate(ev.created_at)}</span>
                  </div>

                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <User className="h-3.5 w-3.5 text-primary/80" />
                    <span>
                      Ator: <strong className="text-foreground">{ev.actor_name}</strong>
                    </span>
                  </div>

                  {ev.reason && (
                    <p className="text-xs text-muted-foreground/90 bg-muted/30 p-2 rounded border">
                      <strong>Motivo:</strong> {ev.reason}
                    </p>
                  )}

                  {hasChanges && (
                    <div>
                      <button
                        type="button"
                        onClick={() => toggleExpand(ev.id)}
                        className="flex items-center gap-1 text-xs font-medium text-primary hover:underline cursor-pointer"
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                        {isExpanded ? "Ocultar detalhes técnicos" : "Ver alterações (Antes/Depois)"}
                      </button>

                      {isExpanded && (
                        <div className="mt-2 rounded bg-muted/40 p-2.5 font-mono text-[11px] overflow-x-auto border">
                          <pre className="whitespace-pre-wrap break-all">
                            {JSON.stringify(ev.changes, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
