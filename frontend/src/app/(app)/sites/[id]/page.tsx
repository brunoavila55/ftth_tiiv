import * as React from "react";
import type { Metadata } from "next";
import { SiteDetailView } from "@/features/inventory/components/site-detail-view";

export const metadata: Metadata = {
  title: "Detalhes do Site | FTTH Manager",
  description: "Ficha técnica e equipamentos do local técnico",
};

interface SitePageProps {
  params: Promise<{ id: string }>;
}

export default async function SiteDetailPage({ params }: SitePageProps) {
  const resolvedParams = await params;
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-6xl">
      <React.Suspense fallback={<div className="p-8 text-center text-xs text-muted-foreground">Carregando dados do site...</div>}>
        <SiteDetailView siteId={resolvedParams.id} />
      </React.Suspense>
    </div>
  );
}
