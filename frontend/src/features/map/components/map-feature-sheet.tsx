"use client";

import * as React from "react";
import Link from "next/link";
import {
  X,
  Building2,
  Box,
  Cable as CableIcon,
  ExternalLink,
  Copy,
  Check,
  MapPin,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import type { MapFeature } from "../types";

export interface MapFeatureSheetProps {
  feature: MapFeature | null;
  onClose: () => void;
}

export function MapFeatureSheet({ feature, onClose }: MapFeatureSheetProps) {
  const [copied, setCopied] = React.useState(false);

  if (!feature) return null;

  const { properties, geometry } = feature;
  const isPoint = geometry.type === "Point";
  const extra = properties.extra ?? {};
  const entityKind =
    properties.entity_type === "structure" && typeof extra.kind === "string"
      ? extra.kind.toLowerCase()
      : properties.entity_type.toLowerCase();

  let detailUrl = "/sites";
  let typeLabel = "Elemento";
  let IconComponent = Box;

  if (entityKind === "site") {
    typeLabel = "POP / Site Central";
    IconComponent = Building2;
    detailUrl = `/sites/${properties.entity_id}`;
  } else if (entityKind === "cable_segment" || entityKind === "cable") {
    typeLabel = "Cabo Óptico";
    IconComponent = CableIcon;
    detailUrl =
      typeof extra.cable_id === "string"
        ? `/cables/${extra.cable_id}`
        : `/cables?q=${encodeURIComponent(properties.code)}`;
  } else if (entityKind === "cto") {
    typeLabel = "Caixa de Terminação (CTO)";
    IconComponent = Box;
    detailUrl = `/ctos/${properties.entity_id}`;
  } else if (entityKind === "ceo") {
    typeLabel = "Caixa de Emenda (CEO)";
    IconComponent = Box;
    detailUrl = `/ceos/${properties.entity_id}`;
  } else if (entityKind === "pole") {
    typeLabel = "Poste";
    IconComponent = Box;
    detailUrl = `/poles/${properties.entity_id}`;
  } else {
    typeLabel = "Estrutura Física";
    IconComponent = Box;
    detailUrl = `/structures/${properties.entity_id}`;
  }

  const visibleExtraEntries = Object.entries(extra).filter(
    ([key, value]) => value != null && !["kind", "site_id", "cable_id"].includes(key)
  );
  const extraLabels: Record<string, string> = {
    capacity: "Capacidade",
    condition: "Condição",
    model: "Modelo",
    fiber_count: "Fibras",
    tube_count: "Tubos",
    origin_code: "Origem",
    destination_code: "Destino",
    map_length_m: "Comprimento no mapa",
    measured_length_m: "Comprimento medido",
    slack_length_m: "Reserva técnica",
    effective_length_m: "Comprimento efetivo",
    length_source: "Fonte do comprimento",
    name: "Nome",
    address: "Endereço",
  };
  const formatExtraValue = (key: string, value: unknown) => {
    if (key.endsWith("_length_m") && typeof value === "number") {
      return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} m`;
    }
    if (key === "length_source") {
      return value === "measured" ? "Medição de campo" : "Calculado pelo mapa";
    }
    return String(value);
  };

  const coordsText = isPoint
    ? `${geometry.coordinates[1].toFixed(6)}, ${geometry.coordinates[0].toFixed(6)}`
    : `${geometry.coordinates.length} vértices georreferenciados`;

  const copyCoords = async () => {
    if (isPoint) {
      await navigator.clipboard.writeText(coordsText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div
      role="complementary"
      aria-label="Painel contextual do elemento selecionado"
      className="absolute top-4 right-4 left-4 z-20 max-h-[calc(100%-2rem)] w-auto overflow-y-auto rounded-xl border border-border bg-card/95 p-5 shadow-2xl backdrop-blur-md transition-all animate-in slide-in-from-right-4 sm:left-auto sm:w-96"
    >
      {/* Cabeçalho */}
      <div className="flex items-start justify-between gap-3 border-b border-border pb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <IconComponent className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h3 className="font-bold text-foreground text-sm truncate">
              {properties.code}
            </h3>
            <p className="text-xs text-muted-foreground">{typeLabel}</p>
          </div>
        </div>

        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 rounded-full hover:bg-muted"
          onClick={onClose}
          aria-label="Fechar detalhes"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Propriedades */}
      <div className="mt-4 space-y-3.5 text-xs">
        {/* Status e Versão */}
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Estado operacional:</span>
          <StatusBadge status={properties.status} />
        </div>

        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Versão de concorrência:</span>
          <Badge variant="outline" className="font-mono text-[10px] py-0">
            v{properties.version}
          </Badge>
        </div>

        {/* Coordenadas / Geometria */}
        <div className="rounded-lg border border-border bg-muted/40 p-2.5">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5 text-primary" />
              <span>{isPoint ? "Coordenadas (WGS-84)" : "Traçado do Cabo"}</span>
            </span>
            {isPoint && (
              <button
                type="button"
                onClick={copyCoords}
                className="text-primary hover:underline flex items-center gap-1 text-[11px]"
                aria-label="Copiar coordenadas"
              >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                <span>{copied ? "Copiado" : "Copiar"}</span>
              </button>
            )}
          </div>
          <p className="font-mono text-foreground text-[11px] select-all truncate">
            {coordsText}
          </p>
        </div>

        {/* Ocupação (para CTOs) */}
        {properties.occupancy && (
          <div className="space-y-1.5 pt-1">
            <span className="text-muted-foreground font-medium">Ocupação de Portas:</span>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded border border-emerald-500/20 bg-emerald-500/5 p-1.5">
                <p className="font-bold text-emerald-600 dark:text-emerald-400">
                  {properties.occupancy.free ?? 0}
                </p>
                <p className="text-[10px] text-muted-foreground">Livres</p>
              </div>
              <div className="rounded border border-amber-500/20 bg-amber-500/5 p-1.5">
                <p className="font-bold text-amber-600 dark:text-amber-400">
                  {properties.occupancy.reserved ?? 0}
                </p>
                <p className="text-[10px] text-muted-foreground">Reservadas</p>
              </div>
              <div className="rounded border border-blue-500/20 bg-blue-500/5 p-1.5">
                <p className="font-bold text-blue-600 dark:text-blue-400">
                  {properties.occupancy.connected ?? 0}
                </p>
                <p className="text-[10px] text-muted-foreground">Conectadas</p>
              </div>
            </div>
          </div>
        )}

        {/* Informações adicionais da camada */}
        {visibleExtraEntries.length > 0 && (
          <div className="space-y-1 pt-1 border-t border-border">
            {visibleExtraEntries.map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-[11px]">
                <span className="text-muted-foreground">{extraLabels[k] ?? k.replace(/_/g, " ")}:</span>
                <span className="max-w-[55%] truncate text-right font-medium text-foreground">
                  {formatExtraValue(k, v)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ações */}
      <div className="mt-5 pt-3 border-t border-border flex items-center gap-2">
        <Button asChild size="sm" className="w-full gap-1.5 text-xs">
          <Link href={detailUrl}>
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Abrir Cadastro Completo</span>
          </Link>
        </Button>
      </div>
    </div>
  );
}
