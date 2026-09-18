"use client";

import * as React from "react";
import Link from "next/link";
import { Building2, Box, Cable as CableIcon, ExternalLink, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import type { MapFeature } from "../types";

export interface MapFallbackTableProps {
  features: MapFeature[];
  onSelectFeature?: (feature: MapFeature) => void;
}

export function MapFallbackTable({ features, onSelectFeature }: MapFallbackTableProps) {
  const [searchTerm, setSearchTerm] = React.useState("");

  const filtered = React.useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return features;
    return features.filter(
      (f) =>
        f.properties.code.toLowerCase().includes(q) ||
        f.properties.entity_type.toLowerCase().includes(q) ||
        f.properties.status.toLowerCase().includes(q)
    );
  }, [features, searchTerm]);

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filtrar por código ou tipo..."
            className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-4 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {filtered.length} de {features.length} ativo(s) na região
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-border bg-muted/50 font-medium text-muted-foreground">
            <tr>
              <th className="py-2.5 px-3">Código</th>
              <th className="py-2.5 px-3">Tipo</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Geometria</th>
              <th className="py-2.5 px-3 text-right">Ação</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50 bg-card">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-muted-foreground">
                  Nenhum ativo de rede encontrado para os critérios atuais.
                </td>
              </tr>
            ) : (
              filtered.map((f) => {
                const pointCoords = f.geometry.type === "Point" ? f.geometry.coordinates : null;
                const lineCoords = f.geometry.type === "LineString" ? f.geometry.coordinates : null;
                let Icon = Box;
                let detailUrl = `/poles?q=${encodeURIComponent(f.properties.code)}`;

                if (f.properties.entity_type === "site") {
                  Icon = Building2;
                  detailUrl = `/sites?q=${encodeURIComponent(f.properties.code)}`;
                } else if (
                  f.properties.entity_type === "cable_segment" ||
                  f.properties.entity_type === "cable"
                ) {
                  Icon = CableIcon;
                  detailUrl = `/cables?q=${encodeURIComponent(f.properties.code)}`;
                } else if (f.properties.entity_type === "cto") {
                  detailUrl = `/ctos?q=${encodeURIComponent(f.properties.code)}`;
                }

                return (
                  <tr
                    key={f.id}
                    className="hover:bg-muted/30 cursor-pointer transition-colors"
                    onClick={() => onSelectFeature?.(f)}
                  >
                    <td className="py-2.5 px-3 font-semibold text-foreground flex items-center gap-2">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <span>{f.properties.code}</span>
                    </td>
                    <td className="py-2.5 px-3 uppercase text-[10px] font-mono text-muted-foreground">
                      {f.properties.entity_type}
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge status={f.properties.status} />
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-muted-foreground">
                      {pointCoords
                        ? `${pointCoords[1].toFixed(5)}, ${pointCoords[0].toFixed(5)}`
                        : `${lineCoords?.length ?? 0} vértices`}
                    </td>
                    <td className="py-2.5 px-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs">
                        <Link href={detailUrl} className="gap-1">
                          <span>Ver</span>
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </Button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
