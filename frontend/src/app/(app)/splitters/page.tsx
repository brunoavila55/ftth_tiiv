import * as React from "react";
import type { Metadata } from "next";
import { SplittersCatalog } from "@/features/splitters/components/splitters-catalog";

export const metadata: Metadata = {
  title: "Splitters Ópticos | FTTH Manager",
  description: "Catálogo e gestão dos divisores ópticos instalados na rede FTTH",
};

export default function SplittersPage() {
  return (
    <div className="container mx-auto max-w-7xl space-y-4 px-4 py-4 sm:py-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
          Splitters Ópticos
        </h1>
        <p className="text-xs text-muted-foreground sm:text-sm">
          Catálogo global de divisores, alojamentos, razões ópticas e perdas por saída.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando catálogo de splitters...
          </div>
        }
      >
        <SplittersCatalog />
      </React.Suspense>
    </div>
  );
}
