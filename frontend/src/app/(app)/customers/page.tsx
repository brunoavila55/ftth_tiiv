import * as React from "react";
import type { Metadata } from "next";
import { CustomersTable } from "@/features/customers/components/customers-table";

export const metadata: Metadata = {
  title: "Assinantes & Clientes | FTTH Manager",
  description: "Gerenciamento de clientes e atendimentos ópticos na rede FTTH",
};

export default function CustomersPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
          Assinantes & Atendimento
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Controle cadastral de clientes, ativação de atendimentos em portas de CTOs e histórico de serviços.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando cadastro de assinantes...
          </div>
        }
      >
        <CustomersTable />
      </React.Suspense>
    </div>
  );
}
