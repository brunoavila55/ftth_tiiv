"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { RadioTower } from "lucide-react";
import { SitesTable } from "@/features/inventory/components/sites-table";
import { DevicesTable } from "@/features/inventory/components/devices-table";
import { RadioLinksPanel } from "@/features/wireless/components/radio-links-panel";
import { LoadingState } from "@/components/ui/state-displays";

function WirelessContent() {
  const searchParams = useSearchParams();
  const requestedType = searchParams.get("type");
  const type = requestedType === "towers" || requestedType === "radios" || requestedType === "links" ? requestedType : "pops";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <RadioTower className="h-4 w-4" aria-hidden="true" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">Wireless</h1>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Inventário de POPs, torres, rádios e enlaces entre pontos wireless.
        </p>
      </div>

      <nav aria-label="Tipos de pontos wireless" className="flex gap-2 border-b border-border">
        <Link
          href="/wireless?type=pops"
          aria-current={type === "pops" ? "page" : undefined}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${type === "pops" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          POPs Wireless
        </Link>
        <Link
          href="/wireless?type=towers"
          aria-current={type === "towers" ? "page" : undefined}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${type === "towers" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          Torres de Rádio
        </Link>
        <Link
          href="/wireless?type=radios"
          aria-current={type === "radios" ? "page" : undefined}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${type === "radios" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          Rádios
        </Link>
        <Link
          href="/wireless?type=links"
          aria-current={type === "links" ? "page" : undefined}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${type === "links" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          Enlaces
        </Link>
      </nav>

      {type === "radios"
        ? <DevicesTable key={type} fixedKind="radio" />
        : type === "links"
          ? <RadioLinksPanel key={type} />
          : <SitesTable key={type} fixedKind={type === "towers" ? "radio_tower" : "wireless_pop"} />}
    </div>
  );
}

export default function WirelessPage() {
  return (
    <React.Suspense fallback={<LoadingState message="Carregando inventário wireless..." />}>
      <WirelessContent />
    </React.Suspense>
  );
}
