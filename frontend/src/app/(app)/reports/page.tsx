import * as React from "react";
import type { Metadata } from "next";
import { ReportsView } from "@/features/reports/components/reports-view";

export const metadata: Metadata = {
  title: "Relatórios de Capacidade | FTTH Manager",
  description: "Indicadores de ocupação de CTOs, balanço de fibras em cabos e diagnóstico de anomalias técnicas",
};

export default function ReportsPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight">
          Relatórios e Capacidade da Rede
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Análise de ocupação de caixas CTO, inventário de fibras ópticas e auditoria de conformidade técnica.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando relatórios operacionais…
          </div>
        }
      >
        <ReportsView />
      </React.Suspense>
    </div>
  );
}
