"use client";

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Copy, Check, Map, Navigation, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CopyableCoordinatesProps {
  latitude: number;
  longitude: number;
  entityId?: string;
  mapHref?: string;
  showExternalNavigation?: boolean;
  className?: string;
}

export function CopyableCoordinates({
  latitude,
  longitude,
  entityId,
  mapHref,
  showExternalNavigation = true,
  className,
}: CopyableCoordinatesProps) {
  const [copied, setCopied] = React.useState(false);

  const formattedLat = latitude.toFixed(6);
  const formattedLon = longitude.toFixed(6);
  const coordString = `${formattedLat}, ${formattedLon}`;

  const handleCopy = async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(coordString);
      } else {
        // Fallback para navegadores ou contextos sem clipboard API direta
        const textarea = document.createElement("textarea");
        textarea.value = coordString;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Ignora falha de clipboard silenciosamente
    }
  };

  const resolvedMapHref =
    mapHref ||
    `/map?lat=${latitude}&lng=${longitude}&zoom=17${entityId ? `&selected=${entityId}` : ""}`;

  const externalGpsUrl = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-3.5 space-y-3 shadow-sm",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5">
        <div>
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            Coordenadas Geográficas (WGS84)
          </span>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="font-mono text-sm font-bold text-foreground">
              Lat: {formattedLat} | Lon: {formattedLon}
            </span>
          </div>
        </div>

        {/* Botão de Copiar */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleCopy}
          className="min-h-[38px] sm:min-h-[32px] px-3 text-xs gap-1.5 shrink-0"
          aria-label={copied ? "Coordenadas copiadas" : "Copiar latitude e longitude"}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />
              <span className="text-emerald-600 font-medium">Copiado!</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
              <span>Copiar Coordenadas</span>
            </>
          )}
        </Button>

        {/* Anúncio Acessível de Leitor de Tela */}
        <span className="sr-only" role="status" aria-live="polite">
          {copied ? `Coordenadas ${coordString} copiadas para a área de transferência.` : ""}
        </span>
      </div>

      {/* Ações de Navegação e Mapa de Campo */}
      <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border/60">
        <Button asChild variant="secondary" size="sm" className="min-h-[36px] text-xs gap-1.5">
          <Link href={resolvedMapHref}>
            <Map className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
            <span>Abrir no Mapa Operacional</span>
          </Link>
        </Button>

        {showExternalNavigation && (
          <Button
            asChild
            variant="ghost"
            size="sm"
            className="min-h-[36px] text-xs gap-1.5 text-muted-foreground hover:text-foreground"
          >
            <a
              href={externalGpsUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Abrir rota no Google Maps para navegação de campo"
            >
              <Navigation className="h-3.5 w-3.5 text-blue-500" aria-hidden="true" />
              <span>Navegar GPS (Campo)</span>
              <ExternalLink className="h-3 w-3 opacity-60 ml-0.5" aria-hidden="true" />
            </a>
          </Button>
        )}
      </div>
    </div>
  );
}
