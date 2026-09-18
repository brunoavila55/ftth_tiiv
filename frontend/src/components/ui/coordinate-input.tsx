"use client";

import * as React from "react";
import { ArrowLeftRight, MapPin } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { parsePtBrNumber } from "@/lib/format/numbers";
import { cn } from "@/lib/utils";

export interface Coordinates {
  lat: number | null;
  lon: number | null;
}

export interface CoordinateInputProps {
  value?: Coordinates;
  onChange?: (coords: Coordinates) => void;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  error?: string;
}

export function CoordinateInput({
  value = { lat: null, lon: null },
  onChange,
  disabled = false,
  required = false,
  className,
  error: customError,
}: CoordinateInputProps) {
  const [latText, setLatText] = React.useState(value.lat !== null && value.lat !== undefined ? String(value.lat) : "");
  const [lonText, setLonText] = React.useState(value.lon !== null && value.lon !== undefined ? String(value.lon) : "");
  const [validationError, setValidationError] = React.useState<string | null>(null);

  // Sincroniza com valor externo se mudar externamente
  React.useEffect(() => {
    setLatText(value.lat !== null && value.lat !== undefined ? String(value.lat) : "");
    setLonText(value.lon !== null && value.lon !== undefined ? String(value.lon) : "");
  }, [value.lat, value.lon]);

  const updateCoordinates = (newLatStr: string, newLonStr: string) => {
    setValidationError(null);

    let parsedLat: number | null = null;
    let parsedLon: number | null = null;

    try {
      parsedLat = parsePtBrNumber(newLatStr);
    } catch {
      setValidationError("Latitude possui formato numérico inválido");
    }

    try {
      parsedLon = parsePtBrNumber(newLonStr);
    } catch {
      setValidationError("Longitude possui formato numérico inválido");
    }

    if (parsedLat !== null && (parsedLat < -90 || parsedLat > 90)) {
      setValidationError("Latitude deve estar no intervalo entre -90° e +90°");
    }

    if (parsedLon !== null && (parsedLon < -180 || parsedLon > 180)) {
      setValidationError("Longitude deve estar no intervalo entre -180° e +180°");
    }

    onChange?.({ lat: parsedLat, lon: parsedLon });
  };

  // Suporte a colar coordenadas combinadas (ex: "-23.5505, -46.6333")
  const handlePasteCombined = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text");
    if (!text) return;

    // Detecta padrão de par de coordenadas separado por vírgula, ponto-e-vírgula ou espaço
    const match = text.trim().match(/^(-?\d+[.,]?\d*)[,\s;]+(-?\d+[.,]?\d*)$/);
    if (match) {
      e.preventDefault();
      const first = match[1];
      const second = match[2];

      setLatText(first);
      setLonText(second);
      updateCoordinates(first, second);
    }
  };

  const handleSwap = () => {
    const prevLat = latText;
    const prevLon = lonText;
    setLatText(prevLon);
    setLonText(prevLat);
    updateCoordinates(prevLon, prevLat);
  };

  const currentError = customError || validationError;

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
          <MapPin className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          <span>Coordenadas Geográficas (WGS-84)</span>
          {required && <span className="text-destructive">*</span>}
        </span>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleSwap}
          disabled={disabled || (!latText && !lonText)}
          className="h-6 px-2 text-[11px] text-muted-foreground hover:text-foreground gap-1"
          title="Inverter Latitude e Longitude"
        >
          <ArrowLeftRight className="h-3 w-3" />
          <span>Inverter</span>
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label htmlFor="coord-latitude" className="text-[11px] text-muted-foreground font-normal">
            Latitude (-90° a +90°)
          </Label>
          <Input
            id="coord-latitude"
            placeholder="-23.550520"
            value={latText}
            onChange={(e) => {
              setLatText(e.target.value);
              updateCoordinates(e.target.value, lonText);
            }}
            onPaste={handlePasteCombined}
            disabled={disabled}
            className={cn("text-xs font-mono", currentError && "border-destructive")}
            autoComplete="off"
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="coord-longitude" className="text-[11px] text-muted-foreground font-normal">
            Longitude (-180° a +180°)
          </Label>
          <Input
            id="coord-longitude"
            placeholder="-46.633308"
            value={lonText}
            onChange={(e) => {
              setLonText(e.target.value);
              updateCoordinates(latText, e.target.value);
            }}
            onPaste={handlePasteCombined}
            disabled={disabled}
            className={cn("text-xs font-mono", currentError && "border-destructive")}
            autoComplete="off"
          />
        </div>
      </div>

      {currentError ? (
        <p className="text-xs text-destructive font-medium animate-in fade-in-0">
          {currentError}
        </p>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          Cole coordenadas no formato &ldquo;-23.5505, -46.6333&rdquo; em qualquer campo para autopreenchimento.
        </p>
      )}
    </div>
  );
}
