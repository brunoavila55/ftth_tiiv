"use client";

import * as React from "react";
import { ChevronDown, ChevronUp, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { LayerFilters } from "../types";

export interface MapLegendProps {
  layers: LayerFilters;
  onToggleLayer: (layerKey: keyof LayerFilters) => void;
}

export function MapLegend({ layers, onToggleLayer }: MapLegendProps) {
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <div className="absolute bottom-6 left-4 z-20 w-64 rounded-xl border border-border bg-card/95 p-3.5 shadow-lg backdrop-blur-md transition-all text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-semibold text-foreground">
          <Layers className="h-4 w-4 text-primary" aria-hidden="true" />
          <span>Camadas & Legenda</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 hover:bg-muted"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expandir legenda" : "Recolher legenda"}
        >
          {collapsed ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>

      {!collapsed && (
        <div className="mt-3 space-y-2.5 divide-y divide-border/40">
          <div className="space-y-2 pt-1">
            {/* Sites / POPs */}
            <label className="flex items-center justify-between gap-2 cursor-pointer select-none">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-sky-600 border border-white shadow-sm" />
                <span className="text-foreground">POP / Site Central</span>
              </div>
              <input
                type="checkbox"
                checked={layers.sites}
                onChange={() => onToggleLayer("sites")}
                className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer"
                aria-label="Alternar exibição de Sites"
              />
            </label>

            {/* CTOs */}
            <label className="flex items-center justify-between gap-2 cursor-pointer select-none">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-amber-500 border border-white shadow-sm" />
                <span className="text-foreground">CTO (Terminação)</span>
              </div>
              <input
                type="checkbox"
                checked={layers.ctos}
                onChange={() => onToggleLayer("ctos")}
                className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer"
                aria-label="Alternar exibição de CTOs"
              />
            </label>

            {/* CEOs, postes e demais estruturas compartilham o filtro, mas não a cor. */}
            <label className="flex items-center justify-between gap-2 cursor-pointer select-none">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-violet-500 border border-white shadow-sm" />
                  <span className="text-foreground">CEO (Emenda)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-slate-500 border border-white shadow-sm" />
                  <span className="text-foreground">Poste / Estruturas</span>
                </div>
              </div>
              <input
                type="checkbox"
                checked={layers.structures}
                onChange={() => onToggleLayer("structures")}
                className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer"
                aria-label="Alternar exibição de CEOs, estruturas e postes"
              />
            </label>

            {/* Cabos Ópticos */}
            <label className="flex items-center justify-between gap-2 cursor-pointer select-none">
              <div className="flex items-center gap-2">
                <span className="h-1 w-3.5 rounded-full bg-indigo-600 shadow-sm" />
                <span className="text-foreground">Cabo Óptico</span>
              </div>
              <input
                type="checkbox"
                checked={layers.cables}
                onChange={() => onToggleLayer("cables")}
                className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer"
                aria-label="Alternar exibição de Cabos"
              />
            </label>
          </div>

          {/* Dica técnica */}
          <div className="pt-2 text-[10px] text-muted-foreground">
            Clique em qualquer elemento do mapa para inspecionar parâmetros e detalhes de conectividade.
          </div>
        </div>
      )}
    </div>
  );
}
