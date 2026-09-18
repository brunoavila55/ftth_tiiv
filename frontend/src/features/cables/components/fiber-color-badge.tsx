"use client";

import * as React from "react";
import {
  getColorForPosition,
  getFiberHierarchy,
  type ColorDef,
} from "@/features/cables/utils/colors";
import { cn } from "@/lib/utils";

export interface FiberColorBadgeProps {
  fiberNumber: number;
  standard?: "NBR" | "TIA-598" | string;
  totalFibers?: number;
  totalTubes?: number;
  showTube?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

/**
 * Componente acessível para identificação de fibras ópticas por técnicos em campo.
 * Atende às diretrizes de daltonismo (WCAG 2.2 AA) ao SEMPRE associar o número
 * ordinal e o nome da cor por extenso ao swatch visual.
 */
export function FiberColorBadge({
  fiberNumber,
  standard = "NBR",
  totalFibers,
  totalTubes,
  showTube = false,
  size = "md",
  className,
}: FiberColorBadgeProps) {
  let fiberColor: ColorDef;
  let tubeNumber: number | undefined;
  let tubeColor: ColorDef | undefined;
  let fiberPositionInTube: number | undefined;

  if (totalFibers && totalTubes) {
    const hierarchy = getFiberHierarchy(fiberNumber, totalFibers, totalTubes, standard);
    fiberColor = hierarchy.fiberColor;
    tubeNumber = hierarchy.tubeNumber;
    tubeColor = hierarchy.tubeColor;
    fiberPositionInTube = hierarchy.fiberPositionInTube;
  } else {
    fiberColor = getColorForPosition(fiberNumber, standard);
  }

  const ariaLabel = showTube && tubeNumber && tubeColor
    ? `Fibra #${fiberNumber} (${fiberColor.name}${fiberPositionInTube ? `, pos ${fiberPositionInTube}` : ""}), Tubo #${tubeNumber} (${tubeColor.name}), Norma ${standard}`
    : `Fibra #${fiberNumber}, Cor ${fiberColor.name}, Norma ${standard}`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-border bg-background font-mono transition-colors",
        size === "sm" && "px-1.5 py-0.5 text-[10px]",
        size === "md" && "px-2 py-1 text-xs",
        size === "lg" && "px-2.5 py-1.5 text-sm",
        className
      )}
      title={ariaLabel}
      aria-label={ariaLabel}
    >
      {/* Swatch visual com borda de alto contraste */}
      <span
        className={cn(
          "rounded-full border shrink-0 shadow-sm",
          size === "sm" && "h-2.5 w-2.5",
          size === "md" && "h-3 w-3",
          size === "lg" && "h-3.5 w-3.5"
        )}
        style={{
          backgroundColor: fiberColor.hex,
          borderColor: fiberColor.border || fiberColor.hex,
        }}
        aria-hidden="true"
      />

      {/* Número da Fibra */}
      <span className="font-bold text-foreground">
        FO #{fiberNumber}
      </span>

      {/* Nome da cor por extenso (Daltonismo) */}
      <span className="text-muted-foreground font-medium">
        ({fiberColor.name})
      </span>

      {/* Identificação de Tubo se requisitada */}
      {showTube && tubeNumber && tubeColor && (
        <span className="text-muted-foreground/80 text-[10px] ml-1 pl-1 border-l border-border">
          Tubo {tubeNumber} ({tubeColor.name})
        </span>
      )}
    </span>
  );
}
