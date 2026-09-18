import * as React from "react";
import type { Metadata } from "next";
import { StructuresTable } from "@/features/inventory/components/structures-table";

export const metadata: Metadata = {
  title: "Caixas de Terminação (CTO) | FTTH Manager",
  description: "Caixas de atendimento, portas ópticas de cliente e splitters de terminação",
};

export default function CtosPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
          Caixas de Terminação Óptica (CTO)
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Gerenciamento de caixas de atendimento ao assinante, splitters e portas ativas.
        </p>
      </div>

      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando catálogo de CTOs...</div>}>
        <StructuresTable fixedKind="cto" title="Caixas CTO" />
      </React.Suspense>
    </div>
  );
}
