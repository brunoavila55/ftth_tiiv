import * as React from "react";
import { MapView } from "@/features/map/components/map-view";
import { LoadingState } from "@/components/ui/state-displays";

export const metadata = {
  title: "Mapa Operacional — FTTH Manager",
  description: "Visualizador georreferenciado de infraestrutura física, traçado de cabos ópticos e caixas de atendimento.",
};

export default function MapPage() {
  return (
    <div className="flex-1 w-full h-full min-h-0 flex flex-col">
      <React.Suspense
        fallback={
          <div className="flex flex-1 h-full w-full items-center justify-center p-12">
            <LoadingState
              message="Carregando visualizador geográfico..."
              description="Preparando camadas de rede e parâmetros espaciais."
              size="lg"
            />
          </div>
        }
      >
        <MapView />
      </React.Suspense>
    </div>
  );
}
