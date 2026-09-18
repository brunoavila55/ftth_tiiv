import * as React from "react";
import type { Metadata } from "next";
import { StructureDetailView } from "@/features/inventory/components/structure-detail-view";

export const metadata: Metadata = {
  title: "Detalhes do Poste | FTTH Manager",
  description: "Ficha técnica e ancoragens do poste",
};

interface PolePageProps {
  params: Promise<{ id: string }>;
}

export default async function PoleDetailPage({ params }: PolePageProps) {
  const resolvedParams = await params;
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-6xl">
      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando dados do poste...</div>}>
        <StructureDetailView structureId={resolvedParams.id} kindOverride="pole" />
      </React.Suspense>
    </div>
  );
}
