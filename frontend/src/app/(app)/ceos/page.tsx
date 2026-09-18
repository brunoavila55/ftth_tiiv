import * as React from "react";
import type { Metadata } from "next";
import { StructuresTable } from "@/features/inventory/components/structures-table";

export const metadata: Metadata = {
  title: "Caixas de Emenda (CEO) | FTTH Manager",
  description: "Caixas de emenda óptica, bandejas de fusão e continuidade de cabos",
};

export default function CeosPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
          Caixas de Emenda Óptica (CEO)
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Gestão de caixas de emenda, bandejas de fusão e sangrias da rede troncal e de distribuição.
        </p>
      </div>

      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando catálogo de CEOs...</div>}>
        <StructuresTable fixedKind="ceo" title="Caixas CEO" />
      </React.Suspense>
    </div>
  );
}
