import * as React from "react";
import { DashboardView } from "@/features/reports/components/dashboard-view";
import { LoadingState } from "@/components/ui/state-displays";

export const metadata = {
  title: "Painel Operacional — FTTH Manager",
  description: "Indicadores de infraestrutura de telecomunicações, ocupação óptica e integridade física.",
};

export default function DashboardPage() {
  return (
    <React.Suspense
      fallback={
        <div className="py-12">
          <LoadingState
            message="Carregando painel de controle da rede óptica..."
            size="lg"
          />
        </div>
      }
    >
      <DashboardView />
    </React.Suspense>
  );
}
