"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Route,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  ExternalLink,
  Layers,
  GitBranch,
  Split,
  ShieldAlert,
  Info,
  Cable,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { traceOpticalPath } from "../api";
import { listCustomers } from "../../customers/api";
import { formatPtBrNumber } from "@/lib/format/numbers";
import type { TraceDirection, TracePath, TraceResponse, TraceStatus, TraceStep } from "../types";

export function TopologyTraceView() {
  const searchParams = useSearchParams();
  const initialTerminalId = searchParams.get("terminal_id") || "";
  const initialDirection = (searchParams.get("direction") as TraceDirection) || "downstream";

  const [terminalIdInput, setTerminalIdInput] = React.useState(initialTerminalId);
  const [direction, setDirection] = React.useState<TraceDirection>(initialDirection);
  const [selectedPathIndex, setSelectedPathIndex] = React.useState<number>(0);
  const [selectedStepNumber, setSelectedStepNumber] = React.useState<number | null>(null);
  const [customerSearch, setCustomerSearch] = React.useState("");

  // Busca lista de clientes para busca rápida
  const { data: customersData } = useQuery({
    queryKey: ["customers", "trace-lookup", customerSearch],
    queryFn: () => listCustomers({ q: customerSearch, page_size: 10 }),
    enabled: Boolean(customerSearch.trim()),
  });

  // Mutação do rastreamento óptico ponta a ponta
  const traceMutation = useMutation({
    mutationFn: (req: { start_terminal_id: string; direction: TraceDirection; max_results: number }) =>
      traceOpticalPath(req),
    onSuccess: (data) => {
      setSelectedPathIndex(0);
      setSelectedStepNumber(data.paths[0]?.steps[0]?.step_number || null);
    },
  });

  const { mutate: executeTrace } = traceMutation;

  // Executa rastreamento automático se o terminal foi informado na URL
  React.useEffect(() => {
    if (initialTerminalId) {
      executeTrace({
        start_terminal_id: initialTerminalId,
        direction: initialDirection,
        max_results: 50,
      });
    }
  }, [initialTerminalId, initialDirection, executeTrace]);

  const handleStartTrace = (termId?: string) => {
    const idToUse = (termId || terminalIdInput).trim();
    if (!idToUse) return;
    traceMutation.mutate({
      start_terminal_id: idToUse,
      direction,
      max_results: 50,
    });
  };

  const traceResult: TraceResponse | undefined = traceMutation.data;
  const paths = traceResult?.paths || [];
  const currentPath: TracePath | undefined = paths[selectedPathIndex] || paths[0];
  const selectedStep: TraceStep | undefined =
    currentPath?.steps.find((s) => s.step_number === selectedStepNumber) || currentPath?.steps[0];

  const getStatusBanner = (status: TraceStatus) => {
    switch (status) {
      case "complete":
        return (
          <div
            role="status"
            className="flex items-center justify-between p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 text-xs"
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <div>
                <span className="font-semibold">Rastreamento Concluído com Sucesso:</span> O sinal
                óptico alcançou um ponto terminal válido sem descontinuidade física.
              </div>
            </div>
            <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white font-mono text-[10px]">
              COMPLETE
            </Badge>
          </div>
        );
      case "incomplete":
        return (
          <div
            role="status"
            className="flex items-start justify-between p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200 text-xs"
          >
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div>
                  <span className="font-semibold">Ponta Aberta Detectada:</span> O circuito óptico
                  termina sem conexão física antes do destino pretendido.
                </div>
                {traceResult?.unresolved_terminals && traceResult.unresolved_terminals.length > 0 && (
                  <div className="font-mono text-[11px] text-amber-700 dark:text-amber-300">
                    Terminais não resolvidos: {traceResult.unresolved_terminals.join(", ")}
                  </div>
                )}
              </div>
            </div>
            <Badge className="bg-amber-600 hover:bg-amber-600 text-white font-mono text-[10px]">
              INCOMPLETE
            </Badge>
          </div>
        );
      case "cycle_detected":
        return (
          <div
            role="alert"
            className="flex items-start justify-between p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs"
          >
            <div className="flex items-start gap-2">
              <ShieldAlert className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div>
                  <span className="font-semibold">Ciclo Óptico Inválido Detectado:</span> O traçado
                  contém um anel ou retroalimentação fechada entre os mesmos terminais.
                </div>
                <div className="text-[11px] opacity-90">
                  O rastreamento foi interrompido com segurança para evitar laço infinito.
                </div>
              </div>
            </div>
            <Badge variant="destructive" className="font-mono text-[10px]">
              CYCLE_DETECTED
            </Badge>
          </div>
        );
      case "ambiguous":
        return (
          <div
            role="alert"
            className="flex items-start justify-between p-3 rounded-lg border border-purple-500/30 bg-purple-500/10 text-purple-800 dark:text-purple-200 text-xs"
          >
            <div className="flex items-start gap-2">
              <GitBranch className="h-4 w-4 text-purple-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Ambiguidade Detectada:</span> Um ou mais terminais
                possuem múltiplas conexões concorrentes simultâneas sem priorização semântica.
              </div>
            </div>
            <Badge className="bg-purple-600 hover:bg-purple-600 text-white font-mono text-[10px]">
              AMBIGUOUS
            </Badge>
          </div>
        );
      case "limit_exceeded":
        return (
          <div
            role="status"
            className="flex items-center justify-between p-3 rounded-lg border border-sky-500/30 bg-sky-500/10 text-sky-800 dark:text-sky-200 text-xs"
          >
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-sky-600 shrink-0" />
              <div>
                <span className="font-semibold">Limite de Resultados Atingido:</span> O número de
                derivações encontradas excedeu o limite máximo configurado (50).
              </div>
            </div>
            <Badge className="bg-sky-600 text-white font-mono text-[10px]">LIMIT_EXCEEDED</Badge>
          </div>
        );
    }
  };

  const getStepElementIcon = (elementType: string) => {
    switch (elementType) {
      case "fiber_segment":
        return <Cable className="h-3.5 w-3.5 text-emerald-600" />;
      case "fusion":
        return <Zap className="h-3.5 w-3.5 text-amber-600" />;
      case "patch_cord":
      case "drop_patch":
        return <ArrowRight className="h-3.5 w-3.5 text-sky-600" />;
      case "splitter":
        return <Split className="h-3.5 w-3.5 text-purple-600" />;
      default:
        return <Route className="h-3.5 w-3.5 text-muted-foreground" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* CABEÇALHO E BARRA DE CONTROLE DE RASTREAMENTO */}
      <div className="rounded-xl border border-border bg-card p-4 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
          <div>
            <h2 className="text-base font-bold tracking-tight text-foreground flex items-center gap-2">
              <Route className="h-4 w-4 text-primary" />
              <span>Rastreamento Óptico Ponta a Ponta</span>
            </h2>
            <p className="text-xs text-muted-foreground">
              Traçado determinístico de caminhos PON-ONU e ONU-PON com semântica de portas e splitters.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center border border-border rounded-lg p-0.5 bg-muted/40">
              <button
                type="button"
                onClick={() => setDirection("downstream")}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  direction === "downstream"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span>Downstream</span>
                <span className="text-[10px] opacity-75">(PON→ONU)</span>
              </button>
              <button
                type="button"
                onClick={() => setDirection("upstream")}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  direction === "upstream"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span>Upstream</span>
                <span className="text-[10px] opacity-75">(ONU→PON)</span>
              </button>
            </div>
          </div>
        </div>

        {/* INPUT DE TERMINAL OU BUSCA RÁPIDA */}
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
          <div className="sm:col-span-8 space-y-1.5">
            <label htmlFor="terminal-id" className="text-xs font-medium text-foreground">
              Terminal Óptico de Partida (UUID)
            </label>
            <div className="relative flex items-center">
              <Input
                id="terminal-id"
                placeholder="Informe o UUID do terminal (ex: porta PON, porta ONU ou extremidade de fibra)..."
                value={terminalIdInput}
                onChange={(e) => setTerminalIdInput(e.target.value)}
                className="font-mono text-xs pr-24"
              />
              <Button
                type="button"
                size="sm"
                onClick={() => handleStartTrace()}
                disabled={!terminalIdInput.trim() || traceMutation.isPending}
                className="absolute right-1 h-7 text-xs gap-1.5 bg-primary"
              >
                <RefreshCw className={`h-3 w-3 ${traceMutation.isPending ? "animate-spin" : ""}`} />
                <span>{traceMutation.isPending ? "Rastreando..." : "Rastrear"}</span>
              </Button>
            </div>
          </div>

          <div className="sm:col-span-4 space-y-1.5">
            <label className="text-xs font-medium text-foreground">Localizar por Assinante</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Buscar cliente para rastrear..."
                value={customerSearch}
                onChange={(e) => setCustomerSearch(e.target.value)}
                className="pl-8 text-xs h-9"
              />
            </div>

            {/* Dropdown de sugestões de assinantes */}
            {customersData?.items && customersData.items.length > 0 && customerSearch.trim() && (
              <div className="absolute z-20 mt-1 w-72 rounded-lg border border-border bg-card shadow-lg p-1 text-xs divide-y divide-border">
                {customersData.items.map((cust) => (
                  <button
                    type="button"
                    key={cust.id}
                    onClick={() => {
                      setCustomerSearch("");
                      setTerminalIdInput(cust.id);
                    }}
                    className="w-full text-left p-2 hover:bg-muted/50 transition-colors"
                  >
                    <div className="font-semibold text-foreground">{cust.name}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {cust.code} • Clique para usar ID
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ERROS DA API RFC 7807 */}
      {traceMutation.isError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-xs text-destructive flex items-start gap-2"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <div>
            <div className="font-bold">Erro ao executar rastreamento óptico</div>
            <p className="mt-0.5">{traceMutation.error.message}</p>
          </div>
        </div>
      )}

      {/* RESULTADOS DO RASTREAMENTO */}
      {traceResult && (
        <div className="space-y-4">
          {/* BANNER DE STATUS */}
          {getStatusBanner(traceResult.status)}

          {/* BARRA DE METADADOS DA TOPOLOGIA E RAMIFICAÇÕES */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-border bg-card p-3 text-xs">
            <div className="flex items-center gap-4">
              <div>
                <span className="text-muted-foreground">Revisão Topológica:</span>
                <span className="font-mono font-bold ml-1.5 text-foreground">
                  v{traceResult.topology_revision}
                </span>
              </div>
              <div className="h-4 w-px bg-border" />
              <div>
                <span className="text-muted-foreground">Caminhos / Derivações:</span>
                <span className="font-mono font-bold ml-1.5 text-foreground">{paths.length}</span>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => handleStartTrace()}
              className="h-7 text-xs gap-1"
            >
              <RefreshCw className="h-3 w-3" />
              <span>Recalcular após Alteração</span>
            </Button>
          </div>

          {/* SELETOR DE RAMOS (QUANDO HÁ SPLITTERS COM MÚLTIPLAS SAÍDAS) */}
          {paths.length > 1 && (
            <div className="rounded-lg border border-border bg-card p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-muted-foreground">
                  Ramificações Encontradas ({paths.length} ramos)
                </span>
                <span className="text-[11px] text-muted-foreground">
                  Ramo ativo: {selectedPathIndex + 1} de {paths.length}
                </span>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {paths.map((p, idx) => {
                  const isSelected = idx === selectedPathIndex;
                  return (
                    <button
                      type="button"
                      key={p.path_id}
                      onClick={() => {
                        setSelectedPathIndex(idx);
                        setSelectedStepNumber(p.steps[0]?.step_number || null);
                      }}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-mono transition-colors flex items-center gap-2 ${
                        isSelected
                          ? "border-primary bg-primary/10 text-primary font-bold shadow-sm"
                          : "border-border hover:bg-muted/50 text-muted-foreground"
                      }`}
                    >
                      <Split className="h-3 w-3" />
                      <span>Ramo #{idx + 1}</span>
                      <span className="text-[10px] opacity-75">
                        ({formatPtBrNumber(p.total_length_m, { minDecimals: 0 })}m •{" "}
                        {formatPtBrNumber(p.total_loss_db, { minDecimals: 2 })} dB)
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* TRAÇADO PASSO A PASSO DO CAMINHO SELECIONADO */}
          {currentPath ? (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              {/* COLUNA ESQUERDA: LISTA ORDENADA E TIMELINE DE PASSOS */}
              <div className="lg:col-span-8 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Layers className="h-4 w-4 text-primary" />
                    <span>Passos do Caminho Óptico</span>
                  </h3>
                  <div className="flex items-center gap-3 font-mono text-xs">
                    <span className="text-muted-foreground">
                      Comprimento:{" "}
                      <strong className="text-foreground">
                        {formatPtBrNumber(currentPath.total_length_m, { minDecimals: 1 })} m
                      </strong>
                    </span>
                    <span className="text-muted-foreground">
                      Perda Total:{" "}
                      <strong className="text-foreground">
                        {formatPtBrNumber(currentPath.total_loss_db, { minDecimals: 2 })} dB
                      </strong>
                    </span>
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
                  {currentPath.steps.map((step) => {
                    const isSelected = step.step_number === selectedStepNumber;
                    return (
                      <button
                        type="button"
                        key={step.step_number}
                        onClick={() => setSelectedStepNumber(step.step_number)}
                        className={`w-full text-left p-3 flex items-start justify-between transition-colors text-xs ${
                          isSelected ? "bg-primary/10" : "hover:bg-muted/40"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-mono font-bold ${
                              isSelected
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {step.step_number}
                          </div>

                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              {getStepElementIcon(step.element_type)}
                              <span className="font-semibold text-foreground">
                                {step.element_code || step.element_type}
                              </span>
                              <Badge variant="outline" className="text-[10px] uppercase">
                                {step.element_type}
                              </Badge>
                            </div>

                            <div className="font-mono text-[11px] text-muted-foreground flex items-center gap-2">
                              {step.location_code && (
                                <span className="text-foreground font-semibold">
                                  [{step.location_code}]
                                </span>
                              )}
                              <span>
                                In: {step.input_terminal_id ? `#${step.input_terminal_id.slice(0, 8)}` : "Origem"}
                              </span>
                              <span>→</span>
                              <span>
                                Out: {step.output_terminal_id ? `#${step.output_terminal_id.slice(0, 8)}` : "Destino"}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="text-right font-mono space-y-0.5">
                          <div className="text-foreground font-medium">
                            {step.length_m > 0
                              ? `+${formatPtBrNumber(step.length_m, { minDecimals: 0 })} m`
                              : "—"}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            +{formatPtBrNumber(step.loss_db, { minDecimals: 2 })} dB (
                            {formatPtBrNumber(step.accumulated_loss_db, { minDecimals: 2 })} dB)
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* COLUNA DIREITA: DETALHES DO PASSO SELECIONADO & LINK PARA FICHA */}
              <div className="lg:col-span-4 space-y-3">
                <h3 className="text-sm font-semibold">Detalhes do Elemento Selecionado</h3>

                {selectedStep ? (
                  <Card className="border-border">
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" className="font-mono text-[10px]">
                          Passo #{selectedStep.step_number}
                        </Badge>
                        <Badge className="capitalize text-[10px]">
                          {selectedStep.element_type}
                        </Badge>
                      </div>
                      <CardTitle className="text-sm font-bold mt-1">
                        {selectedStep.element_code || selectedStep.element_type}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-2 space-y-3 text-xs">
                      <dl className="space-y-2">
                        <div>
                          <dt className="text-muted-foreground">Localização Física</dt>
                          <dd className="font-semibold text-foreground">
                            {selectedStep.location_code || "Estrutura Externa"}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Elemento ID</dt>
                          <dd className="font-mono text-[11px] text-foreground truncate">
                            {selectedStep.element_id}
                          </dd>
                        </div>
                        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border">
                          <div>
                            <dt className="text-muted-foreground">Comprimento</dt>
                            <dd className="font-mono font-semibold text-foreground">
                              {formatPtBrNumber(selectedStep.length_m, { minDecimals: 1 })} m
                            </dd>
                            <dd className="font-mono text-[10px] text-muted-foreground">
                              Acum: {formatPtBrNumber(selectedStep.accumulated_length_m, { minDecimals: 1 })} m
                            </dd>
                          </div>
                          <div>
                            <dt className="text-muted-foreground">Atenuação</dt>
                            <dd className="font-mono font-semibold text-foreground">
                              {formatPtBrNumber(selectedStep.loss_db, { minDecimals: 2 })} dB
                            </dd>
                            <dd className="font-mono text-[10px] text-muted-foreground">
                              Acum: {formatPtBrNumber(selectedStep.accumulated_loss_db, { minDecimals: 2 })} dB
                            </dd>
                          </div>
                        </div>
                        <div className="pt-1 border-t border-border space-y-1">
                          <dt className="text-muted-foreground">Terminais Ópticos</dt>
                          <dd className="font-mono text-[10px] text-muted-foreground">
                            Entrada: {selectedStep.input_terminal_id || "—"}
                          </dd>
                          <dd className="font-mono text-[10px] text-muted-foreground">
                            Saída: {selectedStep.output_terminal_id || "—"}
                          </dd>
                        </div>
                      </dl>

                      {/* Links rápidos para ficha do recurso */}
                      <div className="pt-2 border-t border-border flex items-center justify-between">
                        {selectedStep.element_type === "fiber_segment" && (
                          <Link
                            href="/cables"
                            className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
                          >
                            <span>Ver Cabo no Inventário</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        )}
                        {selectedStep.location_code && (
                          <Link
                            href={`/structures`}
                            className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
                          >
                            <span>Ver Estrutura</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
                    Selecione um passo na lista para ver os detalhes técnicos.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-xs text-muted-foreground">
              Nenhum caminho óptico retornado para esta consulta.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
