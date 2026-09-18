import * as React from "react";
import type { Metadata } from "next";
import { CustomerDetailView } from "@/features/customers/components/customer-detail-view";

export const metadata: Metadata = {
  title: "Ficha do Assinante | FTTH Manager",
  description: "Dados cadastrais, atendimentos ópticos ativos e histórico do assinante",
};

interface CustomerDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function CustomerDetailPage({ params }: CustomerDetailPageProps) {
  const resolvedParams = await params;
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-6xl">
      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando dados do assinante...
          </div>
        }
      >
        <CustomerDetailView customerId={resolvedParams.id} />
      </React.Suspense>
    </div>
  );
}
