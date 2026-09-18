"use client";

import * as React from "react";
import { Filter, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuditTimeline } from "./audit-timeline";

export function AuditView() {
  const [selectedType, setSelectedType] = React.useState<string>("all");
  const [actionQuery, setActionQuery] = React.useState<string>("");
  const [activeFilters, setActiveFilters] = React.useState<{
    entity_type?: string;
    action?: string;
  }>({});

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    setActiveFilters({
      entity_type: selectedType !== "all" ? selectedType : undefined,
      action: actionQuery.trim() || undefined,
    });
  };

  const handleResetFilters = () => {
    setSelectedType("all");
    setActionQuery("");
    setActiveFilters({});
  };

  return (
    <div className="space-y-6">
      {/* Barra de Filtros */}
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <form onSubmit={handleApplyFilters} className="flex flex-col sm:flex-row gap-4 items-end">
          <div className="w-full sm:w-64 space-y-1.5">
            <Label htmlFor="audit-type-filter" className="text-xs">
              Tipo de Entidade
            </Label>
            <select
              id="audit-type-filter"
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="all">Todas as entidades</option>
              <option value="site">Sites e POPs</option>
              <option value="structure">Estruturas (Caixas / Postes)</option>
              <option value="cable">Cabos Ópticos</option>
              <option value="connection">Conexões / Fusões</option>
              <option value="customer">Clientes</option>
              <option value="service_link">Atendimentos</option>
              <option value="attachment">Anexos e Fotos</option>
              <option value="optical_measurement">Medições de Potência</option>
              <option value="user">Usuários do Sistema</option>
            </select>
          </div>

          <div className="w-full sm:w-64 space-y-1.5">
            <Label htmlFor="audit-action-filter" className="text-xs">
              Ação
            </Label>
            <Input
              id="audit-action-filter"
              placeholder="Ex: CREATE, DELETE, FUSION..."
              value={actionQuery}
              onChange={(e) => setActionQuery(e.target.value)}
              className="h-9 text-xs"
            />
          </div>

          <div className="flex gap-2 w-full sm:w-auto">
            <Button type="submit" size="sm" className="h-9 text-xs flex-1 sm:flex-none">
              <Filter className="h-3.5 w-3.5 mr-1.5" />
              Filtrar
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleResetFilters}
              className="h-9 text-xs"
              title="Limpar filtros"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              Limpar
            </Button>
          </div>
        </form>
      </div>

      {/* Linha do Tempo Global */}
      <div className="rounded-lg border bg-card p-6 shadow-sm">
        <AuditTimeline
          entityType={activeFilters.entity_type}
          action={activeFilters.action}
          title="Trilha de Auditoria do Sistema"
          description="Histórico imutável de ações operacionais e modificações da rede"
        />
      </div>
    </div>
  );
}
