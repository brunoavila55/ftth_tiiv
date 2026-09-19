"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import { Plus, RefreshCw, Gauge, AlertCircle, Trash2, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { deleteMeasurement, listMeasurements } from "../api";
import { formatDateTime, formatExcessLossDb, formatPowerDbm, getOriginLabel } from "../utils";
import { NewMeasurementDialog } from "./new-measurement-dialog";
import { MeasurementComparisonModal } from "./measurement-comparison-modal";
import type { MeasurementRead } from "../types";
import { PermissionGate } from "@/components/auth/permission-gate";

export function MeasurementsView() {
  const [measurements, setMeasurements] = useState<MeasurementRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Diálogos
  const [newDialogOpen, setNewDialogOpen] = useState(false);
  const [selectedForComparison, setSelectedForComparison] = useState<MeasurementRead | null>(null);
  const [comparisonModalOpen, setComparisonModalOpen] = useState(false);

  const fetchMeasurements = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await listMeasurements({ page: 1, page_size: 50 });
      setMeasurements(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Falha ao carregar lista de medições.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMeasurements();
  }, []);

  const handleDelete = async (m: MeasurementRead) => {
    if (!confirm(`Deseja realmente remover a medição no terminal ${m.terminal_id}?`)) {
      return;
    }
    try {
      await deleteMeasurement(m.id, m.version);
      setMeasurements((prev) => prev.filter((item) => item.id !== m.id));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao excluir medição.");
    }
  };

  const handleOpenComparison = (m: MeasurementRead) => {
    setSelectedForComparison(m);
    setComparisonModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Gauge className="h-6 w-6 text-primary" />
            Medições & Potência Óptica
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Registro manual de leituras ópticas de campo, histórico temporal e conferência contra o projeto de atenuação.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchMeasurements} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Atualizar
          </Button>
          <PermissionGate permission="measurements:write">
            <Button size="sm" onClick={() => setNewDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Nova Medição
            </Button>
          </PermissionGate>
        </div>
      </div>

      {/* Cards de Resumo */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="py-3">
            <CardDescription className="text-xs">Total de Medições Registradas</CardDescription>
            <CardTitle className="text-2xl font-bold">{total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="py-3">
            <CardDescription className="text-xs">Critério de Engenharia</CardDescription>
            <CardTitle className="text-sm font-semibold text-muted-foreground">
              Perda Excedente = RX Previsto - RX Medido
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="py-3">
            <CardDescription className="text-xs">Validação de Compatibilidade</CardDescription>
            <CardTitle className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
              Restrita a mesma Onda & Receptor
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Mensagem de Erro */}
      {errorMsg && (
        <div className="p-4 rounded-md bg-destructive/15 border border-destructive/30 text-destructive text-sm flex items-center gap-2">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tabela de Medições */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Histórico de Medições de Campo</CardTitle>
          <CardDescription className="text-xs">
            Leituras coletadas em terminais ópticos e pontos de entrega de assinantes.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-muted/50 text-xs text-muted-foreground uppercase border-b">
                <tr>
                  <th className="px-4 py-3">Data / Hora</th>
                  <th className="px-4 py-3">Terminal Receptor</th>
                  <th className="px-4 py-3">Onda / Direção</th>
                  <th className="px-4 py-3">Instrumento</th>
                  <th className="px-4 py-3 text-right">Potência Medida</th>
                  <th className="px-4 py-3 text-right">Potência Prevista</th>
                  <th className="px-4 py-3 text-right">Perda Excedente</th>
                  <th className="px-4 py-3 text-center">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                      Carregando histórico de medições...
                    </td>
                  </tr>
                )}
                {!loading && measurements.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                      Nenhuma medição óptica registrada até o momento. Clique em &quot;Nova Medição&quot; para inserir a primeira leitura.
                    </td>
                  </tr>
                )}
                {!loading &&
                  measurements.map((m) => {
                    const hasComparison = m.predicted_power_dbm !== null && m.excess_loss_db !== null;
                    const isExcessive = m.excess_loss_db !== null && m.excess_loss_db > 2.0;

                    return (
                      <tr key={m.id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3 whitespace-nowrap text-xs">
                          {formatDateTime(m.measured_at)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          <span title={m.terminal_id}>
                            {m.terminal_id.slice(0, 8)}...{m.terminal_id.slice(-4)}
                          </span>
                          {m.service_link_id && (
                            <span className="block text-[10px] text-muted-foreground">
                              Atendimento: {m.service_link_id.slice(0, 8)}...
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs">
                          <span className="font-semibold">{m.wavelength_nm} nm</span>
                          <span className="block text-[11px] text-muted-foreground uppercase">
                            {m.direction}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <span>{m.instrument_model || "—"}</span>
                          <span className="block text-[10px] text-muted-foreground">
                            {getOriginLabel(m.origin)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-sm font-semibold whitespace-nowrap">
                          {formatPowerDbm(m.power_dbm)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs whitespace-nowrap text-muted-foreground">
                          {formatPowerDbm(m.predicted_power_dbm)}
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          {hasComparison ? (
                            <Badge
                              variant={isExcessive ? "destructive" : "default"}
                              className="font-mono text-xs"
                            >
                              {formatExcessLossDb(m.excess_loss_db)}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center whitespace-nowrap">
                          <div className="flex items-center justify-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              title="Comparar com Orçamento"
                              onClick={() => handleOpenComparison(m)}
                              className="h-8 w-8 p-0"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <PermissionGate permission="measurements:write">
                              <Button
                                variant="ghost"
                                size="sm"
                                title="Excluir Medição"
                                onClick={() => handleDelete(m)}
                                className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </PermissionGate>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Diálogos */}
      <NewMeasurementDialog
        open={newDialogOpen}
        onOpenChange={setNewDialogOpen}
        onSuccess={(newMeas) => {
          setMeasurements((prev) => [newMeas, ...prev]);
          setTotal((prev) => prev + 1);
        }}
      />

      <MeasurementComparisonModal
        measurement={selectedForComparison}
        open={comparisonModalOpen}
        onOpenChange={setComparisonModalOpen}
      />
    </div>
  );
}
