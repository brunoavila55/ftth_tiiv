"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Cable as CableIcon,
  Download,
  Filter,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Percent,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { getCableCapacityReport } from "@/features/reports/api";
import type { CableReportFilters } from "@/features/reports/types";
import { formatPtBrNumber } from "@/lib/format/numbers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState, EmptyState, ErrorState } from "@/components/ui/state-displays";

export function CableCapacityTab() {
  const [page, setPage] = React.useState(1);
  const pageSize = 20;

  // Filtros locais do formulário
  const [statusInput, setStatusInput] = React.useState<string>("all");
  const [minUsageInput, setMinUsageInput] = React.useState<string>("");

  // Filtros aplicados
  const [appliedFilters, setAppliedFilters] = React.useState<CableReportFilters>({
    page: 1,
    page_size: pageSize,
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "cables", appliedFilters, page],
    queryFn: ({ signal }) =>
      getCableCapacityReport(
        {
          ...appliedFilters,
          page,
          page_size: pageSize,
        },
        signal
      ),
    staleTime: 30_000,
  });

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setAppliedFilters({
      status: statusInput !== "all" ? statusInput : undefined,
      min_usage_pct: minUsageInput !== "" ? Number(minUsageInput) : undefined,
    });
  };

  const handleResetFilters = () => {
    setStatusInput("all");
    setMinUsageInput("");
    setPage(1);
    setAppliedFilters({ page: 1, page_size: pageSize });
  };

  const items = data?.items ?? [];
  const totalItems = data?.total ?? 0;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;

  // Métricas agregadas
  const totalFibersSum = items.reduce((acc, c) => acc + c.total_fibers, 0);
  const connectedFibersSum = items.reduce((acc, c) => acc + c.connected_fibers, 0);
  const reservedFibersSum = items.reduce((acc, c) => acc + c.reserved_fibers, 0);
  const freeFibersSum = items.reduce((acc, c) => acc + c.free_fibers, 0);
  const damagedFibersSum = items.reduce((acc, c) => acc + c.damaged_fibers, 0);
  const usedFibers = connectedFibersSum + reservedFibersSum;
  const overallUsagePct = totalFibersSum > 0 ? (usedFibers / totalFibersSum) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Cards de Resumo Executivo */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Total de Cabos na Consulta
            </CardTitle>
            <CableIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalItems}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {totalFibersSum} fibras ópticas catalogadas
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Utilização Média Global
            </CardTitle>
            <Percent className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatPtBrNumber(overallUsagePct, { minDecimals: 1, maxDecimals: 1 })}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {usedFibers} de {totalFibersSum} fibras comprometidas
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Fibras Disponíveis (Livres)
            </CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {freeFibersSum}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Prontas para ativação ou expansão
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Fibras Danificadas / Defeito
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {damagedFibersSum}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Avariadas ou indisponíveis
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Barra de Filtros e Exportação */}
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <form onSubmit={handleApplyFilters} className="flex flex-col sm:flex-row gap-4 items-end justify-between">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full sm:w-auto">
            <div className="space-y-1.5 w-full sm:w-56">
              <Label htmlFor="cable-status-filter" className="text-xs">
                Status do Cabo
              </Label>
              <select
                id="cable-status-filter"
                value={statusInput}
                onChange={(e) => setStatusInput(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="all">Todos os status</option>
                <option value="installed">Instalado (installed)</option>
                <option value="planned">Planejado (planned)</option>
                <option value="maintenance">Em Manutenção</option>
                <option value="retired">Aposentado (retired)</option>
              </select>
            </div>

            <div className="space-y-1.5 w-full sm:w-48">
              <Label htmlFor="cable-min-usage" className="text-xs">
                Utilização Mínima (%)
              </Label>
              <Input
                id="cable-min-usage"
                type="number"
                min={0}
                max={100}
                placeholder="Ex: 50"
                value={minUsageInput}
                onChange={(e) => setMinUsageInput(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2 w-full sm:w-auto justify-end">
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
            <Link href="/exports?layer=cables">
              <Button type="button" variant="secondary" size="sm" className="h-9 text-xs">
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Exportar Camada Cabos
              </Button>
            </Link>
          </div>
        </form>
      </div>

      {/* Tabela de Cabos */}
      {isLoading ? (
        <div className="py-12">
          <LoadingState
            message="Calculando capacidade óptica de cabos e balanço de fibras..."
            description="Computando fibras conectadas, reservas e estado de ocupação por tubo loose."
          />
        </div>
      ) : isError ? (
        <ErrorState
          title="Erro ao carregar relatório de cabos"
          error={error}
          onRetry={() => refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={CableIcon}
          title="Nenhum cabo óptico encontrado com os filtros selecionados"
          description="Tente ajustar os parâmetros de utilização ou status para encontrar os cabos correspondentes."
          actionLabel="Limpar Filtros"
          onAction={handleResetFilters}
        />
      ) : (
        <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 border-b text-muted-foreground uppercase text-[10px] font-semibold tracking-wider">
                <tr>
                  <th className="px-4 py-3">Código do Cabo</th>
                  <th className="px-4 py-3">Modelo</th>
                  <th className="px-4 py-3 text-center">Fibras Totais</th>
                  <th className="px-4 py-3 text-center">Conectadas</th>
                  <th className="px-4 py-3 text-center">Reservadas</th>
                  <th className="px-4 py-3 text-center">Livres</th>
                  <th className="px-4 py-3 text-center">Danificadas</th>
                  <th className="px-4 py-3 min-w-[180px]">Taxa de Utilização</th>
                  <th className="px-4 py-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((cable) => {
                  const pct = cable.usage_pct;
                  let badgeClass = "bg-green-500/10 text-green-700 border-green-500/30 dark:text-green-400";
                  let label = "Folga ampla";

                  if (pct > 0 && pct <= 50) {
                    badgeClass = "bg-blue-500/10 text-blue-700 border-blue-500/30 dark:text-blue-400";
                    label = "Baixa ocupação";
                  } else if (pct > 50 && pct < 80) {
                    badgeClass = "bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-400";
                    label = "Moderada";
                  } else if (pct >= 80 && pct < 100) {
                    badgeClass = "bg-orange-500/10 text-orange-700 border-orange-500/30 dark:text-orange-400";
                    label = "Saturação alta";
                  } else if (pct >= 100) {
                    badgeClass = "bg-red-500/10 text-red-700 border-red-500/30 dark:text-red-400";
                    label = "Saturado (100%)";
                  }

                  return (
                    <tr key={cable.cable_id} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3 font-medium text-foreground">
                        <Link
                          href={`/cables/${cable.cable_id}`}
                          className="hover:underline text-primary"
                        >
                          {cable.code}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground font-mono text-[11px]">
                        {cable.model}
                      </td>
                      <td className="px-4 py-3 text-center font-medium">
                        {cable.total_fibers}
                      </td>
                      <td className="px-4 py-3 text-center text-primary font-medium">
                        {cable.connected_fibers}
                      </td>
                      <td className="px-4 py-3 text-center text-amber-600 dark:text-amber-400">
                        {cable.reserved_fibers}
                      </td>
                      <td className="px-4 py-3 text-center text-green-600 dark:text-green-400 font-medium">
                        {cable.free_fibers}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {cable.damaged_fibers > 0 ? (
                          <span className="text-red-600 dark:text-red-400 font-bold">
                            {cable.damaged_fibers}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-semibold">{formatPtBrNumber(pct, { minDecimals: 1, maxDecimals: 1 })}%</span>
                            <Badge variant="outline" className={`text-[10px] px-1.5 py-0 h-4 border ${badgeClass}`}>
                              {label}
                            </Badge>
                          </div>
                          {/* Barra de progresso visual */}
                          <div className="w-full bg-secondary rounded-full h-2 overflow-hidden flex">
                            <div
                              className={`h-full transition-all ${
                                pct >= 100
                                  ? "bg-red-600"
                                  : pct >= 80
                                  ? "bg-orange-500"
                                  : pct > 50
                                  ? "bg-amber-500"
                                  : "bg-blue-600"
                              }`}
                              style={{ width: `${Math.min(pct, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Badge variant="outline" className="capitalize text-[11px]">
                          {cable.status}
                        </Badge>
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
              Mostrando {items.length} de {totalItems} cabos ópticos
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
