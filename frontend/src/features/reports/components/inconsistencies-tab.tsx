"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  AlertOctagon,
  Filter,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { getInconsistenciesReport } from "@/features/reports/api";
import type { InconsistencyReportItem } from "@/features/reports/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState, EmptyState, ErrorState } from "@/components/ui/state-displays";

const INCONSISTENCY_TYPE_LABELS: Record<string, string> = {
  cable_without_segments: "Cabo sem segmentos georreferenciados",
  zero_effective_length: "Segmento com metragem zerada ou negativa",
  structure_without_site: "Estrutura sem POP / Site de referência",
  damaged_port: "Porta física com avaria ou defeito",
};

export function InconsistenciesTab() {
  const [page, setPage] = React.useState(1);
  const pageSize = 20;

  const [severityInput, setSeverityInput] = React.useState<string>("all");
  const [typeInput, setTypeInput] = React.useState<string>("all");

  const [appliedSeverity, setAppliedSeverity] = React.useState<string>("all");
  const [appliedType, setAppliedType] = React.useState<string>("all");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "inconsistencies", page],
    queryFn: ({ signal }) =>
      getInconsistenciesReport(
        {
          page,
          page_size: pageSize,
        },
        signal
      ),
    staleTime: 30_000,
  });

  const rawItems = React.useMemo(() => data?.items ?? [], [data?.items]);
  const totalRawItems = data?.total ?? 0;

  // Filtragem local se aplicável
  const filteredItems = React.useMemo(() => {
    return rawItems.filter((item) => {
      if (appliedSeverity !== "all" && item.severity !== appliedSeverity) {
        return false;
      }
      if (appliedType !== "all" && item.inconsistency_type !== appliedType) {
        return false;
      }
      return true;
    });
  }, [rawItems, appliedSeverity, appliedType]);

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    setAppliedSeverity(severityInput);
    setAppliedType(typeInput);
  };

  const handleResetFilters = () => {
    setSeverityInput("all");
    setTypeInput("all");
    setAppliedSeverity("all");
    setAppliedType("all");
  };

  // Contadores
  const criticalCount = rawItems.filter((i) => i.severity === "critical").length;
  const warningCount = rawItems.filter((i) => i.severity === "warning").length;
  const infoCount = rawItems.filter((i) => i.severity === "info").length;
  const totalPages = Math.ceil(totalRawItems / pageSize) || 1;

  const getEntityHref = (item: InconsistencyReportItem): string => {
    switch (item.entity_type) {
      case "cable":
        return `/cables/${item.entity_id}`;
      case "structure":
        return `/ctos/${item.entity_id}`;
      case "site":
        return `/sites/${item.entity_id}`;
      default:
        return "#";
    }
  };

  return (
    <div className="space-y-6">
      {/* Cards de Resumo Executivo */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Total de Pendências Detectadas
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalRawItems}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Anomalias que afetam a integridade cadastral
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Inconsistências Críticas
            </CardTitle>
            <AlertOctagon className="h-4 w-4 text-red-600 dark:text-red-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {criticalCount}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Impactam cálculo óptico ou rota física
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Alertas e Advertências
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {warningCount}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Pendências cadastrais secundárias
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Observações Informativas
            </CardTitle>
            <CheckCircle2 className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {infoCount}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Notas informativas sem impacto imediato
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Barra de Filtros */}
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <form onSubmit={handleApplyFilters} className="flex flex-col sm:flex-row gap-4 items-end justify-between">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full sm:w-auto">
            <div className="space-y-1.5 w-full sm:w-56">
              <Label htmlFor="incons-severity-filter" className="text-xs">
                Severidade
              </Label>
              <select
                id="incons-severity-filter"
                value={severityInput}
                onChange={(e) => setSeverityInput(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="all">Todas as severidades</option>
                <option value="critical">Crítica (critical)</option>
                <option value="warning">Alerta (warning)</option>
                <option value="info">Informativo (info)</option>
              </select>
            </div>

            <div className="space-y-1.5 w-full sm:w-64">
              <Label htmlFor="incons-type-filter" className="text-xs">
                Tipo de Anomalia
              </Label>
              <select
                id="incons-type-filter"
                value={typeInput}
                onChange={(e) => setTypeInput(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="all">Todos os tipos</option>
                <option value="cable_without_segments">Cabo sem segmentos</option>
                <option value="zero_effective_length">Metragem zerada / negativa</option>
                <option value="structure_without_site">Estrutura sem POP pai</option>
                <option value="damaged_port">Porta física avariada</option>
              </select>
            </div>
          </div>

          <div className="flex gap-2 w-full sm:w-auto justify-end">
            <Button type="submit" size="sm" className="h-9 text-xs">
              <Filter className="h-3.5 w-3.5 mr-1.5" />
              Filtrar
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleResetFilters}
              className="h-9 text-xs"
              title="Limpar filtros"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              Limpar
            </Button>
          </div>
        </form>
      </div>

      {/* Conteúdo / Tabela */}
      {isLoading ? (
        <div className="py-12">
          <LoadingState
            message="Diagnosticando pendências cadastrais e anomalias de malha..."
            description="Cruzando segmentos, cálculos de atenuação e metadados de infraestrutura."
          />
        </div>
      ) : isError ? (
        <ErrorState
          title="Erro ao carregar relatório de inconsistências"
          error={error}
          onRetry={() => refetch()}
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="Nenhuma anomalia técnica encontrada"
          description="A malha física e lógica está 100% íntegra segundo os critérios auditados pelo sistema."
        />
      ) : (
        <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 border-b text-muted-foreground uppercase text-[10px] font-semibold tracking-wider">
                <tr>
                  <th className="px-4 py-3">Severidade</th>
                  <th className="px-4 py-3">Tipo de Anomalia</th>
                  <th className="px-4 py-3">Elemento / Código</th>
                  <th className="px-4 py-3">Descrição Técnica</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredItems.map((item, idx) => {
                  const isCrit = item.severity === "critical";
                  const friendlyType =
                    INCONSISTENCY_TYPE_LABELS[item.inconsistency_type] ||
                    item.inconsistency_type;

                  return (
                    <tr key={`${item.entity_id}-${idx}`} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3">
                        <Badge
                          variant={isCrit ? "destructive" : "outline"}
                          className={`text-[10px] px-2 py-0.5 gap-1 inline-flex items-center ${
                            !isCrit
                              ? "bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-400"
                              : ""
                          }`}
                        >
                          {isCrit ? (
                            <AlertOctagon className="h-3 w-3" />
                          ) : (
                            <AlertTriangle className="h-3 w-3" />
                          )}
                          <span className="capitalize">{item.severity}</span>
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-medium text-foreground">
                        {friendlyType}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-primary">
                        {item.code}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-md">
                        {item.description}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link href={getEntityHref(item)}>
                          <Button variant="ghost" size="sm" className="h-7 text-xs px-2 gap-1">
                            <span>Ver elemento</span>
                            <ExternalLink className="h-3 w-3" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Paginação */}
          <div className="flex items-center justify-between px-4 py-3 border-t bg-card text-xs text-muted-foreground">
            <div>
              Mostrando {filteredItems.length} de {totalRawItems} inconsistências
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
                <span className="sr-only">Página anterior</span>
              </Button>
              <span className="text-xs">
                Página {page} de {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
                <span className="sr-only">Próxima página</span>
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
