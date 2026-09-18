"use client";

import * as React from "react";
import Link from "next/link";
import {
  Building2,
  Clock,
  Palette,
  Users,
  History,
  ExternalLink,
  Layers,
  Activity,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            <div className="space-y-3">
              <div>
                <span className="text-muted-foreground block text-[11px]">Nome da Instalação / Provedor</span>
                <span className="font-semibold text-foreground text-sm">Operação FTTH Manager</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[11px]">Fuso Horário do Sistema</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="font-medium text-foreground">America/Sao_Paulo (UTC-03:00)</span>
                </div>
              </div>
              <div>
                <span className="text-muted-foreground block text-[11px]">Sistema Geodésico de Referência</span>
                <span className="font-medium text-foreground font-mono">WGS 84 (EPSG:4326) / PostGIS Geography</span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-muted-foreground block text-[11px]">Tolerância para Perda Óptica Excedente</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Activity className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
                  <span className="font-medium text-foreground">± 2.0 dB (Limite de alerta)</span>
                </div>
              </div>
              <div>
                <span className="text-muted-foreground block text-[11px]">Profundidade Máxima de Rastreamento (Trace PON)</span>
                <span className="font-medium text-foreground font-mono">100 saltos / nós</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[11px]">Tamanho Máximo de Upload por Arquivo</span>
                <span className="font-medium text-foreground">10 MB (JPEG, PNG, WebP, PDF)</span>
              </div>
            </div>
          </div>
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
