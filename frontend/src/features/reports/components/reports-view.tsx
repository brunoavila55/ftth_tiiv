"use client";

import * as React from "react";
import { Box, Cable as CableIcon, AlertTriangle } from "lucide-react";
import type { ReportTab } from "@/features/reports/types";
import { CTOOccupancyTab } from "./cto-occupancy-tab";
import { CableCapacityTab } from "./cable-capacity-tab";
import { InconsistenciesTab } from "./inconsistencies-tab";
import { cn } from "@/lib/utils";

export function ReportsView() {
  const [activeTab, setActiveTab] = React.useState<ReportTab>("ctos");

  const tabs: { id: ReportTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: "ctos", label: "Ocupação de CTOs", icon: Box },
    { id: "cables", label: "Capacidade de Cabos", icon: CableIcon },
    { id: "inconsistencies", label: "Inconsistências Técnicas", icon: AlertTriangle },
  ];

  return (
    <div className="space-y-6">
      {/* Navegação por Abas */}
      <div className="flex border-b border-border bg-card rounded-t-lg px-2 pt-2 gap-2 overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap",
                isActive
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Conteúdo da Aba Ativa */}
      <div>
        {activeTab === "ctos" && <CTOOccupancyTab />}
        {activeTab === "cables" && <CableCapacityTab />}
        {activeTab === "inconsistencies" && <InconsistenciesTab />}
      </div>
    </div>
  );
}
