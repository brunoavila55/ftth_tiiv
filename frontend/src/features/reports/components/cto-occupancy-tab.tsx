"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Download,
  Filter,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Percent,
} from "lucide-react";
import { getCTOOccupancyReport } from "@/features/reports/api";
import type { CTOReportFilters } from "@/features/reports/types";
import { formatPtBrNumber } from "@/lib/format/numbers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState, EmptyState, ErrorState } from "@/components/ui/state-displays";

export function CTOOccupancyTab() {
  const [page, setPage] = React.useState(1);
  const pageSize = 20;

  // Filtros locais do formulário
  const [statusInput, setStatusInput] = React.useState<string>("all");
  const [minOccInput, setMinOccInput] = React.useState<string>("");
  const [maxOccInput, setMaxOccInput] = React.useState<string>("");

  // Filtros aplicados na query
  const [appliedFilters, setAppliedFilters] = React.useState<CTOReportFilters>({
    page: 1,
    page_size: pageSize,
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reports", "ctos", appliedFilters, page],
    queryFn: ({ signal }) =>
      getCTOOccupancyReport(
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
      min_occupancy_pct: minOccInput !== "" ? Number(minOccInput) : undefined,
      max_occupancy_pct: maxOccInput !== "" ? Number(maxOccInput) : undefined,
    });
  };

  const handleResetFilters = () => {
    setStatusInput("all");
    setMinOccInput("");
    setMaxOccInput("");
    setPage(1);
    setAppliedFilters({ page: 1, page_size: pageSize });
  };

  const items = data?.items ?? [];
  const totalItems = data?.total ?? 0;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;

  // Métricas agregadas da amostra
  const totalPortsSum = items.reduce((acc, i) => acc + i.total_ports, 0);
  const occupiedPortsSum = items.reduce((acc, i) => acc + i.occupied_ports, 0);
  const avgOccupancy =
    totalPortsSum > 0 ? (occupiedPortsSum / totalPortsSum) * 100 : 0;
  const criticalCount = items.filter((i) => i.occupancy_pct >= 80 && i.occupancy_pct < 100).length;
  const fullCount = items.filter((i) => i.occupancy_pct >= 100).length;

  return (
    <div className="space-y-6">
      {/* Cards de Resumo Executivo */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Total de CTOs na Consulta
            </CardTitle>
            <Box className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalItems}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Caixas de terminação avaliadas
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Média de Ocupação
            </CardTitle>
            <Percent className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatPtBrNumber(avgOccupancy, { minDecimals: 1, maxDecimals: 1 })}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {occupiedPortsSum} de {totalPortsSum} portas ocupadas
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              CTOs Críticas (≥ 80%)
            </CardTitle>
            <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {criticalCount}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Próximas ao limite de capacidade
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              CTOs Esgotadas (100%)
            </CardTitle>
            <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {fullCount}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Sem disponibilidade para novos clientes
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Barra de Filtros e Exportação */}
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <form onSubmit={handleApplyFilters} className="flex flex-col lg:flex-row gap-4 items-end justify-between">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full lg:w-auto">
            <div className="space-y-1.5">
              <Label htmlFor="cto-status-filter" className="text-xs">
                Status Operacional
              </Label>
              <select
                id="cto-status-filter"
                value={statusInput}
                onChange={(e) => setStatusInput(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="all">Todos os status</option>
                <option value="installed">Instalada (installed)</option>
                <option value="planned">Planejada (planned)</option>
                <option value="maintenance">Em Manutenção</option>
                <option value="retired">Aposentada (retired)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="cto-min-occ" className="text-xs">
                Ocupação Mínima (%)
              </Label>
              <Input
                id="cto-min-occ"
                type="number"
                min={0}
                max={100}
                placeholder="Ex: 50"
                value={minOccInput}
                onChange={(e) => setMinOccInput(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="cto-max-occ" className="text-xs">
                Ocupação Máxima (%)
              </Label>
              <Input
                id="cto-max-occ"
                type="number"
                min={0}
                max={100}
                placeholder="Ex: 100"
                value={maxOccInput}
                onChange={(e) => setMaxOccInput(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2 w-full lg:w-auto justify-end">
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
            <Link href="/exports?layer=ctos">
              <Button type="button" variant="secondary" size="sm" className="h-9 text-xs">
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Exportar Camada CTOs
              </Button>
            </Link>
          </div>
        </form>
      </div>

      {/* Conteúdo Principal / Tabela */}
      {isLoading ? (
        <div className="py-12">
          <LoadingState
            message="Calculando capacidade e ocupação das caixas de terminação óptica..."
            description="Processando portas ativas, reservas de terminais e disponibilidade de drop."
          />
        </div>
      ) : isError ? (
        <ErrorState
          title="Erro ao carregar relatório de CTOs"
          error={error}
          onRetry={() => refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Box}
          title="Nenhuma caixa CTO encontrada com os filtros selecionados"
          description="Tente ajustar os parâmetros de ocupação mínima/máxima ou limpe os filtros para visualizar todas as caixas."
          actionLabel="Limpar Filtros"
          onAction={handleResetFilters}
        />
      ) : (
        <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 border-b text-muted-foreground uppercase text-[10px] font-semibold tracking-wider">
                <tr>
                  <th className="px-4 py-3">Código CTO</th>
                  <th className="px-4 py-3">POP / Site</th>
                  <th className="px-4 py-3 text-center">Portas Totais</th>
                  <th className="px-4 py-3 text-center">Ocupadas</th>
                  <th className="px-4 py-3 text-center">Reservadas</th>
                  <th className="px-4 py-3 text-center">Livres</th>
                  <th className="px-4 py-3 min-w-[180px]">Taxa de Ocupação</th>
                  <th className="px-4 py-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((cto) => {
                  const pct = cto.occupancy_pct;
                  let badgeClass = "bg-green-500/10 text-green-700 border-green-500/30 dark:text-green-400";
                  let label = "Livre (0%)";

                  if (pct > 0 && pct <= 50) {
                    badgeClass = "bg-blue-500/10 text-blue-700 border-blue-500/30 dark:text-blue-400";
                    label = "Baixa";
                  } else if (pct > 50 && pct < 80) {
                    badgeClass = "bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-400";
                    label = "Moderada";
                  } else if (pct >= 80 && pct < 100) {
                    badgeClass = "bg-orange-500/10 text-orange-700 border-orange-500/30 dark:text-orange-400";
                    label = "Crítica";
                  } else if (pct >= 100) {
                    badgeClass = "bg-red-500/10 text-red-700 border-red-500/30 dark:text-red-400";
                    label = "Esgotada";
                  }

                  return (
                    <tr key={cto.structure_id} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3 font-medium text-foreground">
                        <Link
                          href={`/ctos/${cto.structure_id}`}
                          className="hover:underline text-primary"
                        >
                          {cto.code}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {cto.site_name || "—"}
                      </td>
                      <td className="px-4 py-3 text-center font-medium">
                        {cto.total_ports}
                      </td>
                      <td className="px-4 py-3 text-center text-primary font-medium">
                        {cto.occupied_ports}
                      </td>
                      <td className="px-4 py-3 text-center text-amber-600 dark:text-amber-400">
                        {cto.reserved_ports}
                      </td>
                      <td className="px-4 py-3 text-center text-green-600 dark:text-green-400 font-medium">
                        {cto.free_ports}
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
                          {cto.status}
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
              Mostrando {items.length} de {totalItems} caixas CTO
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
