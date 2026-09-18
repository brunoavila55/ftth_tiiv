import * as React from "react";
import type { Metadata } from "next";
import { SimulationsView } from "@/features/simulations/components/simulations-view";

export const metadata: Metadata = {
  title: "Simulações de Engenharia | FTTH Manager",
  description: "Simulador de cenários hipotéticos ópticos com overrides e análise preditiva de rompimento de cabos",
};

export default function SimulationsPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando simulador de engenharia…
          </div>
        }
      >
        <SimulationsView />
      </React.Suspense>
    </div>
  );
}
