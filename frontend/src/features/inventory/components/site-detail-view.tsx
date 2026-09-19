"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getSite,
  deleteSite,
  listDevices,
  listStructures,
} from "@/features/inventory/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { ErrorState, LoadingState } from "@/components/ui/state-displays";
import { formatPtBrNumber } from "@/lib/format/numbers";
import { SiteFormDialog } from "@/features/inventory/components/site-form-dialog";
import { DeactivationDialog } from "@/features/inventory/components/deactivation-dialog";
import { DevicesTable } from "@/features/inventory/components/devices-table";
import {
  MapPin,
  Edit,
  Trash2,
  Map,
  Copy,
  Check,
  Server,
  Box,
  ArrowLeft,
} from "lucide-react";
import { CopyableCoordinates } from "@/components/ui/copyable-coordinates";
import Link from "next/link";
import { PermissionGate } from "@/components/auth/permission-gate";

export interface SiteDetailViewProps {
  siteId: string;
}

export function SiteDetailView({ siteId }: SiteDetailViewProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = React.useState<"overview" | "devices" | "structures" | "map">(
    "overview"
  );
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = React.useState(false);
  const [copiedCoords, setCopiedCoords] = React.useState(false);

  const {
    data: site,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["inventory", "sites", siteId],
    queryFn: () => getSite(siteId),
  });

  // Consulta contagem de dependências para o diálogo de desativação
  const { data: siteDevices } = useQuery({
    queryKey: ["inventory", "devices", "by-site", siteId],
    queryFn: () => listDevices({ site_id: siteId, page_size: 100 }),
    enabled: Boolean(site),
  });

  const { data: allStructures } = useQuery({
    queryKey: ["inventory", "structures", "by-site", siteId],
    queryFn: () => listStructures({ page_size: 100 }),
    enabled: Boolean(site),
  });

  const structuresInSite = React.useMemo(() => {
    if (!allStructures?.items) return [];
    return allStructures.items.filter((st) => st.site_id === siteId);
  }, [allStructures, siteId]);

  if (isLoading) {
    return (
      <div className="py-12">
        <LoadingState message="Carregando informações detalhadas do site..." />
      </div>
    );
  }

  if (error || !site) {
    return (
      <div className="py-12">
        <ErrorState
          title="Site não encontrado"
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const coords = site.location?.coordinates;
  const lat = coords ? coords[1] : null;
  const lon = coords ? coords[0] : null;

  const copyCoordinates = () => {
    if (lat !== null && lon !== null) {
      navigator.clipboard.writeText(`${lat.toFixed(6)}, ${lon.toFixed(6)}`);
      setCopiedCoords(true);
      setTimeout(() => setCopiedCoords(false), 2000);
    }
  };

  const dependencies = [
    { label: "Dispositivos / Equipamentos instalados", count: siteDevices?.total || 0 },
    { label: "Estruturas físicas associadas", count: structuresInSite.length },
  ];

  return (
    <div className="space-y-6">
      {/* Barra de Navegação e Ações Superiores */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild className="h-9 w-9">
            <Link href="/sites">
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Voltar para Sites</span>
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground font-mono">
                {site.code}
              </h1>
              <Badge variant="outline" className="text-xs uppercase">
                {site.kind}
              </Badge>
              <StatusBadge status={site.status === "installed" ? "free" : "reserved"} />
              <Badge variant="secondary" className="font-mono text-[10px]">
                v{site.version}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">{site.name}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {lat !== null && lon !== null && (
            <Button variant="outline" size="sm" asChild className="gap-1.5 text-xs">
              <Link href={`/map?lat=${lat}&lng=${lon}&zoom=17&selected=${site.id}`}>
                <Map className="h-3.5 w-3.5" />
                <span>Ver no Mapa</span>
              </Link>
            </Button>
          )}

          <PermissionGate permission="network:write">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 text-xs"
              onClick={() => setEditDialogOpen(true)}
            >
              <Edit className="h-3.5 w-3.5" />
              <span>Editar</span>
            </Button>
          </PermissionGate>

          <PermissionGate permission="network:write">
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-xs text-destructive hover:bg-destructive/10"
              onClick={() => setDeactivateDialogOpen(true)}
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Desativar</span>
            </Button>
          </PermissionGate>
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
            {siteDevices?.total || 0}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("structures")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "structures"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Box className="h-3 w-3" />
          <span>Estruturas</span>
          <span className="rounded-full bg-muted px-1.5 py-0.2 text-[10px] font-mono">
            {structuresInSite.length}
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
            <h3 className="text-xs font-semibold text-foreground">Identificação e Cadastro</h3>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Código Único</dt>
                <dd className="font-mono font-bold text-foreground">{site.code}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Nome Legível</dt>
                <dd className="font-medium text-foreground">{site.name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Tipo de Estação</dt>
                <dd className="capitalize text-foreground">{site.kind.replace("_", " ")}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Situação</dt>
                <dd className="capitalize text-foreground">{site.status}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Endereço / Referência</dt>
                <dd className="text-foreground">{site.address || "Não informado"}</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground">Geolocalização e Auditoria</h3>
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
                <dt className="text-muted-foreground">Versão de Concorrência</dt>
                <dd className="font-mono text-foreground font-semibold">v{site.version}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Cadastrado em</dt>
                <dd className="text-foreground">
                  {site.created_at ? new Date(site.created_at).toLocaleDateString("pt-BR") : "—"}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Observações Técnicas</dt>
                <dd className="text-foreground italic">{site.notes || "Nenhuma anotação técnica."}</dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {/* Conteúdo da Aba: Dispositivos */}
      {activeTab === "devices" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">Equipamentos Instalados no Site</h3>
              <p className="text-xs text-muted-foreground">
                OLTs, DIOs, switches e roteadores alocados neste local técnico.
              </p>
            </div>
          </div>
          <DevicesTable siteId={siteId} />
        </div>
      )}

      {/* Conteúdo da Aba: Estruturas */}
      {activeTab === "structures" && (
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-semibold">Estruturas Físicas Associadas</h3>
            <p className="text-xs text-muted-foreground">
              Armários, caixas ou suportes alocados internamente nesta estação técnica.
            </p>
          </div>
          {structuresInSite.length > 0 ? (
            <div className="rounded-lg border border-border divide-y divide-border">
              {structuresInSite.map((st) => (
                <div key={st.id} className="p-3 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-mono font-bold text-foreground">{st.code}</span>
                    <span className="text-muted-foreground ml-2">({st.kind.toUpperCase()})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{st.status}</Badge>
                    <Button variant="ghost" size="sm" asChild className="h-7 px-2 text-xs">
                      <Link href={`/structures/${st.id}`}>Ver Detalhes</Link>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
              Nenhuma estrutura associada a este site.
            </div>
          )}
        </div>
      )}

      {/* Conteúdo da Aba: Mapa */}
      {activeTab === "map" && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div>
            <h3 className="text-xs font-semibold">Visualização Geográfica</h3>
            <p className="text-xs text-muted-foreground">
              Localização exata da estação técnica no Mapa Operacional.
            </p>
          </div>
          {lat !== null && lon !== null ? (
            <CopyableCoordinates
              latitude={lat}
              longitude={lon}
              entityId={site.id}
            />
          ) : (
            <p className="text-xs text-muted-foreground">Coordenadas geográficas não configuradas.</p>
          )}
        </div>
      )}

      {/* Dialog de Edição */}
      <SiteFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        site={site}
        onSuccess={() => refetch()}
      />

      {/* Dialog de Desativação */}
      <DeactivationDialog
        open={deactivateDialogOpen}
        onOpenChange={setDeactivateDialogOpen}
        title="Desativar Site / POP"
        entityName={site.code}
        entityTypeLabel="Site"
        version={site.version}
        dependencies={dependencies}
        onConfirm={() => deleteSite(site.id, site.version)}
        onSuccess={() => router.push("/sites")}
      />
    </div>
  );
}
