"use client";

import React, { useState, useEffect, useTransition } from "react";
import {
  Calculator,
  ArrowDownRight,
  ArrowUpRight,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Zap,
  Radio,
  Layers,
  Info,
  Sliders,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  calculateOpticalBudget,
  listOpticalProfiles,
  listCustomers,
  listServiceLinks,
  type CustomerRead,
  type ServiceLinkRead,
} from "../api";
import type {
  BudgetCalculationRequest,
  BudgetCalculationResponse,
  OpticalDirection,
  OpticalProfileRead,
} from "../types";
import {
  formatPowerDbm,
  formatLossDb,
  formatMarginDb,
  formatDistance,
  ASSESSMENT_CONFIGS,
} from "../utils";

interface OpticalBudgetViewProps {
  initialServiceLinkId?: string;
  initialDirection?: OpticalDirection;
}

export function OpticalBudgetView({
  initialServiceLinkId,
  initialDirection = "downstream",
}: OpticalBudgetViewProps) {
  const [direction, setDirection] = useState<OpticalDirection>(initialDirection);
  const [engineeringMargin, setEngineeringMargin] = useState<number>(3.0);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [profiles, setProfiles] = useState<OpticalProfileRead[]>([]);

  // Seleção de cliente / atendimento
  const [customers, setCustomers] = useState<CustomerRead[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [customerLinks, setCustomerLinks] = useState<ServiceLinkRead[]>([]);
  const [selectedServiceLinkId, setSelectedServiceLinkId] = useState<string>(
    initialServiceLinkId || ""
  );
  const [terminalIdInput, setTerminalIdInput] = useState<string>("");
  const [inputMode, setInputMode] = useState<"customer" | "terminal">("customer");

  // Estado do cálculo
  const [budgetResult, setBudgetResult] = useState<BudgetCalculationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  // Carrega perfis ópticos e clientes na inicialização
  useEffect(() => {
    async function loadData() {
      try {
        const [profilesRes, custRes] = await Promise.all([
          listOpticalProfiles(),
          listCustomers({ page_size: 50 }),
        ]);
        setProfiles(profilesRes.items);
        setCustomers(custRes.items);
      } catch (err) {
        console.error("Erro ao carregar dados iniciais para cálculo óptico:", err);
      }
    }
    loadData();
  }, []);

  // Quando o cliente selecionado muda, busca os links de atendimento dele
  useEffect(() => {
    if (!selectedCustomerId) {
      setCustomerLinks([]);
      return;
    }
    async function loadLinks() {
      try {
        const res = await listServiceLinks({ customer_id: selectedCustomerId, page_size: 20 });
        setCustomerLinks(res.items);
        if (res.items.length > 0) {
          const active = res.items.find((l) => l.status === "active") || res.items[0];
          setSelectedServiceLinkId(active.id);
        } else {
          setSelectedServiceLinkId("");
        }
      } catch (err) {
        console.error("Erro ao carregar atendimentos do cliente:", err);
      }
    }
    loadLinks();
  }, [selectedCustomerId]);

  // Se já veio com initialServiceLinkId, executa o cálculo automático
  useEffect(() => {
    if (initialServiceLinkId) {
      handleCalculate(initialServiceLinkId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialServiceLinkId]);

  async function handleCalculate(overrideServiceLinkId?: string) {
    const slId = overrideServiceLinkId || selectedServiceLinkId;
    if (inputMode === "customer" && !slId) {
      setErrorMsg("Selecione um cliente com atendimento óptico ativo.");
      return;
    }
    if (inputMode === "terminal" && !terminalIdInput.trim()) {
      setErrorMsg("Informe o UUID do terminal óptico.");
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    const payload: BudgetCalculationRequest = {
      service_link_id: inputMode === "customer" ? slId : null,
      start_terminal_id: inputMode === "terminal" ? terminalIdInput.trim() : null,
      direction,
      profile_id: selectedProfileId || null,
      engineering_margin_db: engineeringMargin,
    };

    try {
      const res = await calculateOpticalBudget(payload);
      startTransition(() => {
        setBudgetResult(res);
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao calcular orçamento óptico";
      setErrorMsg(msg);
      setBudgetResult(null);
    } finally {
      setLoading(false);
    }
  }

  // Mudança de direção: atualiza o perfil/onda correspondente
  function handleDirectionChange(newDir: OpticalDirection) {
    setDirection(newDir);
    // Se o perfil atual não for compatível, reseta para padrão da direção
    setSelectedProfileId("");
  }

  const assessmentMeta = budgetResult
    ? ASSESSMENT_CONFIGS[budgetResult.assessment] || ASSESSMENT_CONFIGS.unknown
    : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Cabeçalho */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Calculator className="h-6 w-6 text-primary" />
            Orçamento Óptico e Balanço de Potência
          </h1>
          <p className="text-sm text-muted-foreground">
            Cálculo determinístico de atenuação acumulada, sensibilidade RX e margem de projeto (F13 / B10).
          </p>
        </div>

        {budgetResult && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/60 px-3 py-1.5 rounded-md border">
            <Layers className="h-3.5 w-3.5 text-primary" />
            <span>Revisão da Topologia: <strong>v{budgetResult.topology_revision}</strong></span>
          </div>
        )}
      </div>

      {/* Painel de Parâmetros e Filtros */}
      <Card className="shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Sliders className="h-4 w-4 text-primary" />
            Parâmetros do Enlace Óptico
          </CardTitle>
          <CardDescription>
            Configure a direção do sinal, o atendimento ou terminal de origem e os limites de potência.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Alternância de Modo (Cliente ou Terminal) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">
                Origem do Rastreamento
              </Label>
              <div className="flex rounded-md border p-1 bg-muted/30">
                <button
                  type="button"
                  onClick={() => setInputMode("customer")}
                  className={`flex-1 py-1.5 text-xs font-medium rounded transition-colors ${
                    inputMode === "customer"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Assinante / Atendimento
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode("terminal")}
                  className={`flex-1 py-1.5 text-xs font-medium rounded transition-colors ${
                    inputMode === "terminal"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Terminal Direto
                </button>
              </div>
            </div>

            {/* Direção Óptica */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">
                Direção do Sinal
              </Label>
              <div className="flex rounded-md border p-1 bg-muted/30">
                <button
                  type="button"
                  onClick={() => handleDirectionChange("downstream")}
                  className={`flex-1 py-1.5 text-xs font-medium rounded flex items-center justify-center gap-1.5 transition-colors ${
                    direction === "downstream"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <ArrowDownRight className="h-3.5 w-3.5 text-emerald-500" />
                  Downstream (1490 nm)
                </button>
                <button
                  type="button"
                  onClick={() => handleDirectionChange("upstream")}
                  className={`flex-1 py-1.5 text-xs font-medium rounded flex items-center justify-center gap-1.5 transition-colors ${
                    direction === "upstream"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <ArrowUpRight className="h-3.5 w-3.5 text-blue-500" />
                  Upstream (1310 nm)
                </button>
              </div>
            </div>

            {/* Perfil Óptico */}
            <div className="space-y-2">
              <Label htmlFor="profile-select" className="text-xs font-semibold uppercase text-muted-foreground">
                Perfil Óptico / Tecnologia
              </Label>
              <select
                id="profile-select"
                value={selectedProfileId}
                onChange={(e) => setSelectedProfileId(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="">
                  {direction === "downstream"
                    ? "Padrão GPON B+ (TX +3 dBm / RX -27 dBm)"
                    : "Padrão GPON B+ Upstream (TX +2.5 dBm / RX -28 dBm)"}
                </option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.technology} - {p.wavelength_nm} nm)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Seleção do Cliente ou Terminal + Margem */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1 border-t">
            {inputMode === "customer" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="customer-select" className="text-sm font-medium">
                    Cliente / Assinante
                  </Label>
                  <select
                    id="customer-select"
                    value={selectedCustomerId}
                    onChange={(e) => setSelectedCustomerId(e.target.value)}
                    className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="">Selecione um cliente...</option>
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code} — {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="link-select" className="text-sm font-medium">
                    Atendimento / Porta CTO
                  </Label>
                  <select
                    id="link-select"
                    value={selectedServiceLinkId}
                    onChange={(e) => setSelectedServiceLinkId(e.target.value)}
                    disabled={customerLinks.length === 0}
                    className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
                  >
                    {customerLinks.length === 0 ? (
                      <option value="">Nenhum atendimento encontrado</option>
                    ) : (
                      customerLinks.map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.status === "active" ? "● Ativo" : "○ Inativo"} — Porta: {l.port_id.slice(0, 8)}…
                        </option>
                      ))
                    )}
                  </select>
                </div>
              </>
            ) : (
              <div className="md:col-span-2 space-y-2">
                <Label htmlFor="terminal-uuid" className="text-sm font-medium">
                  UUID do Terminal Óptico
                </Label>
                <Input
                  id="terminal-uuid"
                  placeholder="ex: a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                  value={terminalIdInput}
                  onChange={(e) => setTerminalIdInput(e.target.value)}
                  className="font-mono text-xs"
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="margin-input" className="text-sm font-medium flex items-center justify-between">
                <span>Margem de Engenharia</span>
                <span className="text-xs text-muted-foreground">dB</span>
              </Label>
              <div className="flex items-center gap-3">
                <Input
                  id="margin-input"
                  type="number"
                  step="0.5"
                  min="0.0"
                  max="15.0"
                  value={engineeringMargin}
                  onChange={(e) => setEngineeringMargin(parseFloat(e.target.value) || 0)}
                  className="w-28"
                />
                <Button
                  onClick={() => handleCalculate()}
                  disabled={loading}
                  className="flex-1 font-medium gap-2"
                >
                  {loading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Calculando…
                    </>
                  ) : (
                    <>
                      <Zap className="h-4 w-4" />
                      Calcular Orçamento
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-400 rounded-md text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resultados do Orçamento */}
      {budgetResult && (
        <div className="space-y-6">
          {/* Banner de Veredito Oficial */}
          {assessmentMeta && (
            <div
              className={`p-4 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-4 ${assessmentMeta.badgeClass}`}
            >
              <div className="flex items-start gap-3">
                {budgetResult.assessment === "pass" && (
                  <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                )}
                {budgetResult.assessment === "low_margin" && (
                  <AlertTriangle className="h-6 w-6 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                )}
                {budgetResult.assessment === "below_sensitivity" && (
                  <XCircle className="h-6 w-6 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                )}
                {budgetResult.assessment === "overload" && (
                  <Zap className="h-6 w-6 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
                )}
                {budgetResult.assessment === "unknown" && (
                  <HelpCircle className="h-6 w-6 text-slate-600 dark:text-slate-400 shrink-0 mt-0.5" />
                )}

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-base">{assessmentMeta.label}</h3>
                    <Badge variant={assessmentMeta.variant} className="text-[10px] uppercase font-bold tracking-wider">
                      {budgetResult.status === "complete" ? "Completo" : "Incompleto"}
                    </Badge>
                  </div>
                  <p className="text-xs opacity-90 mt-0.5">{assessmentMeta.description}</p>
                </div>
              </div>

              <div className="flex flex-col md:items-end text-xs shrink-0">
                <span>Comprimento de Onda: <strong>{budgetResult.wavelength_nm || "—"} nm</strong></span>
                <span>Direção: <strong className="capitalize">{budgetResult.direction}</strong></span>
              </div>
            </div>
          )}

          {/* Cards de Métricas Principais */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            {/* 1. Potência TX */}
            <Card className="p-3 shadow-sm bg-card/60">
              <span className="text-[11px] font-semibold uppercase text-muted-foreground block">
                TX Nominal
              </span>
              <span className="text-lg font-bold tracking-tight text-foreground block mt-1">
                {formatPowerDbm(budgetResult.tx_dbm)}
              </span>
              <span className="text-[10px] text-muted-foreground">Transmissor</span>
            </Card>

            {/* 2. Perda Total */}
            <Card className="p-3 shadow-sm bg-card/60">
              <span className="text-[11px] font-semibold uppercase text-muted-foreground block">
                Perda Total
              </span>
              <span className="text-lg font-bold tracking-tight text-amber-600 dark:text-amber-400 block mt-1">
                {formatLossDb(budgetResult.total_loss_db)}
              </span>
              <span className="text-[10px] text-muted-foreground">Atenuação somada</span>
            </Card>

            {/* 3. RX Previsto */}
            <Card className="p-3 shadow-sm bg-card/60 border-primary/30">
              <span className="text-[11px] font-semibold uppercase text-primary block">
                RX Previsto
              </span>
              <span className="text-lg font-bold tracking-tight text-foreground block mt-1">
                {formatPowerDbm(budgetResult.predicted_rx_dbm)}
              </span>
              <span className="text-[10px] text-muted-foreground">Recepção nominal</span>
            </Card>

            {/* 4. Sensibilidade RX */}
            <Card className="p-3 shadow-sm bg-card/60">
              <span className="text-[11px] font-semibold uppercase text-muted-foreground block">
                Sensibilidade
              </span>
              <span className="text-lg font-bold tracking-tight text-foreground block mt-1">
                {formatPowerDbm(-27.0)}
              </span>
              <span className="text-[10px] text-muted-foreground">Ponto de corte</span>
            </Card>

            {/* 5. Margem de Projeto */}
            <Card className="p-3 shadow-sm bg-card/60">
              <span className="text-[11px] font-semibold uppercase text-muted-foreground block">
                Margem Projeto
              </span>
              <span className="text-lg font-bold tracking-tight text-foreground block mt-1">
                {formatLossDb(budgetResult.engineering_margin_db)}
              </span>
              <span className="text-[10px] text-muted-foreground">Engenharia</span>
            </Card>

            {/* 6. Margem Restante */}
            <Card className="p-3 shadow-sm bg-card/60">
              <span className="text-[11px] font-semibold uppercase text-muted-foreground block">
                Margem Líquida
              </span>
              <span
                className={`text-lg font-bold tracking-tight block mt-1 ${
                  budgetResult.remaining_margin_db !== null &&
                  budgetResult.remaining_margin_db !== undefined &&
                  budgetResult.remaining_margin_db >= 0
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-rose-600 dark:text-rose-400"
                }`}
              >
                {formatMarginDb(budgetResult.remaining_margin_db)}
              </span>
              <span className="text-[10px] text-muted-foreground">Disponível</span>
            </Card>

            {/* 7. Sobrecarga */}
            <Card className="p-3 shadow-sm bg-card/60">
              <span className="text-[11px] font-semibold uppercase text-muted-foreground block">
                Sobrecarga
              </span>
              <span className="text-lg font-bold tracking-tight text-foreground block mt-1">
                {formatPowerDbm(-8.0)}
              </span>
              <span className="text-[10px] text-muted-foreground">Saturação máx</span>
            </Card>

            {/* 8. Folga Sobrecarga */}
            <Card className="p-3 shadow-sm bg-card/60">
              <span className="text-[11px] font-semibold uppercase text-muted-foreground block">
                Folga Saturação
              </span>
              <span className="text-lg font-bold tracking-tight text-emerald-600 dark:text-emerald-400 block mt-1">
                {formatLossDb(budgetResult.overload_headroom_db)}
              </span>
              <span className="text-[10px] text-muted-foreground">Distância máx</span>
            </Card>
          </div>

          {/* Premissas e Hipóteses Adotadas */}
          {budgetResult.assumptions && budgetResult.assumptions.length > 0 && (
            <div className="bg-muted/40 border rounded-lg p-3 text-xs space-y-1">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Info className="h-3.5 w-3.5 text-primary" />
                Premissas de Engenharia e Convenções Adotadas:
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-muted-foreground pl-1">
                {budgetResult.assumptions.map((asm, i) => (
                  <li key={i}>{asm}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Dados Faltantes (se houver) */}
          {budgetResult.missing_fields && budgetResult.missing_fields.length > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-xs space-y-1">
              <span className="font-semibold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                Parâmetros Faltantes que Impedem o Cálculo Total:
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-amber-600 dark:text-amber-400 pl-1">
                {budgetResult.missing_fields.map((mf, i) => (
                  <li key={i}>{mf}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Memória de Cálculo Passo a Passo (Breakdown) */}
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Radio className="h-4 w-4 text-primary" />
                  Memória de Cálculo e Atenuação Passo a Passo
                </span>
                <span className="text-xs font-normal text-muted-foreground">
                  {budgetResult.steps.length} elementos atravessados
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left" role="table">
                  <thead className="bg-muted/50 border-y text-muted-foreground font-semibold">
                    <tr>
                      <th className="py-2.5 px-3 w-12 text-center">#</th>
                      <th className="py-2.5 px-3">Elemento Óptico</th>
                      <th className="py-2.5 px-3">Tipo</th>
                      <th className="py-2.5 px-3 text-right">Comprimento / Medida</th>
                      <th className="py-2.5 px-3 text-right">Perda Unitária</th>
                      <th className="py-2.5 px-3 text-right">Perda Acumulada</th>
                      <th className="py-2.5 px-3">Origem do Parâmetro</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {budgetResult.steps.map((step) => {
                      const isSplitter = step.element_type.includes("splitter");
                      const isFiber = step.element_type.includes("fiber");
                      const isFusion = step.element_type.includes("fusion");
                      const isMated = step.element_type.includes("mated") || step.element_type.includes("connector");

                      return (
                        <tr
                          key={step.step_number}
                          className="hover:bg-muted/30 transition-colors font-mono"
                        >
                          <td className="py-2.5 px-3 text-center text-muted-foreground">
                            {step.step_number}
                          </td>
                          <td className="py-2.5 px-3 font-sans font-medium text-foreground">
                            {step.element_name}
                          </td>
                          <td className="py-2.5 px-3 font-sans capitalize text-muted-foreground">
                            <span
                              className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                isSplitter
                                  ? "bg-purple-500/10 text-purple-700 dark:text-purple-300"
                                  : isFiber
                                  ? "bg-blue-500/10 text-blue-700 dark:text-blue-300"
                                  : isFusion
                                  ? "bg-amber-500/10 text-amber-700 dark:text-amber-300"
                                  : isMated
                                  ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                                  : "bg-muted text-muted-foreground"
                              }`}
                            >
                              {step.element_type}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right text-foreground">
                            {isFiber ? formatDistance(step.individual_value) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-semibold text-amber-600 dark:text-amber-400">
                            {formatLossDb(step.loss_db)}
                          </td>
                          <td className="py-2.5 px-3 text-right font-bold text-foreground">
                            {formatLossDb(step.accumulated_loss_db)}
                          </td>
                          <td className="py-2.5 px-3 font-sans text-muted-foreground capitalize">
                            {step.parameter_source}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
