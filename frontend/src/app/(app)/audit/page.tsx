import * as React from "react";
import type { Metadata } from "next";
import { AuditView } from "@/features/audit/components/audit-view";

export const metadata: Metadata = {
  title: "Trilha de Auditoria | FTTH Manager",
  description: "Histórico imutável de eventos operacionais e alterações cadastrais da rede FTTH",
};

export default function AuditPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando trilha de auditoria…
          </div>
        }
      >
        <AuditView />
      </React.Suspense>
    </div>
  );
}
