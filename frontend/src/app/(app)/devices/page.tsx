import * as React from "react";
import type { Metadata } from "next";
import { DevicesTable } from "@/features/inventory/components/devices-table";

export const metadata: Metadata = {
  title: "Dispositivos & OLTs | FTTH Manager",
  description: "Equipamentos ativos e passivos: OLTs, DIOs, switches e roteadores",
};

export default function DevicesPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
          Dispositivos & OLTs
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Catálogo e alocação física de terminais de linha, distribuidores ópticos e equipamentos ativos.
        </p>
      </div>

      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando catálogo de dispositivos...</div>}>
        <DevicesTable />
      </React.Suspense>
    </div>
  );
}
