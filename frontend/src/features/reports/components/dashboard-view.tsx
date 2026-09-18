"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  Box,
  Cable as CableIcon,
  Users,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  ArrowRight,
  GitBranch,
  Map,
  Activity,
  Layers,
  LayoutDashboard,
} from "lucide-react";
import { getDashboardSummary, type DashboardSummaryResponse } from "@/features/reports/api";
import { formatPtBrNumber } from "@/lib/format/numbers";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState, EmptyState, ErrorState } from "@/components/ui/state-displays";

export function DashboardView() {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<DashboardSummaryResponse>({
    queryKey: ["dashboard", "summary"],
    queryFn: ({ signal }) => getDashboardSummary(signal),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="py-12">
        <LoadingState
          message="Consultando indicadores consolidados da rede óptica..."
          description="Calculando métricas de ativos físicos, ocupação de caixas e revisão de topologia."
          size="lg"
        />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-6">
        <ErrorState
          title="Falha ao carregar dados do painel operacional"
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const isNetworkEmpty =
    data.total_sites === 0 &&
    data.total_structures === 0 &&
    data.total_cables === 0;

  if (isNetworkEmpty) {
    return (
      <div className="py-8">
        <EmptyState
          icon={LayoutDashboard}
          title="Nenhum elemento de rede documentado"
          description="A infraestrutura ainda não possui estações, cabos ou caixas registradas no banco de dados. Inicie cadastrando a primeira central técnica ou importando dados de projeto."
          actionLabel="Cadastrar Primeiro POP / Site"
          actionHref="/sites"
        />
      </div>
    );
  }

  // Cálculos de ocupação das CTOs
  const ctosTotal =
    data.ctos_occupancy.empty_0_pct +
    data.ctos_occupancy.low_1_to_50_pct +
    data.ctos_occupancy.high_51_to_99_pct +
    data.ctos_occupancy.full_100_pct;

  const pctEmpty = ctosTotal > 0 ? Math.round((data.ctos_occupancy.empty_0_pct / ctosTotal) * 100) : 0;
  const pctLow = ctosTotal > 0 ? Math.round((data.ctos_occupancy.low_1_to_50_pct / ctosTotal) * 100) : 0;
  const pctHigh = ctosTotal > 0 ? Math.round((data.ctos_occupancy.high_51_to_99_pct / ctosTotal) * 100) : 0;
  const pctFull = ctosTotal > 0 ? Math.round((data.ctos_occupancy.full_100_pct / ctosTotal) * 100) : 0;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Cabeçalho do Painel */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Painel Operacional
            </h1>
            <Badge variant="outline" className="font-mono text-xs gap-1 py-0.5">
              <GitBranch className="h-3 w-3" aria-hidden="true" />
              Revisão topológica: #{data.topology_revision}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Indicadores consolidados de infraestrutura física, ocupação óptica e integridade técnica.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="gap-2"
          >
            <RefreshCw
              className={`h-4 w-4 ${isFetching ? "animate-spin text-primary" : ""}`}
              aria-hidden="true"
            />
            <span>{isFetching ? "Atualizando..." : "Atualizar"}</span>
          </Button>
          <Button asChild size="sm">
            <Link href="/map" className="gap-2">
              <Map className="h-4 w-4" aria-hidden="true" />
              <span>Ver no Mapa</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Cards de Totais Operacionais */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card: POPs & Sites */}
        <Card className="hover:border-primary/40 transition-colors shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              POPs & Sites
            </CardTitle>
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Building2 className="h-4 w-4" aria-hidden="true" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tracking-tight text-foreground">
              {formatPtBrNumber(data.total_sites)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Estações centrais e abrigos
            </p>
            <div className="mt-4 pt-3 border-t border-border">
              <Link
                href="/sites"
                className="flex items-center text-xs font-medium text-primary hover:underline gap-1"
              >
                Gerenciar POPs
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Card: Estruturas & Postes */}
        <Card className="hover:border-primary/40 transition-colors shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Estruturas & Postes
            </CardTitle>
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <Box className="h-4 w-4" aria-hidden="true" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tracking-tight text-foreground">
              {formatPtBrNumber(data.total_structures)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Postes, CTOs e caixas subterrâneas
            </p>
            <div className="mt-4 pt-3 border-t border-border">
              <Link
                href="/poles"
                className="flex items-center text-xs font-medium text-primary hover:underline gap-1"
              >
                Ver estruturas físicas
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Card: Cabos Ópticos */}
        <Card className="hover:border-primary/40 transition-colors shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Cabos Ópticos
            </CardTitle>
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <CableIcon className="h-4 w-4" aria-hidden="true" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tracking-tight text-foreground">
              {formatPtBrNumber(data.total_cables)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Rotas troncos, distribuição e derivações
            </p>
            <div className="mt-4 pt-3 border-t border-border">
              <Link
                href="/cables"
                className="flex items-center text-xs font-medium text-primary hover:underline gap-1"
              >
                Ver inventário de cabos
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Card: Assinantes e Links de Serviço */}
        <Card className="hover:border-primary/40 transition-colors shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Clientes & Conexões
            </CardTitle>
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Users className="h-4 w-4" aria-hidden="true" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tracking-tight text-foreground">
              {formatPtBrNumber(data.total_customers)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {data.total_active_service_links} serviço(s) ativo(s)
            </p>
            <div className="mt-4 pt-3 border-t border-border">
              <Link
                href="/customers"
                className="flex items-center text-xs font-medium text-primary hover:underline gap-1"
              >
                Base de assinantes
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Grid: Ocupação de CTOs & Integridade Técnica */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Ocupação Documentada de CTOs */}
        <Card className="shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base font-semibold">
                  Ocupação Documentada de CTOs
                </CardTitle>
                <CardDescription className="text-xs mt-1">
                  Distribuição de caixas de terminação óptica por capacidade utilizada ({ctosTotal} total)
                </CardDescription>
              </div>
              <Badge variant="secondary" className="font-mono text-xs">
                {ctosTotal} CTOs
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Barra de distribuição gráfica de faixas */}
            <div className="space-y-1.5">
              <div className="flex h-3.5 w-full overflow-hidden rounded-full bg-muted">
                {pctEmpty > 0 && (
                  <div
                    style={{ width: `${pctEmpty}%` }}
                    className="bg-emerald-500 transition-all"
                    title={`0% Vazia: ${data.ctos_occupancy.empty_0_pct} (${pctEmpty}%)`}
                  />
                )}
                {pctLow > 0 && (
                  <div
                    style={{ width: `${pctLow}%` }}
                    className="bg-blue-500 transition-all"
                    title={`1-50%: ${data.ctos_occupancy.low_1_to_50_pct} (${pctLow}%)`}
                  />
                )}
                {pctHigh > 0 && (
                  <div
                    style={{ width: `${pctHigh}%` }}
                    className="bg-amber-500 transition-all"
                    title={`51-99%: ${data.ctos_occupancy.high_51_to_99_pct} (${pctHigh}%)`}
                  />
                )}
                {pctFull > 0 && (
                  <div
                    style={{ width: `${pctFull}%` }}
                    className="bg-destructive transition-all"
                    title={`100% Esgotada: ${data.ctos_occupancy.full_100_pct} (${pctFull}%)`}
                  />
                )}
              </div>
            </div>

            {/* Lista detalhada com links filtrados */}
            <div className="grid grid-cols-2 gap-3">
              <Link
                href="/ctos?occupancy=empty"
                className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent/40 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">0% Vazia</p>
                    <p className="text-[11px] text-muted-foreground">{pctEmpty}% do total</p>
                  </div>
                </div>
                <span className="font-mono text-sm font-semibold ml-2">
                  {data.ctos_occupancy.empty_0_pct}
                </span>
              </Link>

              <Link
                href="/ctos?occupancy=low"
                className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent/40 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="h-2.5 w-2.5 rounded-full bg-blue-500 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">1% a 50%</p>
                    <p className="text-[11px] text-muted-foreground">{pctLow}% do total</p>
                  </div>
                </div>
                <span className="font-mono text-sm font-semibold ml-2">
                  {data.ctos_occupancy.low_1_to_50_pct}
                </span>
              </Link>

              <Link
                href="/ctos?occupancy=high"
                className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent/40 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="h-2.5 w-2.5 rounded-full bg-amber-500 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">51% a 99%</p>
                    <p className="text-[11px] text-muted-foreground">{pctHigh}% do total</p>
                  </div>
                </div>
                <span className="font-mono text-sm font-semibold ml-2">
                  {data.ctos_occupancy.high_51_to_99_pct}
                </span>
              </Link>

              <Link
                href="/ctos?occupancy=full"
                className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent/40 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="h-2.5 w-2.5 rounded-full bg-destructive flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">100% Esgotada</p>
                    <p className="text-[11px] text-muted-foreground">{pctFull}% do total</p>
                  </div>
                </div>
                <span className="font-mono text-sm font-semibold ml-2">
                  {data.ctos_occupancy.full_100_pct}
                </span>
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Qualidade e Incompletude Técnica da Documentação */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Integridade da Documentação
            </CardTitle>
            <CardDescription className="text-xs mt-1">
              Verificação contínua de amarrações geográficas e parâmetros físicos de rede
            </CardDescription>
          </CardHeader>
          <CardContent>
            {(() => {
              const alerts = data.incomplete_documentation_alerts ?? [];
              if (alerts.length === 0) {
                return (
                  <div className="flex flex-col items-center justify-center p-6 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-center">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 mb-2">
                      <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <p className="text-sm font-semibold text-foreground">
                      Documentação em Conformidade
                    </p>
                    <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                      Todos os cabos cadastrados possuem segmentos georreferenciados e amarrações consistentes.
                    </p>
                  </div>
                );
              }
              return (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-xs font-medium text-amber-600 dark:text-amber-400 pb-1">
                    <AlertTriangle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
                    <span>
                      {alerts.length} apontamento(s) requerem atenção
                    </span>
                  </div>

                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {alerts.map((alertMsg, idx) => (
                      <div
                        key={idx}
                        className="flex items-start justify-between gap-3 p-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5 text-xs"
                      >
                        <div className="flex items-start gap-2">
                          <AlertTriangle
                            className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5"
                            aria-hidden="true"
                          />
                          <span className="text-foreground">{alertMsg}</span>
                        </div>
                        <Link
                          href="/reports"
                          className="text-xs text-primary hover:underline whitespace-nowrap font-medium ml-2"
                        >
                          Ver detalhes
                        </Link>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })()}

            {/* Ações Rápidas de Navegação */}
            <div className="mt-6 pt-4 border-t border-border grid grid-cols-2 gap-3">
              <Link
                href="/trace"
                className="flex items-center gap-2 p-2 rounded-md hover:bg-accent/40 text-xs font-medium text-foreground transition-colors"
              >
                <Activity className="h-4 w-4 text-primary" aria-hidden="true" />
                <span>Rastreamento Óptico</span>
              </Link>
              <Link
                href="/import"
                className="flex items-center gap-2 p-2 rounded-md hover:bg-accent/40 text-xs font-medium text-foreground transition-colors"
              >
                <Layers className="h-4 w-4 text-primary" aria-hidden="true" />
                <span>Importar GeoJSON / KML</span>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
