import * as React from "react";
import type { Metadata } from "next";
import { MeasurementsView } from "@/features/measurements/components/measurements-view";

export const metadata: Metadata = {
  title: "Medições & Potência Óptica | FTTH Manager",
  description: "Histórico de medições manuais e comparativo de perda excedente previsto vs. medido",
};

export default function MeasurementsPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando medições ópticas…
          </div>
        }
      >
        <MeasurementsView />
      </React.Suspense>
    </div>
  );
}
