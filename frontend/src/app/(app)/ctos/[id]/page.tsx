import * as React from "react";
import type { Metadata } from "next";
import { StructureDetailView } from "@/features/inventory/components/structure-detail-view";

export const metadata: Metadata = {
  title: "Detalhes da Caixa CTO | FTTH Manager",
  description: "Ficha técnica, portas de atendimento e status da caixa de terminação",
};

interface CtoPageProps {
  params: Promise<{ id: string }>;
}

export default async function CtoDetailPage({ params }: CtoPageProps) {
  const resolvedParams = await params;
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-6xl">
      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando dados da CTO...</div>}>
        <StructureDetailView structureId={resolvedParams.id} kindOverride="cto" />
      </React.Suspense>
    </div>
  );
}
