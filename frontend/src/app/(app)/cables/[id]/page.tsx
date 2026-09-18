import * as React from "react";
import type { Metadata } from "next";
import { CableDetailView } from "@/features/cables/components/cable-detail-view";

export const metadata: Metadata = {
  title: "Detalhes do Cabo Óptico | FTTH Manager",
  description: "Ficha técnica, segmentos, tubos e fibras do cabo óptico",
};

interface CableDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function CableDetailPage({ params }: CableDetailPageProps) {
  const resolvedParams = await params;
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-6xl">
      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando dados do cabo óptico...</div>}>
        <CableDetailView cableId={resolvedParams.id} />
      </React.Suspense>
    </div>
  );
}
