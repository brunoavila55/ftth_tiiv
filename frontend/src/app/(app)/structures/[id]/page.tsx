import * as React from "react";
import type { Metadata } from "next";
import { StructureDetailView } from "@/features/inventory/components/structure-detail-view";

export const metadata: Metadata = {
  title: "Detalhes da Estrutura | FTTH Manager",
  description: "Ficha técnica e conectividade da estrutura física",
};

interface StructurePageProps {
  params: Promise<{ id: string }>;
}

export default async function StructureDetailPage({ params }: StructurePageProps) {
  const resolvedParams = await params;
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-6xl">
      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando dados da estrutura...</div>}>
        <StructureDetailView structureId={resolvedParams.id} />
      </React.Suspense>
    </div>
  );
}
