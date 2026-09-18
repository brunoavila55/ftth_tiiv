import * as React from "react";
import type { Metadata } from "next";
import { StructuresTable } from "@/features/inventory/components/structures-table";

export const metadata: Metadata = {
  title: "Postes & Ancoragens | FTTH Manager",
  description: "Catálogo georreferenciado de postes e estruturas de sustentação aérea",
};

export default function PolesPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
          Postes & Ancoragens
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Gerenciamento e localização física de postes da rede aérea e estruturas de suporte.
        </p>
      </div>

      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando catálogo de postes...</div>}>
        <StructuresTable fixedKind="pole" title="Postes" />
      </React.Suspense>
    </div>
  );
}
