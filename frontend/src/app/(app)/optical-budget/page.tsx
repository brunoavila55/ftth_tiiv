import * as React from "react";
import type { Metadata } from "next";
import { OpticalBudgetView } from "@/features/optical/components/optical-budget-view";

export const metadata: Metadata = {
  title: "Orçamento Óptico e Balanço de Potência | FTTH Manager",
  description: "Cálculo determinístico de atenuação acumulada, sensibilidade RX e margem de projeto",
};

export default function OpticalBudgetPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando motor de cálculo óptico…
          </div>
        }
      >
        <OpticalBudgetView />
      </React.Suspense>
    </div>
  );
}
