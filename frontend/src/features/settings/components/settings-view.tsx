"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Building2,
  Clock,
  Palette,
  Users,
  History,
  ExternalLink,
  Layers,
  Loader2,
  Save,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PermissionGate } from "@/components/auth/permission-gate";
import { ApiError } from "@/lib/api/types";
import { getAppSettings, updateAppSettings } from "../api";

const NBR_COLORS = [
  { pos: 1, name: "Verde", hex: "#16a34a" },
  { pos: 2, name: "Amarelo", hex: "#ca8a04" },
  { pos: 3, name: "Branco", hex: "#f8fafc", border: true },
  { pos: 4, name: "Azul", hex: "#2563eb" },
  { pos: 5, name: "Vermelho", hex: "#dc2626" },
  { pos: 6, name: "Violeta", hex: "#7c3aed" },
  { pos: 7, name: "Marrom", hex: "#854d0e" },
  { pos: 8, name: "Rosa", hex: "#db2777" },
  { pos: 9, name: "Preto", hex: "#0f172a" },
  { pos: 10, name: "Cinza", hex: "#64748b" },
  { pos: 11, name: "Laranja", hex: "#ea580c" },
  { pos: 12, name: "Aqua", hex: "#0891b2" },
];

const TIA_COLORS = [
  { pos: 1, name: "Azul", hex: "#2563eb" },
  { pos: 2, name: "Laranja", hex: "#ea580c" },
  { pos: 3, name: "Verde", hex: "#16a34a" },
  { pos: 4, name: "Marrom", hex: "#854d0e" },
  { pos: 5, name: "Cinza", hex: "#64748b" },
  { pos: 6, name: "Branco", hex: "#f8fafc", border: true },
  { pos: 7, name: "Vermelho", hex: "#dc2626" },
  { pos: 8, name: "Preto", hex: "#0f172a" },
  { pos: 9, name: "Amarelo", hex: "#ca8a04" },
  { pos: 10, name: "Violeta", hex: "#7c3aed" },
  { pos: 11, name: "Rosa", hex: "#db2777" },
  { pos: 12, name: "Aqua", hex: "#0891b2" },
];

export function SettingsView() {
  const [selectedStandard, setSelectedStandard] = React.useState<"NBR" | "TIA">("NBR");
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["app-settings"],
    queryFn: getAppSettings,
  });
  const [form, setForm] = React.useState({
    organization_name: "",
    timezone: "",
    longitude: "",
    latitude: "",
    default_map_zoom: "14",
    excess_loss_tolerance_db: "2",
  });
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!settingsQuery.data) return;
    setForm({
      organization_name: settingsQuery.data.organization_name,
      timezone: settingsQuery.data.timezone,
      longitude: String(settingsQuery.data.default_map_center[0]),
      latitude: String(settingsQuery.data.default_map_center[1]),
      default_map_zoom: String(settingsQuery.data.default_map_zoom),
      excess_loss_tolerance_db: String(settingsQuery.data.excess_loss_tolerance_db),
    });
  }, [settingsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!settingsQuery.data) throw new Error("Configurações ainda não carregadas.");
      return updateAppSettings(
        {
          organization_name: form.organization_name.trim(),
          timezone: form.timezone.trim(),
          default_map_center: [Number(form.longitude), Number(form.latitude)],
          default_map_zoom: Number(form.default_map_zoom),
          excess_loss_tolerance_db: Number(form.excess_loss_tolerance_db),
        },
        settingsQuery.data.version
      );
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["app-settings"], updated);
      setSuccessMessage("Configurações salvas com sucesso.");
    },
  });

  const setField = (field: keyof typeof form, value: string) => {
    setSuccessMessage(null);
    setForm((current) => ({ ...current, [field]: value }));
  };

  return (
    <div className="space-y-8">
      {/* Seção 1: Parâmetros do Provedor e Fuso Horário */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 text-primary">
            <Building2 className="h-5 w-5" />
            <CardTitle className="text-base">Parâmetros Operacionais da Organização</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Configurações de identidade corporativa, fuso horário oficial e tolerâncias de engenharia.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {settingsQuery.isLoading ? (
            <div className="flex items-center gap-2 py-6 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Carregando parâmetros...
            </div>
          ) : settingsQuery.error || !settingsQuery.data ? (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-xs text-destructive">
              <AlertCircle className="h-4 w-4" />
              {settingsQuery.error instanceof ApiError
                ? settingsQuery.error.detail
                : "Não foi possível carregar as configurações."}
            </div>
          ) : (
            <form
              className="space-y-5"
              onSubmit={(event) => {
                event.preventDefault();
                setSuccessMessage(null);
                updateMutation.mutate();
              }}
            >
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="organization-name">Nome da instalação / provedor</Label>
                  <Input id="organization-name" value={form.organization_name} onChange={(event) => setField("organization_name", event.target.value)} maxLength={150} required />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="organization-timezone">Fuso horário IANA</Label>
                  <div className="relative">
                    <Clock className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input id="organization-timezone" value={form.timezone} onChange={(event) => setField("timezone", event.target.value)} className="pl-8" required />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>Centro padrão do mapa (longitude / latitude)</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <Input aria-label="Longitude padrão" type="number" min="-180" max="180" step="0.000001" value={form.longitude} onChange={(event) => setField("longitude", event.target.value)} required />
                    <Input aria-label="Latitude padrão" type="number" min="-90" max="90" step="0.000001" value={form.latitude} onChange={(event) => setField("latitude", event.target.value)} required />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="default-map-zoom">Zoom padrão</Label>
                    <Input id="default-map-zoom" type="number" min="1" max="22" value={form.default_map_zoom} onChange={(event) => setField("default_map_zoom", event.target.value)} required />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="excess-loss">Tolerância de perda (dB)</Label>
                    <Input id="excess-loss" type="number" min="0.1" max="10" step="0.1" value={form.excess_loss_tolerance_db} onChange={(event) => setField("excess_loss_tolerance_db", event.target.value)} required />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 rounded-md bg-muted/40 p-3 text-xs sm:grid-cols-3">
                <div><span className="block text-[11px] text-muted-foreground">Aplicação</span><strong>{settingsQuery.data.app_name}</strong></div>
                <div><span className="block text-[11px] text-muted-foreground">Trace máximo</span><strong className="font-mono">{settingsQuery.data.trace_max_depth} saltos</strong></div>
                <div><span className="block text-[11px] text-muted-foreground">Upload máximo</span><strong>{Math.round(settingsQuery.data.max_upload_size_bytes / 1024 / 1024)} MB</strong></div>
              </div>

              {updateMutation.error && (
                <div className="flex items-center gap-2 text-xs text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {updateMutation.error instanceof ApiError ? updateMutation.error.detail : "Não foi possível salvar as configurações."}
                </div>
              )}
              {successMessage && <p className="text-xs text-emerald-600 dark:text-emerald-400">{successMessage}</p>}

              <div className="flex items-center justify-between border-t border-border pt-4">
                <span className="text-[11px] text-muted-foreground">Versão ETag: v{settingsQuery.data.version}</span>
                <PermissionGate permission="settings:write">
                  <Button type="submit" size="sm" disabled={updateMutation.isPending} className="gap-2">
                    {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Salvar parâmetros
                  </Button>
                </PermissionGate>
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      {/* Seção 2: Normas Industriais de Cores de Fibras */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-primary">
              <Palette className="h-5 w-5" />
              <CardTitle className="text-base">Catálogos de Código de Cores de Fibras e Tubos</CardTitle>
            </div>
            <div className="flex gap-1 bg-muted p-1 rounded-md">
              <button
                type="button"
                onClick={() => setSelectedStandard("NBR")}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  selectedStandard === "NBR"
                    ? "bg-background text-foreground shadow-sm font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                ABNT NBR 14106
              </button>
              <button
                type="button"
                onClick={() => setSelectedStandard("TIA")}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  selectedStandard === "TIA"
                    ? "bg-background text-foreground shadow-sm font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                ANSI/TIA-598-C
              </button>
            </div>
          </div>
          <CardDescription className="text-xs">
            {selectedStandard === "NBR"
              ? "Norma técnica brasileira (ABNT NBR 14106/14771) adotada por fabricantes nacionais de cabos ópticos."
              : "Norma técnica internacional (ANSI/TIA-598-C) amplamente adotada em telecomunicações globais."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {(selectedStandard === "NBR" ? NBR_COLORS : TIA_COLORS).map((c) => (
              <div
                key={c.pos}
                className="flex items-center gap-2 p-2 rounded-lg border bg-card/60 shadow-xs"
              >
                <div
                  className={`h-5 w-5 rounded-full flex-shrink-0 ${c.border ? "border border-gray-300" : ""}`}
                  style={{ backgroundColor: c.hex }}
                />
                <div className="text-xs">
                  <span className="font-semibold block text-[11px]">#{c.pos} {c.name}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Seção 3: Atalhos de Administração e Governança */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2 text-primary">
              <Users className="h-4 w-4" />
              <CardTitle className="text-sm">Gestão de Usuários e RBAC</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Cadastre operadores, defina níveis de permissão e audite contas ativas.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/settings/users">
              <Button variant="outline" size="sm" className="w-full text-xs gap-1.5">
                <span>Gerenciar Usuários</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2 text-primary">
              <History className="h-4 w-4" />
              <CardTitle className="text-sm">Trilha de Auditoria Append-Only</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Consulte histórico cronológico e imutável de mutações de rede e operadores.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/audit">
              <Button variant="outline" size="sm" className="w-full text-xs gap-1.5">
                <span>Consultar Auditoria</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2 text-primary">
              <Layers className="h-4 w-4" />
              <CardTitle className="text-sm">Exportação & Backup</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Exporte camadas georreferenciadas em GeoJSON, KML ou tabelas CSV com LGPD.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/exports">
              <Button variant="outline" size="sm" className="w-full text-xs gap-1.5">
                <span>Exportar Dados</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
