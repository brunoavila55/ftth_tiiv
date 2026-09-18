import * as React from "react";
import type { Metadata } from "next";
import { TopologyTraceView } from "@/features/topology/components/topology-trace-view";

export const metadata: Metadata = {
  title: "Rastreamento Óptico & Topologia | FTTH Manager",
  description: "Rastreamento ponta a ponta de caminhos ópticos PON-ONU e ONU-PON",
};

export default function TopologyPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
          Topologia & Rastreamento Óptico
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Diagnóstico de continuidade, perdas acumuladas, ramificações de splitters e detecção de anéis e pontas abertas.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando motor de topologia óptica...
          </div>
        }
      >
        <TopologyTraceView />
      </React.Suspense>
    </div>
  );
}
