"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getStructure,
  deleteStructure,
  listPorts,
  listDevices,
  getStructureConnectivity,
} from "@/features/inventory/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { ErrorState, LoadingState } from "@/components/ui/state-displays";
import { formatPtBrNumber } from "@/lib/format/numbers";
import { StructureFormDialog } from "@/features/inventory/components/structure-form-dialog";
import { PortFormDialog } from "@/features/inventory/components/port-form-dialog";
import { DeactivationDialog } from "@/features/inventory/components/deactivation-dialog";
import { DevicesTable } from "@/features/inventory/components/devices-table";
import { FusionEditor } from "@/features/connectivity/components/fusion-editor";
import { CtoPortsGrid } from "@/features/customers/components/cto-ports-grid";
import {
  MapPin,
  Edit,
  Trash2,
  Map,
  Copy,
  Check,
  Server,
  Network,
  Plus,
  ArrowLeft,
} from "lucide-react";
import { CopyableCoordinates } from "@/components/ui/copyable-coordinates";
import Link from "next/link";

export interface StructureDetailViewProps {
  structureId: string;
  kindOverride?: "pole" | "ceo" | "cto" | "manhole" | "pedestal";
}

const KIND_TITLES: Record<string, string> = {
  pole: "Poste",
  ceo: "Caixa de Emenda Óptica (CEO)",
  cto: "Caixa de Terminação Óptica (CTO)",
  manhole: "Caixa Subterrânea",
  pedestal: "Pedestal",
};

export function StructureDetailView({ structureId, kindOverride }: StructureDetailViewProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = React.useState<"overview" | "connectivity" | "devices" | "map">(
    "overview"
  );
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [portDialogOpen, setPortDialogOpen] = React.useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = React.useState(false);
  const [copiedCoords, setCopiedCoords] = React.useState(false);

  const {
    data: structure,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["inventory", "structures", structureId],
    queryFn: () => getStructure(structureId),
  });

  // Consulta de portas da estrutura (para CTOs ou caixas)
  const { data: portsData, refetch: refetchPorts } = useQuery({
    queryKey: ["inventory", "ports", "by-structure", structureId],
    queryFn: () => listPorts({ structure_id: structureId, page_size: 100 }),
    enabled: Boolean(structure),
  });

  // Consulta de conectividade interna (para CEOs)
  const { data: connectivityData } = useQuery({
    queryKey: ["inventory", "structures", structureId, "connectivity"],
    queryFn: () => getStructureConnectivity(structureId),
    enabled: Boolean(structure && structure.kind === "ceo"),
  });

  // Consulta de dispositivos instalados nesta estrutura
  const { data: devicesData } = useQuery({
    queryKey: ["inventory", "devices", "by-structure", structureId],
    queryFn: () => listDevices({ structure_id: structureId, page_size: 100 }),
    enabled: Boolean(structure),
  });

  if (isLoading) {
    return (
      <div className="py-12">
        <LoadingState message="Carregando dados da estrutura física..." />
      </div>
    );
  }

  if (error || !structure) {
    return (
      <div className="py-12">
        <ErrorState
          title="Estrutura não encontrada"
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const coords = structure.location?.coordinates;
  const lat = coords ? coords[1] : null;
  const lon = coords ? coords[0] : null;

  const copyCoordinates = () => {
    if (lat !== null && lon !== null) {
      navigator.clipboard.writeText(`${lat.toFixed(6)}, ${lon.toFixed(6)}`);
      setCopiedCoords(true);
      setTimeout(() => setCopiedCoords(false), 2000);
    }
  };

  const isCto = structure.kind === "cto";
  const isCeo = structure.kind === "ceo";
  const portsCount = portsData?.total || 0;
  const devicesCount = devicesData?.total || 0;

  const dependencies = [
    { label: "Portas de atendimento cadastradas", count: portsCount },
    { label: "Equipamentos alocados na estrutura", count: devicesCount },
  ];

  const structureKind = structure.kind || kindOverride || "pole";
  const backHref = `/${structureKind === "pole" ? "poles" : structureKind === "ceo" ? "ceos" : structureKind === "cto" ? "ctos" : "structures"}`;

  return (
    <div className="space-y-6">
      {/* Cabeçalho */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild className="h-9 w-9">
            <Link href={backHref}>
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Voltar</span>
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground font-mono">
                {structure.code}
              </h1>
              <Badge variant="outline" className="text-xs uppercase">
                {KIND_TITLES[structure.kind] || structure.kind}
              </Badge>
              <StatusBadge status={structure.status === "installed" ? "free" : "reserved"} />
              <Badge
                variant={structure.condition === "ok" ? "secondary" : "destructive"}
                className="text-[10px]"
              >
                {structure.condition.toUpperCase()}
              </Badge>
              <Badge variant="secondary" className="font-mono text-[10px]">
                v{structure.version}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {KIND_TITLES[structure.kind] || "Estrutura"} georreferenciada • Capacidade:{" "}
              {structure.capacity} {isCto ? "portas" : isCeo ? "fusões" : "unid."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {lat !== null && lon !== null && (
            <Button variant="outline" size="sm" asChild className="gap-1.5 text-xs">
              <Link href={`/map?lat=${lat}&lng=${lon}&zoom=17&selected=${structure.id}`}>
                <Map className="h-3.5 w-3.5" />
                <span>Ver no Mapa</span>
              </Link>
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            className="gap-1.5 text-xs"
            onClick={() => setEditDialogOpen(true)}
          >
            <Edit className="h-3.5 w-3.5" />
            <span>Editar</span>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-xs text-destructive hover:bg-destructive/10"
            onClick={() => setDeactivateDialogOpen(true)}
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Desativar</span>
          </Button>
        </div>
      </div>

      {/* Navegação por Abas */}
      <div className="flex border-b border-border gap-2">
        <button
          onClick={() => setActiveTab("overview")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors ${
            activeTab === "overview"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Visão Geral
        </button>

        {(isCto || isCeo) && (
          <button
            onClick={() => setActiveTab("connectivity")}
            className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "connectivity"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Network className="h-3 w-3" />
            <span>{isCto ? "Portas de Atendimento" : "Conectividade & Fusões"}</span>
            <span className="rounded-full bg-muted px-1.5 py-0.2 text-[10px] font-mono">
              {isCto ? portsCount : connectivityData?.connections?.length || 0}
            </span>
          </button>
        )}

        <button
          onClick={() => setActiveTab("devices")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "devices"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Server className="h-3 w-3" />
          <span>Dispositivos</span>
          <span className="rounded-full bg-muted px-1.5 py-0.2 text-[10px] font-mono">
            {devicesCount}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("map")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "map"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <MapPin className="h-3 w-3" />
          <span>Localização</span>
        </button>
      </div>

      {/* Conteúdo da Aba: Visão Geral */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground">Identificação e Características</h3>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Código da Estrutura</dt>
                <dd className="font-mono font-bold text-foreground">{structure.code}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Tipo de Estrutura</dt>
                <dd className="capitalize text-foreground">
                  {KIND_TITLES[structure.kind] || structure.kind}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Capacidade Cadastrada</dt>
                <dd className="font-mono font-semibold text-foreground">
                  {structure.capacity} {isCto ? "Portas" : isCeo ? "Fusões" : "Unidades"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Condição Física</dt>
                <dd className="capitalize text-foreground font-medium">{structure.condition}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Situação</dt>
                <dd className="capitalize text-foreground">{structure.status}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Site Vinculado</dt>
                <dd className="text-foreground">
                  {structure.site_id ? (
                    <Link
                      href={`/sites/${structure.site_id}`}
                      className="text-primary hover:underline font-mono"
                    >
                      Ver Site
                    </Link>
                  ) : (
                    "Via Pública / Externo"
                  )}
                </dd>
              </div>
            </dl>
          </div>

          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground">Coordenadas e Controle</h3>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div className="col-span-2">
                <dt className="text-muted-foreground">Coordenadas WGS-84</dt>
                <dd className="flex items-center gap-2 font-mono text-xs pt-1">
                  <span>
                    {lat !== null && lon !== null
                      ? `${formatPtBrNumber(lat, { minDecimals: 6 })}, ${formatPtBrNumber(lon, { minDecimals: 6 })}`
                      : "—"}
                  </span>
                  {lat !== null && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={copyCoordinates}
                      className="h-6 w-6 p-0 text-muted-foreground"
                    >
                      {copiedCoords ? <Check className="h-3 w-3 text-primary" /> : <Copy className="h-3 w-3" />}
                    </Button>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Versão ETag</dt>
                <dd className="font-mono text-foreground font-semibold">v{structure.version}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Criado em</dt>
                <dd className="text-foreground">
                  {structure.created_at ? new Date(structure.created_at).toLocaleDateString("pt-BR") : "—"}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Observações Técnicas</dt>
                <dd className="text-foreground italic">
                  {structure.notes || "Nenhuma observação técnica registrada."}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {/* Conteúdo da Aba: Portas / Conectividade */}
      {activeTab === "connectivity" && (
        <div className="space-y-6">
          {isCto && (
            <div className="space-y-4 pb-6 border-b border-border">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold">Portas de Atendimento ao Assinante (CTO)</h3>
                  <p className="text-xs text-muted-foreground">
                    Grade visual de portas frontais, ocupação em tempo real, reservas e vínculo com clientes.
                  </p>
                </div>
                <Button size="sm" onClick={() => setPortDialogOpen(true)} className="gap-1.5 text-xs">
                  <Plus className="h-4 w-4" />
                  <span>Nova Porta</span>
                </Button>
              </div>

              <CtoPortsGrid structureId={structureId} structureCode={structure.code} />
            </div>
          )}

          {/* Editor Transacional de Fusões, Terminais e Splitters */}
          <FusionEditor
            structureId={structureId}
            structureCode={structure.code}
            structureKind={structure.kind}
          />
        </div>
      )}

      {/* Conteúdo da Aba: Dispositivos */}
      {activeTab === "devices" && (
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-semibold">Equipamentos Instalados na Estrutura</h3>
            <p className="text-xs text-muted-foreground">
              Dispositivos físicos (DIOs, conversores, rádios) fixados nesta estrutura.
            </p>
          </div>
          <DevicesTable structureId={structureId} />
        </div>
      )}

      {/* Conteúdo da Aba: Mapa */}
      {activeTab === "map" && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div>
            <h3 className="text-xs font-semibold">Localização no Mapa Operacional</h3>
            <p className="text-xs text-muted-foreground">
              Visualização vetorial com snap magnético e traçados adjacentes.
            </p>
          </div>
          {lat !== null && lon !== null ? (
            <CopyableCoordinates
              latitude={lat}
              longitude={lon}
              entityId={structure.id}
            />
          ) : (
            <p className="text-xs text-muted-foreground">Coordenadas geográficas não configuradas.</p>
          )}
        </div>
      )}

      {/* Dialog de Edição da Estrutura */}
      <StructureFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        structure={structure}
        defaultKind={(structure.kind as "pole" | "ceo" | "cto" | "manhole" | "pedestal") || "pole"}
        onSuccess={() => refetch()}
      />

      {/* Dialog de Nova Porta */}
      <PortFormDialog
        open={portDialogOpen}
        onOpenChange={setPortDialogOpen}
        structureId={structureId}
        defaultRole="client_access"
        onSuccess={() => refetchPorts()}
      />

      {/* Dialog de Desativação */}
      <DeactivationDialog
        open={deactivateDialogOpen}
        onOpenChange={setDeactivateDialogOpen}
        title={`Desativar ${KIND_TITLES[structure.kind] || "Estrutura"}`}
        entityName={structure.code}
        entityTypeLabel="Estrutura"
        version={structure.version}
        dependencies={dependencies}
        onConfirm={() => deleteStructure(structure.id, structure.version)}
        onSuccess={() => router.push(backHref)}
      />
    </div>
  );
}
