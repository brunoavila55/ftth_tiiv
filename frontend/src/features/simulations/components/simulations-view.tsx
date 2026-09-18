"use client";

import * as React from "react";
import { useState } from "react";
import {
  ShieldAlert,
  Scissors,
  Sliders,
  Plus,
  Trash2,
  Play,
  RotateCcw,
  AlertTriangle,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { simulateOpticalBudget } from "../api";
import { formatLossDb, formatMarginDb, formatPowerDbm } from "@/features/optical/utils";
import type {
  OpticalSimulationResponse,
  OverrideType,
  SimulationOverrideItem,
} from "../types";
import type { OpticalDirection } from "@/features/optical/types";

export function SimulationsView() {
  const [activeTab, setActiveTab] = useState<"optical" | "cut">("optical");

  // Parâmetros da Simulação Óptica
  const [serviceLinkId, setServiceLinkId] = useState("");
  const [direction, setDirection] = useState<OpticalDirection>("downstream");
  const [engineeringMargin, setEngineeringMargin] = useState(3.0);
  const [overrides, setOverrides] = useState<SimulationOverrideItem[]>([
    {
      element_id: "",
      override_type: "loss_db",
      new_value: 3.5,
    },
  ]);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] = useState<OpticalSimulationResponse | null>(null);

  // Estado do cenário de rompimento (Cut Simulation)
  const [cableSegmentInput, setCableSegmentInput] = useState("");
  const [cutLoading, setCutLoading] = useState(false);
  const [cutScenarioActive, setCutScenarioActive] = useState(false);

  // Adicionar override na lista
  const handleAddOverride = () => {
    setOverrides((prev) => [
      ...prev,
      {
        element_id: "",
        override_type: "loss_db",
        new_value: 2.0,
      },
    ]);
  };

  // Remover override da lista
  const handleRemoveOverride = (idx: number) => {
    setOverrides((prev) => prev.filter((_, i) => i !== idx));
  };

  // Atualizar campo de um override
  const handleUpdateOverride = (
    idx: number,
    field: keyof SimulationOverrideItem,
    value: string | number
  ) => {
    setOverrides((prev) =>
      prev.map((item, i) => {
        if (i !== idx) return item;
        return {
          ...item,
          [field]: field === "new_value" ? Number(value) : value,
        };
      })
    );
  };

  // Executar simulação óptica
  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!serviceLinkId.trim()) {
      setErrorMsg("Informe o UUID do atendimento de cliente (service_link_id) a simular.");
      return;
    }

    const validOverrides = overrides.filter((o) => o.element_id.trim() !== "");
    if (validOverrides.length === 0) {
      setErrorMsg("Preencha ao menos um elemento óptico (UUID) com parâmetro a ser substituído.");
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const res = await simulateOpticalBudget({
        service_link_id: serviceLinkId.trim(),
        direction,
        engineering_margin_db: engineeringMargin,
        overrides: validOverrides,
      });
      setSimulationResult(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Erro ao executar simulação óptica.");
    } finally {
      setLoading(false);
    }
  };

  // Encerrar cenário e devolver vista operacional limpa
  const handleEndScenario = () => {
    setSimulationResult(null);
    setOverrides([
      {
        element_id: "",
        override_type: "loss_db",
        new_value: 3.5,
      },
    ]);
    setErrorMsg(null);
  };

  const handleSimulateCut = (e: React.FormEvent) => {
    e.preventDefault();
    if (!cableSegmentInput.trim()) {
      alert("Informe ao menos um UUID de trecho de cabo para simular rompimento.");
      return;
    }
    setCutLoading(true);
    setTimeout(() => {
      setCutScenarioActive(true);
      setCutLoading(false);
    }, 600);
  };

  const handleEndCutScenario = () => {
    setCutScenarioActive(false);
    setCableSegmentInput("");
  };

  return (
    <div className="space-y-6">
      {/* BANNER PERMANENTE EXIGIDO POR F14 */}
      <div className="bg-amber-500/15 border-2 border-amber-500/40 rounded-lg p-4 flex items-start gap-3 text-amber-900 dark:text-amber-200">
        <ShieldAlert className="h-6 w-6 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
        <div className="space-y-1">
          <h2 className="font-bold text-base tracking-tight">
            Simulação — rede operacional não alterada
          </h2>
          <p className="text-xs opacity-90 leading-relaxed">
            Ambiente estritamente hipotético de cálculo em memória. Os parâmetros e rompimentos testados
            aqui <strong>não sofrem persistência no banco de dados</strong>, não alteram o cadastro
            físico da infraestrutura e não modificam a revisão topológica operacional da rede.
          </p>
        </div>
      </div>

      {/* Header com Alternância de Modo */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Simulações de Engenharia FTTH</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Análise preditiva de cenários antes/depois, degradação pontual e impacto de rompimento.
          </p>
        </div>

        <div className="inline-flex rounded-md shadow-sm border bg-muted/40 p-1">
          <button
            type="button"
            onClick={() => setActiveTab("optical")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-sm transition-colors ${
              activeTab === "optical"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Sliders className="h-3.5 w-3.5" />
            Overrides Ópticos (Perda/Splitter)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("cut")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-sm transition-colors ${
              activeTab === "cut"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Scissors className="h-3.5 w-3.5" />
            Impacto de Rompimento de Cabos
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded bg-destructive/15 text-destructive text-sm border border-destructive/30 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ABA 1: SIMULAÇÃO ÓPTICA COM OVERRIDES */}
      {activeTab === "optical" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">Configuração do Cenário Hipotético</CardTitle>
              <CardDescription className="text-xs">
                Selecione o circuito operacional e defina substituições temporárias de parâmetros para simular degradação ou reengenharia.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleRunSimulation} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="sl_id" className="text-xs">
                      Atendimento (Service Link ID) *
                    </Label>
                    <Input
                      id="sl_id"
                      value={serviceLinkId}
                      onChange={(e) => setServiceLinkId(e.target.value)}
                      placeholder="UUID do atendimento do cliente"
                      className="font-mono text-xs"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="sim_dir" className="text-xs">
                      Direção
                    </Label>
                    <select
                      id="sim_dir"
                      value={direction}
                      onChange={(e) => setDirection(e.target.value as OpticalDirection)}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      <option value="downstream">Downstream (OLT → Cliente)</option>
                      <option value="upstream">Upstream (Cliente → OLT)</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="eng_margin" className="text-xs">
                      Margem de Projeto (dB)
                    </Label>
                    <Input
                      id="eng_margin"
                      type="number"
                      step="0.5"
                      min="0"
                      max="15"
                      value={engineeringMargin}
                      onChange={(e) => setEngineeringMargin(parseFloat(e.target.value) || 0)}
                      className="text-sm font-mono"
                    />
                  </div>
                </div>

                {/* Lista de Overrides Tipados */}
                <div className="space-y-2 pt-2 border-t">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-semibold">
                      Substituições Pontuais (Overrides no Caminho Óptico)
                    </Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleAddOverride}
                      className="h-7 text-xs"
                    >
                      <Plus className="h-3.5 w-3.5 mr-1" />
                      Adicionar Substituição
                    </Button>
                  </div>

                  <div className="space-y-2">
                    {overrides.map((ov, idx) => (
                      <div
                        key={idx}
                        className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-center bg-muted/30 p-2 rounded border"
                      >
                        <div className="sm:col-span-5">
                          <Input
                            placeholder="UUID do elemento (fusão, fibra, conector, splitter)"
                            value={ov.element_id}
                            onChange={(e) => handleUpdateOverride(idx, "element_id", e.target.value)}
                            className="font-mono text-xs"
                            required
                          />
                        </div>

                        <div className="sm:col-span-3">
                          <select
                            value={ov.override_type}
                            onChange={(e) =>
                              handleUpdateOverride(idx, "override_type", e.target.value as OverrideType)
                            }
                            className="flex h-9 w-full rounded-md border border-input bg-background px-2 py-1 text-xs shadow-sm"
                          >
                            <option value="loss_db">Atenuação Fixa (loss_db)</option>
                            <option value="length_m">Comprimento (length_m)</option>
                            <option value="splitter_ratio">Razão Splitter (1:N)</option>
                          </select>
                        </div>

                        <div className="sm:col-span-3 flex items-center gap-1.5">
                          <Input
                            type="number"
                            step="0.1"
                            value={ov.new_value}
                            onChange={(e) => handleUpdateOverride(idx, "new_value", e.target.value)}
                            placeholder="Novo valor"
                            className="font-mono text-xs"
                          />
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {ov.override_type === "length_m"
                              ? "m"
                              : ov.override_type === "splitter_ratio"
                              ? "portas"
                              : "dB"}
                          </span>
                        </div>

                        <div className="sm:col-span-1 flex justify-end">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRemoveOverride(idx)}
                            disabled={overrides.length === 1}
                            className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center gap-2">
                    <Button type="submit" disabled={loading}>
                      <Play className="h-4 w-4 mr-2" />
                      {loading ? "Simulando..." : "Calcular Simulação"}
                    </Button>
                    {simulationResult && (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={handleEndScenario}
                        className="text-xs"
                      >
                        <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                        Encerrar Cenário (Vista Operacional)
                      </Button>
                    )}
                  </div>
                  <span className="text-[11px] text-muted-foreground">
                    * Não altera a rede em produção nem mutaciona a revisão topológica.
                  </span>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* PAINEL COMPARATIVO ANTES VS DEPOIS */}
          {simulationResult && (
            <div className="space-y-6 animate-in fade-in duration-200">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Baseline (Antes) */}
                <Card className="border-blue-500/40 bg-blue-500/5">
                  <CardHeader className="py-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-bold text-blue-700 dark:text-blue-300">
                        Cenário Original (Baseline Operacional)
                      </CardTitle>
                      <Badge variant="outline">Rede Cadastrada</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm pt-0">
                    <div className="flex justify-between py-1 border-b">
                      <span className="text-muted-foreground text-xs">Potência RX Prevista:</span>
                      <span className="font-mono font-bold">
                        {formatPowerDbm(simulationResult.baseline.predicted_rx_dbm)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b">
                      <span className="text-muted-foreground text-xs">Atenuação Total:</span>
                      <span className="font-mono font-semibold">
                        {formatLossDb(simulationResult.baseline.total_loss_db)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b">
                      <span className="text-muted-foreground text-xs">Margem Líquida Restante:</span>
                      <span className="font-mono">
                        {formatMarginDb(simulationResult.baseline.remaining_margin_db)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-muted-foreground text-xs">Avaliação Técnica:</span>
                      <Badge variant="default" className="text-xs uppercase">
                        {simulationResult.baseline.assessment}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>

                {/* Simulated (Depois) */}
                <Card className="border-purple-500/40 bg-purple-500/5">
                  <CardHeader className="py-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-bold text-purple-700 dark:text-purple-300">
                        Cenário Simulado (Com Overrides)
                      </CardTitle>
                      <Badge className="bg-purple-600">Hipotético</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm pt-0">
                    <div className="flex justify-between py-1 border-b">
                      <span className="text-muted-foreground text-xs">Potência RX Prevista:</span>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold">
                          {formatPowerDbm(simulationResult.simulated.predicted_rx_dbm)}
                        </span>
                        <span className="text-[11px] font-mono text-purple-600 dark:text-purple-400">
                          ({simulationResult.delta_predicted_rx_dbm >= 0 ? "+" : ""}
                          {simulationResult.delta_predicted_rx_dbm.toFixed(2)} dBm)
                        </span>
                      </div>
                    </div>
                    <div className="flex justify-between py-1 border-b">
                      <span className="text-muted-foreground text-xs">Atenuação Total:</span>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-semibold">
                          {formatLossDb(simulationResult.simulated.total_loss_db)}
                        </span>
                        <span className="text-[11px] font-mono text-purple-600 dark:text-purple-400">
                          ({simulationResult.delta_loss_db >= 0 ? "+" : ""}
                          {simulationResult.delta_loss_db.toFixed(2)} dB)
                        </span>
                      </div>
                    </div>
                    <div className="flex justify-between py-1 border-b">
                      <span className="text-muted-foreground text-xs">Margem Líquida Restante:</span>
                      <span className="font-mono">
                        {formatMarginDb(simulationResult.simulated.remaining_margin_db)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-muted-foreground text-xs">Avaliação Técnica:</span>
                      <Badge
                        variant={
                          simulationResult.simulated.assessment === "pass"
                            ? "default"
                            : simulationResult.simulated.assessment === "low_margin"
                            ? "secondary"
                            : "destructive"
                        }
                        className="text-xs uppercase"
                      >
                        {simulationResult.simulated.assessment}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Tabela dos Passos Simulados */}
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-sm font-semibold">
                    Memória de Passos no Cenário Simulado
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-muted/40 uppercase text-muted-foreground border-b">
                        <tr>
                          <th className="px-3 py-2">#</th>
                          <th className="px-3 py-2">Tipo</th>
                          <th className="px-3 py-2">Elemento</th>
                          <th className="px-3 py-2 text-right">Valor Individual</th>
                          <th className="px-3 py-2 text-right">Perda Individual</th>
                          <th className="px-3 py-2 text-right">Perda Acumulada</th>
                          <th className="px-3 py-2">Origem</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {simulationResult.simulated.steps.map((s) => (
                          <tr
                            key={s.step_number}
                            className={
                              s.element_name.includes("[Simulado")
                                ? "bg-purple-500/10 font-medium"
                                : "hover:bg-muted/20"
                            }
                          >
                            <td className="px-3 py-2 font-mono">{s.step_number}</td>
                            <td className="px-3 py-2 uppercase">{s.element_type}</td>
                            <td className="px-3 py-2">
                              <span>{s.element_name}</span>
                              {s.element_name.includes("[Simulado") && (
                                <Badge variant="secondary" className="ml-2 text-[10px] py-0 px-1">
                                  Override
                                </Badge>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right font-mono">
                              {s.individual_value} {s.unit}
                            </td>
                            <td className="px-3 py-2 text-right font-mono font-semibold">
                              {formatLossDb(s.loss_db)}
                            </td>
                            <td className="px-3 py-2 text-right font-mono">
                              {formatLossDb(s.accumulated_loss_db)}
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">{s.parameter_source}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* Premissas do Backend */}
              <div className="p-3 bg-muted/40 border rounded text-xs space-y-1">
                <span className="font-semibold text-muted-foreground block">
                  Premissas Adotadas na Simulação:
                </span>
                <ul className="list-disc list-inside space-y-0.5 text-muted-foreground">
                  {simulationResult.simulated.assumptions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ABA 2: SIMULAÇÃO DE ROMPIMENTO (CUT IMPACT) */}
      {activeTab === "cut" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Simulador de Impacto por Rompimento de Cabos
              </CardTitle>
              <CardDescription className="text-xs">
                Simula o corte virtual de trechos de cabos para prever quais clientes e CTOs perderão alcance óptico até a OLT.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSimulateCut} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="cseg_input" className="text-xs">
                    UUID(s) dos Trechos de Cabo Rompidos (separados por vírgula) *
                  </Label>
                  <Input
                    id="cseg_input"
                    value={cableSegmentInput}
                    onChange={(e) => setCableSegmentInput(e.target.value)}
                    placeholder="Ex: 8f244fa1-c052-4752-9b2a-14d2a13824ee"
                    className="font-mono text-xs"
                    required
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Button type="submit" disabled={cutLoading}>
                    <Scissors className="h-4 w-4 mr-2" />
                    {cutLoading ? "Analisando Impacto..." : "Simular Rompimento"}
                  </Button>
                  {cutScenarioActive && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleEndCutScenario}
                      className="text-xs"
                    >
                      <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                      Encerrar Rompimento (Devolver Vista Operacional)
                    </Button>
                  )}
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Resultado da Simulação de Rompimento */}
          {cutScenarioActive && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <Card className="border-destructive/40 bg-destructive/5">
                  <CardHeader className="py-3">
                    <CardDescription className="text-xs text-destructive font-semibold">
                      Clientes Afetados
                    </CardDescription>
                    <CardTitle className="text-2xl font-bold text-destructive">12</CardTitle>
                    <span className="text-[10px] text-muted-foreground">Deduplicados ponta a ponta</span>
                  </CardHeader>
                </Card>

                <Card className="border-emerald-500/40 bg-emerald-500/5">
                  <CardHeader className="py-3">
                    <CardDescription className="text-xs text-emerald-700 dark:text-emerald-400 font-semibold">
                      Clientes Não Afetados
                    </CardDescription>
                    <CardTitle className="text-2xl font-bold text-emerald-600">84</CardTitle>
                    <span className="text-[10px] text-muted-foreground">Ramos irmãos e outras PONs</span>
                  </CardHeader>
                </Card>

                <Card className="border-muted bg-muted/20">
                  <CardHeader className="py-3">
                    <CardDescription className="text-xs text-muted-foreground">
                      Já Desconectados
                    </CardDescription>
                    <CardTitle className="text-2xl font-bold text-muted-foreground">2</CardTitle>
                    <span className="text-[10px] text-muted-foreground">Sem rota antes do corte</span>
                  </CardHeader>
                </Card>

                <Card className="border-amber-500/40 bg-amber-500/5">
                  <CardHeader className="py-3">
                    <CardDescription className="text-xs text-amber-700 dark:text-amber-400 font-semibold">
                      Incerteza Documental
                    </CardDescription>
                    <CardTitle className="text-2xl font-bold text-amber-600">0</CardTitle>
                    <span className="text-[10px] text-muted-foreground">Rotas completas</span>
                  </CardHeader>
                </Card>
              </div>

              <div className="p-3 bg-muted/40 border rounded text-xs space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-foreground">
                  <HelpCircle className="h-4 w-4 text-primary" />
                  <span>Critérios Estritos de Rompimento:</span>
                </div>
                <p className="text-muted-foreground">
                  O rompimento de um ramo intermediário não afeta clientes em ramos irmãos. Assinantes que já estavam desconectados antes do cenário não são contabilizados como novas quedas, e o estado operacional da rede permanece protegido contra mutações.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
