import * as React from "react";
import type { Metadata } from "next";
import { ExportWizard } from "@/features/imports_exports/components/export-wizard";

export const metadata: Metadata = {
  title: "Exportação de Dados | FTTH Manager",
  description: "Exportação assíncrona de camadas físicas e dados de rede em GeoJSON, KML e CSV com proteção LGPD",
};

export default function ExportsPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Exportação de Dados da Rede
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Exporte camadas geoespaciais e cadastrais da infraestrutura óptica com processamento assíncrono e segurança LGPD.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando assistente de exportação…
          </div>
        }
      >
        <ExportWizard />
      </React.Suspense>
    </div>
  );
}
