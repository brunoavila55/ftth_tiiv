"use client";

import * as React from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, type SiteRead } from "@/lib/api/types";
import type { DeviceRead } from "@/features/inventory/api";
import { createRadioLink, updateRadioLink, type RadioLinkRead } from "../api";

interface LinkFormValues {
  code: string;
  name: string;
  site_a_id: string;
  site_b_id: string;
  radio_a_id: string;
  radio_b_id: string;
  frequency_mhz: string;
  channel_width_mhz: string;
  status: "planned" | "installed" | "retired";
  notes: string;
}

const EMPTY_FORM: LinkFormValues = {
  code: "", name: "", site_a_id: "", site_b_id: "", radio_a_id: "", radio_b_id: "",
  frequency_mhz: "", channel_width_mhz: "", status: "planned", notes: "",
};

export interface RadioLinkFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  link?: RadioLinkRead | null;
  sites: SiteRead[];
  radios: DeviceRead[];
  onSuccess: () => void;
}

export function RadioLinkFormDialog({ open, onOpenChange, link, sites, radios, onSuccess }: RadioLinkFormDialogProps) {
  const [form, setForm] = React.useState<LinkFormValues>(EMPTY_FORM);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    setForm(link ? {
      code: link.code,
      name: link.name,
      site_a_id: link.site_a_id,
      site_b_id: link.site_b_id,
      radio_a_id: link.radio_a_id,
      radio_b_id: link.radio_b_id,
      frequency_mhz: String(link.frequency_mhz),
      channel_width_mhz: String(link.channel_width_mhz),
      status: link.status,
      notes: link.notes ?? "",
    } : EMPTY_FORM);
    setError(null);
  }, [link, open]);

  const set = (key: keyof LinkFormValues, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const frequency = Number(form.frequency_mhz);
    const width = Number(form.channel_width_mhz);
    if (!form.code.trim() || !form.name.trim() || !form.site_a_id || !form.site_b_id || !form.radio_a_id || !form.radio_b_id) {
      setError("Preencha o código, nome, sites e rádios das duas pontas.");
      return;
    }
    if (form.site_a_id === form.site_b_id || form.radio_a_id === form.radio_b_id) {
      setError("Origem e destino devem ser diferentes.");
      return;
    }
    if (!Number.isFinite(frequency) || frequency <= 0 || frequency > 100000 || !Number.isFinite(width) || width <= 0 || width > 10000) {
      setError("Informe frequência e largura de canal válidas em MHz.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const details = {
        name: form.name.trim(),
        frequency_mhz: frequency,
        channel_width_mhz: width,
        status: form.status,
        notes: form.notes.trim() || null,
      };
      if (link) {
        await updateRadioLink(link.id, details, link.version);
      } else {
        await createRadioLink({
          ...details,
          code: form.code.trim().toUpperCase(),
          site_a_id: form.site_a_id,
          site_b_id: form.site_b_id,
          radio_a_id: form.radio_a_id,
          radio_b_id: form.radio_b_id,
        });
      }
      onSuccess();
      onOpenChange(false);
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 409 || cause.status === 412)) {
        setError("O enlace foi alterado por outra pessoa ou já existe. Recarregue a lista e tente novamente.");
      } else {
        setError(cause instanceof ApiError ? cause.detail ?? cause.message : "Não foi possível salvar o enlace.");
      }
    } finally {
      setSaving(false);
    }
  };

  const radioOptions = (siteId: string) => radios.filter((radio) => radio.site_id === siteId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{link ? `Editar Enlace — ${link.code}` : "Novo Enlace de Rádio"}</DialogTitle>
          <DialogDescription>Associe dois sites wireless e um rádio em cada ponta.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          {error && <p role="alert" className="rounded-md bg-destructive/10 p-3 text-xs text-destructive">{error}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1"><Label htmlFor="link-code">Código *</Label><Input id="link-code" value={form.code} onChange={(e) => set("code", e.target.value)} maxLength={50} disabled={saving || Boolean(link)} /></div>
            <div className="space-y-1"><Label htmlFor="link-name">Nome *</Label><Input id="link-name" value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={100} disabled={saving} /></div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {(["a", "b"] as const).map((end) => {
              const siteKey = `site_${end}_id` as const;
              const radioKey = `radio_${end}_id` as const;
              return <div key={end} className="space-y-3 rounded-lg border border-border p-3">
                <p className="text-sm font-semibold">Ponta {end.toUpperCase()}</p>
                <div className="space-y-1"><Label htmlFor={`link-site-${end}`}>POP ou Torre *</Label>
                  <select id={`link-site-${end}`} value={form[siteKey]} onChange={(e) => setForm((current) => ({ ...current, [siteKey]: e.target.value, [radioKey]: "" }))} disabled={saving || Boolean(link)} className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs">
                    <option value="">Selecione o ponto</option>
                    {sites.map((site) => <option key={site.id} value={site.id}>{site.code} — {site.name}</option>)}
                  </select>
                </div>
                <div className="space-y-1"><Label htmlFor={`link-radio-${end}`}>Rádio *</Label>
                  <select id={`link-radio-${end}`} value={form[radioKey]} onChange={(e) => set(radioKey, e.target.value)} disabled={saving || Boolean(link) || !form[siteKey]} className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs">
                    <option value="">Selecione o rádio</option>
                    {radioOptions(form[siteKey]).map((radio) => <option key={radio.id} value={radio.id}>{radio.code} — {radio.manufacturer} {radio.model}</option>)}
                  </select>
                </div>
              </div>;
            })}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1"><Label htmlFor="link-frequency">Frequência (MHz) *</Label><Input id="link-frequency" type="number" min="0.001" max="100000" step="any" value={form.frequency_mhz} onChange={(e) => set("frequency_mhz", e.target.value)} disabled={saving} /></div>
            <div className="space-y-1"><Label htmlFor="link-width">Largura de canal (MHz) *</Label><Input id="link-width" type="number" min="0.001" max="10000" step="any" value={form.channel_width_mhz} onChange={(e) => set("channel_width_mhz", e.target.value)} disabled={saving} /></div>
          </div>
          <div className="space-y-1"><Label htmlFor="link-status">Situação</Label>
            <select id="link-status" value={form.status} onChange={(e) => set("status", e.target.value)} disabled={saving} className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs">
              <option value="planned">Planejado</option><option value="installed">Instalado</option><option value="retired">Desativado</option>
            </select>
          </div>
          <div className="space-y-1"><Label htmlFor="link-notes">Observações</Label><textarea id="link-notes" value={form.notes} onChange={(e) => set("notes", e.target.value)} maxLength={5000} rows={2} disabled={saving} className="w-full rounded-md border border-input bg-background p-2 text-xs" /></div>
          <DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>Cancelar</Button><Button type="submit" disabled={saving}>{link ? "Salvar Alterações" : "Cadastrar Enlace"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
