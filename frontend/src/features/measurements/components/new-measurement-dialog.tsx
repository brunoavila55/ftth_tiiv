"use client";

import * as React from "react";
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createMeasurement } from "../api";
import type { MeasurementCreate, MeasurementDirection, MeasurementOrigin, MeasurementRead } from "../types";

interface NewMeasurementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (measurement: MeasurementRead) => void;
  initialTerminalId?: string;
  initialServiceLinkId?: string;
}

export function NewMeasurementDialog({
  open,
  onOpenChange,
  onSuccess,
  initialTerminalId = "",
  initialServiceLinkId = "",
}: NewMeasurementDialogProps) {
  const [terminalId, setTerminalId] = useState(initialTerminalId);
  const [serviceLinkId, setServiceLinkId] = useState(initialServiceLinkId);
  const [powerDbm, setPowerDbm] = useState("-25.40");
  const [wavelengthNm, setWavelengthNm] = useState(1490);
  const [direction, setDirection] = useState<MeasurementDirection>("downstream");
  const [origin, setOrigin] = useState<MeasurementOrigin>("manual_entry");
  const [instrumentModel, setInstrumentModel] = useState("Power Meter de Campo");
  const [measuredAt, setMeasuredAt] = useState(new Date().toISOString().slice(0, 16));
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!terminalId.trim()) {
      setErrorMsg("O UUID do terminal receptor é obrigatório.");
      return;
    }
    const numPower = parseFloat(powerDbm.replace(",", "."));
    if (isNaN(numPower)) {
      setErrorMsg("Informe um valor numérico válido para a potência em dBm.");
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    try {
      const payload: MeasurementCreate = {
        terminal_id: terminalId.trim(),
        service_link_id: serviceLinkId.trim() || null,
        power_dbm: numPower,
        wavelength_nm: Number(wavelengthNm),
        direction,
        origin,
        instrument_model: instrumentModel.trim() || null,
        measured_at: measuredAt ? new Date(measuredAt).toISOString() : null,
        notes: notes.trim() || null,
      };

      const result = await createMeasurement(payload);
      onSuccess(result);
      onOpenChange(false);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Erro ao registrar medição óptica.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Registrar Medição Óptica de Campo</DialogTitle>
            <DialogDescription>
              Insira os dados coletados com o medidor de potência (Power Meter / OTDR) no ponto de recepção.
            </DialogDescription>
          </DialogHeader>

          {errorMsg && (
            <div className="my-3 p-3 rounded bg-destructive/15 text-destructive text-sm font-medium border border-destructive/30">
              {errorMsg}
            </div>
          )}

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="terminal_id" className="text-right text-xs">
                Terminal ID *
              </Label>
              <Input
                id="terminal_id"
                value={terminalId}
                onChange={(e) => setTerminalId(e.target.value)}
                placeholder="UUID do terminal óptico"
                className="col-span-3 font-mono text-xs"
                required
              />
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="service_link_id" className="text-right text-xs">
                Atendimento
              </Label>
              <Input
                id="service_link_id"
                value={serviceLinkId}
                onChange={(e) => setServiceLinkId(e.target.value)}
                placeholder="UUID do atendimento de cliente (opcional)"
                className="col-span-3 font-mono text-xs"
              />
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="power_dbm" className="text-right text-xs">
                Potência (dBm) *
              </Label>
              <div className="col-span-3 flex items-center gap-2">
                <Input
                  id="power_dbm"
                  type="text"
                  value={powerDbm}
                  onChange={(e) => setPowerDbm(e.target.value)}
                  placeholder="Ex: -25.40"
                  className="font-mono text-sm"
                  required
                />
                <span className="text-xs text-muted-foreground whitespace-nowrap">dBm</span>
              </div>
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="wavelength" className="text-right text-xs">
                Comprimento de Onda
              </Label>
              <select
                id="wavelength"
                value={wavelengthNm}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  setWavelengthNm(val);
                  if (val === 1310) setDirection("upstream");
                  if (val === 1490) setDirection("downstream");
                }}
                className="col-span-3 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value={1490}>1490 nm — GPON Downstream (Padrão ONU)</option>
                <option value={1310}>1310 nm — GPON Upstream (Padrão OLT)</option>
                <option value={1550}>1550 nm — Vídeo Overlay / CATV</option>
                <option value={1577}>1577 nm — XGS-PON Downstream</option>
                <option value={1270}>1270 nm — XGS-PON Upstream</option>
              </select>
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="direction" className="text-right text-xs">
                Direção do Sinal
              </Label>
              <select
                id="direction"
                value={direction}
                onChange={(e) => setDirection(e.target.value as MeasurementDirection)}
                className="col-span-3 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="downstream">Downstream (OLT → ONU/CTO)</option>
                <option value="upstream">Upstream (ONU → OLT)</option>
              </select>
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="origin" className="text-right text-xs">
                Origem da Medição
              </Label>
              <select
                id="origin"
                value={origin}
                onChange={(e) => setOrigin(e.target.value as MeasurementOrigin)}
                className="col-span-3 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="manual_entry">Registro Manual</option>
                <option value="field_power_meter">Power Meter Óptico de Campo</option>
                <option value="otdr">Reflectômetro Óptico (OTDR)</option>
              </select>
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="instrument" className="text-right text-xs">
                Instrumento
              </Label>
              <Input
                id="instrument"
                value={instrumentModel}
                onChange={(e) => setInstrumentModel(e.target.value)}
                placeholder="Ex: EXFO PPM-350D / Yokogawa"
                className="col-span-3 text-xs"
              />
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="measured_at" className="text-right text-xs">
                Data e Hora
              </Label>
              <Input
                id="measured_at"
                type="datetime-local"
                value={measuredAt}
                onChange={(e) => setMeasuredAt(e.target.value)}
                className="col-span-3 text-xs"
              />
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="notes" className="text-right text-xs">
                Observações
              </Label>
              <Input
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ex: Conector SC/APC inspecionado e limpo antes da leitura"
                className="col-span-3 text-xs"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Registrando..." : "Salvar Medição"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
