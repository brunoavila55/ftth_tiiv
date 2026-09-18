import * as React from "react";
import { SitesTable } from "@/features/inventory/components/sites-table";
import { LoadingState } from "@/components/ui/state-displays";
import { Building2 } from "lucide-react";

export default function SitesPage() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Building2 className="h-4 w-4" aria-hidden="true" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            POPs & Sites de Rede
          </h1>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Gestão de estações de telecomunicações, centrais telefônicas, data centers e armários de distribuição física.
        </p>
      </div>

      <React.Suspense fallback={<LoadingState message="Carregando inventário de sites..." />}>
        <SitesTable />
      </React.Suspense>
    </div>
  );
}
