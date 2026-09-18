"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { compareMeasurement } from "../api";
import { formatDateTime, formatExcessLossDb, formatPowerDbm } from "../utils";
import type { MeasurementComparisonResponse, MeasurementRead } from "../types";

interface MeasurementComparisonModalProps {
  measurement: MeasurementRead | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MeasurementComparisonModal({
  measurement,
  open,
  onOpenChange,
}: MeasurementComparisonModalProps) {
  const [loading, setLoading] = useState(false);
  const [toleranceDb, setToleranceDb] = useState(2.0);
  const [comparison, setComparison] = useState<MeasurementComparisonResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (open && measurement) {
      loadComparison(measurement.id, toleranceDb);
    } else {
      setComparison(null);
      setErrorMsg(null);
    }
  }, [open, measurement, toleranceDb]);

  const loadComparison = async (id: string, tol: number) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await compareMeasurement(id, tol);
      setComparison(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Erro ao carregar comparação de potência.");
    } finally {
      setLoading(false);
    }
  };

  if (!measurement) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[620px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>Conferência de Potência Óptica</span>
            {comparison && comparison.is_compatible && (
              <Badge variant={comparison.is_within_tolerance ? "default" : "destructive"}>
                {comparison.is_within_tolerance ? "Dentro da Tolerância" : "Atenuação Excedente"}
              </Badge>
            )}
            {comparison && !comparison.is_compatible && (
              <Badge variant="outline" className="text-amber-600 border-amber-500">
                Incompatível para Análise
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Comparativo entre a potência real de campo e a potência prevista pelo projeto na topologia.
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="py-8 text-center text-sm text-muted-foreground animate-pulse">
            Carregando cálculo de orçamento e comparando leituras...
          </div>
        )}

        {errorMsg && (
          <div className="my-3 p-3 rounded bg-destructive/15 text-destructive text-sm border border-destructive/30">
            {errorMsg}
          </div>
        )}

        {comparison && !loading && (
          <div className="space-y-4 py-2">
            {/* Metadados da medição */}
            <div className="bg-muted/40 p-3 rounded-md border text-xs grid grid-cols-2 gap-2">
              <div>
                <span className="text-muted-foreground">Comprimento de onda:</span>{" "}
                <span className="font-semibold">{comparison.wavelength_nm} nm</span>
              </div>
              <div>
                <span className="text-muted-foreground">Direção:</span>{" "}
                <span className="font-semibold uppercase">{comparison.direction}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Data da Medição:</span>{" "}
                <span>{formatDateTime(measurement.measured_at)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Instrumento:</span>{" "}
                <span>{measurement.instrument_model || "Não informado"}</span>
              </div>
            </div>

            {/* Aviso de Incompatibilidade */}
            {!comparison.is_compatible && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-md text-amber-800 dark:text-amber-300 text-xs">
                <p className="font-semibold mb-1">Aviso de Incompatibilidade</p>
                <p>{comparison.incompatibility_reason}</p>
                <p className="mt-1 text-[11px] opacity-80">
                  Por diretriz de engenharia, parâmetros incompatíveis não geram alarmes conclusivos nem cálculo de perda excedente.
                </p>
              </div>
            )}

            {/* Comparativo de potências quando compatível */}
            {comparison.is_compatible && (
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 border rounded-lg bg-card text-center">
                  <span className="text-xs text-muted-foreground block mb-1">Potência Prevista</span>
                  <span className="font-mono text-lg font-bold text-blue-600 dark:text-blue-400">
                    {formatPowerDbm(comparison.predicted_power_dbm)}
                  </span>
                  <span className="text-[10px] text-muted-foreground block mt-1">Cálculo Teórico</span>
                </div>

                <div className="p-3 border rounded-lg bg-card text-center">
                  <span className="text-xs text-muted-foreground block mb-1">Potência Medida</span>
                  <span className="font-mono text-lg font-bold text-foreground">
                    {formatPowerDbm(comparison.measured_power_dbm)}
                  </span>
                  <span className="text-[10px] text-muted-foreground block mt-1">Leitura de Campo</span>
                </div>

                <div
                  className={`p-3 border rounded-lg text-center ${
                    comparison.is_within_tolerance
                      ? "bg-emerald-500/10 border-emerald-500/30"
                      : "bg-destructive/10 border-destructive/30"
                  }`}
                >
                  <span className="text-xs text-muted-foreground block mb-1">Perda Excedente</span>
                  <span
                    className={`font-mono text-lg font-bold ${
                      comparison.is_within_tolerance ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
                    }`}
                  >
                    {formatExcessLossDb(comparison.excess_loss_db)}
                  </span>
                  <span className="text-[10px] text-muted-foreground block mt-1">
                    Tol: ±{toleranceDb.toFixed(1)} dB
                  </span>
                </div>
              </div>
            )}

            {/* Memória explicativa */}
            {comparison.is_compatible && comparison.predicted_power_dbm !== null && (
              <div className="bg-muted/30 p-3 rounded border text-xs space-y-1">
                <div className="font-semibold text-muted-foreground">Fórmula de Perda Excedente:</div>
                <div className="font-mono text-foreground">
                  Perda Excedente = RX Previsto ({formatPowerDbm(comparison.predicted_power_dbm)}) - RX Medido ({formatPowerDbm(comparison.measured_power_dbm)}) ={" "}
                  <span className="font-bold">{formatExcessLossDb(comparison.excess_loss_db)}</span>
                </div>
                {comparison.excess_loss_db !== null && comparison.excess_loss_db > 0 ? (
                  <p className="text-[11px] text-muted-foreground pt-1">
                    Valor positivo indica atenuação real adicional de {formatExcessLossDb(comparison.excess_loss_db)} em relação ao modelo de perdas cadastrado.
                  </p>
                ) : (
                  <p className="text-[11px] text-muted-foreground pt-1">
                    Sinal recebido compatível ou superior à margem mínima do projeto.
                  </p>
                )}
              </div>
            )}

            {/* Ajuste interativo da tolerância */}
            <div className="flex items-center justify-between text-xs pt-1">
              <span className="text-muted-foreground">Ajustar Tolerância de Desvio:</span>
              <div className="flex items-center gap-2">
                {[1.0, 2.0, 3.0, 5.0].map((tol) => (
                  <Button
                    key={tol}
                    size="sm"
                    variant={toleranceDb === tol ? "default" : "outline"}
                    className="h-6 px-2 text-xs"
                    onClick={() => setToleranceDb(tol)}
                  >
                    ±{tol.toFixed(1)} dB
                  </Button>
                ))}
              </div>
            </div>

            {/* Alerta de Boas Práticas FTTH */}
            <div className="p-3 bg-muted/50 border rounded text-[11px] text-muted-foreground space-y-1">
              <span className="font-semibold text-foreground block">
                Diretriz de Diagnóstico Óptico:
              </span>
              <p>
                Um desvio ou perda excedente isolada indica divergência em relação ao modelo documentado (ex: raio de curvatura acentuado, sujeira em conector óptico ou degradação de fusão), mas <strong>não localiza a falha nem comprova a causa física</strong> sem inspeção dos pontos intermediários ou reflectometria de campo (OTDR).
              </p>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
