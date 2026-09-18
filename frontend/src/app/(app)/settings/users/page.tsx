import * as React from "react";
import type { Metadata } from "next";
import { UsersTable } from "@/features/users/components/users-table";

export const metadata: Metadata = {
  title: "Gestão de Usuários e Acessos | FTTH Manager",
  description: "Gerenciamento de operadores, papéis RBAC e controle de credenciais da equipe",
};

export default function UsersSettingsPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight">
          Usuários e Permissões de Acesso
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Administração de contas de operadores, níveis de permissão baseados em papéis (RBAC) e status de acesso.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando usuários…
          </div>
        }
      >
        <UsersTable />
      </React.Suspense>
    </div>
  );
}
