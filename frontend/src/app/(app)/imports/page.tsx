import * as React from "react";
import type { Metadata } from "next";
import { ImportWizard } from "@/features/imports_exports/components/import-wizard";

export const metadata: Metadata = {
  title: "Assistente de Importação | FTTH Manager",
  description: "Importação com prévia segura e verificação de integridade de dados GeoJSON, KML e CSV",
};

export default function ImportsPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Assistente de Importação de Rede
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Importe dados geoespaciais e cadastrais com validação prévia sem efeitos colaterais e garantia atômica de transação.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando assistente de importação…
          </div>
        }
      >
        <ImportWizard />
      </React.Suspense>
    </div>
  );
}
