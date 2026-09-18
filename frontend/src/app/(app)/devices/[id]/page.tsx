import * as React from "react";
import type { Metadata } from "next";
import { DeviceDetailView } from "@/features/inventory/components/device-detail-view";

export const metadata: Metadata = {
  title: "Detalhes do Dispositivo | FTTH Manager",
  description: "Ficha técnica, portas ópticas e localização do equipamento",
};

interface DevicePageProps {
  params: Promise<{ id: string }>;
}

export default async function DeviceDetailPage({ params }: DevicePageProps) {
  const resolvedParams = await params;
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-6xl">
      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando dados do equipamento...</div>}>
        <DeviceDetailView deviceId={resolvedParams.id} />
      </React.Suspense>
    </div>
  );
}
