import * as React from "react";
import type { Metadata } from "next";
import { CablesTable } from "@/features/cables/components/cables-table";

export const metadata: Metadata = {
  title: "Cabos Ópticos | FTTH Manager",
  description: "Catálogo de cabos ópticos, tubos loose e fibras da rede FTTH",
};

export default function CablesPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
          Cabos Ópticos & Rotas
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Gerenciamento de cabos troncais, de distribuição e atendimento com identificação de tubos e fibras.
        </p>
      </div>

      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando catálogo de cabos...</div>}>
        <CablesTable />
      </React.Suspense>
    </div>
  );
}
