import * as React from "react";
import { WirelessMapView } from "@/features/wireless/components/wireless-map-view";
import { LoadingState } from "@/components/ui/state-displays";

export const metadata = {
  title: "Mapa Wireless — FTTH Manager",
  description: "Mapa de POPs, torres e enlaces de rádio separado da rede de fibra.",
};

export default function WirelessMapPage() {
  return (
    <React.Suspense fallback={<LoadingState message="Carregando mapa wireless..." />}>
      <WirelessMapView />
    </React.Suspense>
  );
}
