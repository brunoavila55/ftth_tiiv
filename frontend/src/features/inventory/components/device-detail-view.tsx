"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getDevice,
  deleteDevice,
  listPorts,
  deletePort,
  getSite,
  getStructure,
} from "@/features/inventory/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { ErrorState, LoadingState } from "@/components/ui/state-displays";
import { DeviceFormDialog } from "@/features/inventory/components/device-form-dialog";
import { PortFormDialog } from "@/features/inventory/components/port-form-dialog";
import { DeactivationDialog } from "@/features/inventory/components/deactivation-dialog";
import {
  Edit,
  Trash2,
  Plus,
  ArrowLeft,
  Building2,
  Box,
  Cpu,
} from "lucide-react";
import Link from "next/link";

export interface DeviceDetailViewProps {
  deviceId: string;
}

const DEVICE_KIND_LABELS: Record<string, string> = {
  olt: "Terminal Óptico de Linha (OLT)",
  dio: "Distribuidor Interno Óptico (DIO)",
  switch: "Switch de Borda / Agregação",
  onu: "Unidade de Rede Óptica (ONU/ONT)",
};

export function DeviceDetailView({ deviceId }: DeviceDetailViewProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = React.useState<"overview" | "ports" | "location">("overview");
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [portDialogOpen, setPortDialogOpen] = React.useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = React.useState(false);

  const {
    data: device,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["inventory", "devices", deviceId],
    queryFn: () => getDevice(deviceId),
  });

  // Consulta de portas do dispositivo
  const { data: portsData, refetch: refetchPorts } = useQuery({
    queryKey: ["inventory", "ports", "by-device", deviceId],
    queryFn: () => listPorts({ device_id: deviceId, page_size: 100 }),
    enabled: Boolean(device),
  });

  // Consulta do local associado (Site ou Estrutura)
  const { data: hostSite } = useQuery({
    queryKey: ["inventory", "sites", device?.site_id],
    queryFn: () => getSite(device!.site_id!),
    enabled: Boolean(device?.site_id),
  });

  const { data: hostStructure } = useQuery({
    queryKey: ["inventory", "structures", device?.structure_id],
    queryFn: () => getStructure(device!.structure_id!),
    enabled: Boolean(device?.structure_id),
  });

  if (isLoading) {
    return (
      <div className="py-12">
        <LoadingState message="Carregando informações do equipamento..." />
      </div>
    );
  }

  if (error || !device) {
    return (
      <div className="py-12">
        <ErrorState
          title="Dispositivo não encontrado"
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const portsCount = portsData?.total || 0;
  const dependencies = [{ label: "Portas ópticas cadastradas no equipamento", count: portsCount }];

  const handleDeletePort = async (portId: string, portVersion: number) => {
    try {
      await deletePort(portId, portVersion);
      refetchPorts();
    } catch {
      // Erro gerenciado pela API
    }
  };

  return (
    <div className="space-y-6">
      {/* Cabeçalho */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild className="h-9 w-9">
            <Link href="/devices">
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Voltar para Dispositivos</span>
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground font-mono">
                {device.code}
              </h1>
              <Badge variant="outline" className="text-xs uppercase">
                {device.kind}
              </Badge>
              <StatusBadge status={device.status === "installed" ? "free" : "reserved"} />
              <Badge
                variant={device.condition === "ok" ? "secondary" : "destructive"}
                className="text-[10px]"
              >
                {device.condition.toUpperCase()}
              </Badge>
              <Badge variant="secondary" className="font-mono text-[10px]">
                v{device.version}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {device.manufacturer} {device.model}
              {device.serial_number && (
                <span className="ml-2 font-mono text-[11px] text-foreground">
                  (Serial: {device.serial_number})
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5 text-xs"
            onClick={() => setPortDialogOpen(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Nova Porta</span>
          </Button>

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

        <button
          onClick={() => setActiveTab("ports")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "ports"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Cpu className="h-3 w-3" />
          <span>Portas Ópticas</span>
          <span className="rounded-full bg-muted px-1.5 py-0.2 text-[10px] font-mono">
            {portsCount}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("location")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "location"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          {device.site_id ? <Building2 className="h-3 w-3" /> : <Box className="h-3 w-3" />}
          <span>Alocação Física</span>
        </button>
      </div>

      {/* Conteúdo da Aba: Visão Geral */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground">Especificações do Equipamento</h3>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Código de Inventário</dt>
                <dd className="font-mono font-bold text-foreground">{device.code}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Tipo de Dispositivo</dt>
                <dd className="capitalize text-foreground">
                  {DEVICE_KIND_LABELS[device.kind] || device.kind}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Fabricante</dt>
                <dd className="font-medium text-foreground">{device.manufacturer}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Modelo</dt>
                <dd className="font-medium text-foreground">{device.model}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Número de Série (Serial)</dt>
                <dd className="font-mono text-xs font-semibold text-foreground">
                  {device.serial_number || "Não registrado"}
                </dd>
              </div>
            </dl>
          </div>

          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground">Status e Localização</h3>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Situação Operacional</dt>
                <dd className="capitalize text-foreground font-medium">{device.status}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Condição Física</dt>
                <dd className="capitalize text-foreground font-medium">{device.condition}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Local de Hospedagem</dt>
                <dd className="text-foreground pt-1">
                  {hostSite ? (
                    <Link
                      href={`/sites/${hostSite.id}`}
                      className="inline-flex items-center gap-1.5 text-primary hover:underline font-mono"
                    >
                      <Building2 className="h-3.5 w-3.5" />
                      <span>{hostSite.code} — {hostSite.name} (Site/POP)</span>
                    </Link>
                  ) : hostStructure ? (
                    <Link
                      href={`/structures/${hostStructure.id}`}
                      className="inline-flex items-center gap-1.5 text-primary hover:underline font-mono"
                    >
                      <Box className="h-3.5 w-3.5" />
                      <span>{hostStructure.code} ({hostStructure.kind.toUpperCase()})</span>
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">Sem localização definida</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Revisão Concorrente</dt>
                <dd className="font-mono text-foreground font-semibold">v{device.version}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Cadastrado em</dt>
                <dd className="text-foreground">
                  {device.created_at ? new Date(device.created_at).toLocaleDateString("pt-BR") : "—"}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Observações Técnicas</dt>
                <dd className="text-foreground italic">
                  {device.notes || "Nenhuma anotação técnica."}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {/* Conteúdo da Aba: Portas */}
      {activeTab === "ports" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">Portas e Interfaces Ópticas</h3>
              <p className="text-xs text-muted-foreground">
                Portas PON, uplinks de agregação e interfaces ópticas do dispositivo.
              </p>
            </div>
            <Button size="sm" onClick={() => setPortDialogOpen(true)} className="gap-1.5 text-xs">
              <Plus className="h-4 w-4" />
              <span>Nova Porta</span>
            </Button>
          </div>

          {portsData?.items && portsData.items.length > 0 ? (
            <div className="rounded-lg border border-border divide-y divide-border">
              {portsData.items.map((port) => (
                <div key={port.id} className="p-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-foreground">{port.name}</span>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {port.role}
                    </Badge>
                    <span className="text-muted-foreground font-mono text-[11px]">
                      {port.connector_type}
                    </span>
                    {port.has_internal_pass_through && (
                      <Badge variant="secondary" className="text-[9px]">
                        Pass-Through
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="font-mono text-[10px]">
                      v{port.version}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeletePort(port.id, port.version)}
                      className="h-7 px-2 text-xs text-destructive hover:bg-destructive/10"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
              Nenhuma porta óptica cadastrada neste equipamento.
            </div>
          )}
        </div>
      )}

      {/* Conteúdo da Aba: Localização */}
      {activeTab === "location" && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div>
            <h3 className="text-xs font-semibold">Local Técnico de Hospedagem</h3>
            <p className="text-xs text-muted-foreground">
              Equipamento alocado fisicamente conforme a regra de exclusividade mútua.
            </p>
          </div>

          {hostSite ? (
            <div className="rounded-md border border-border bg-muted/40 p-4 space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-primary" />
                <span className="font-bold text-foreground">{hostSite.name}</span>
                <Badge variant="outline" className="font-mono text-[10px]">
                  {hostSite.code}
                </Badge>
              </div>
              <p className="text-muted-foreground">Tipo: {hostSite.kind.toUpperCase()}</p>
              {hostSite.address && <p className="text-muted-foreground">{hostSite.address}</p>}
              <div className="pt-2">
                <Button size="sm" variant="outline" asChild className="text-xs">
                  <Link href={`/sites/${hostSite.id}`}>Ver Detalhes do Site</Link>
                </Button>
              </div>
            </div>
          ) : hostStructure ? (
            <div className="rounded-md border border-border bg-muted/40 p-4 space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <Box className="h-4 w-4 text-primary" />
                <span className="font-bold text-foreground">{hostStructure.code}</span>
                <Badge variant="outline" className="text-[10px] uppercase">
                  {hostStructure.kind}
                </Badge>
              </div>
              <p className="text-muted-foreground">Condição: {hostStructure.condition.toUpperCase()}</p>
              <div className="pt-2">
                <Button size="sm" variant="outline" asChild className="text-xs">
                  <Link href={`/structures/${hostStructure.id}`}>Ver Detalhes da Estrutura</Link>
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Sem local associado.</p>
          )}
        </div>
      )}

      {/* Dialog de Edição do Dispositivo */}
      <DeviceFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        device={device}
        onSuccess={() => refetch()}
      />

      {/* Dialog de Nova Porta */}
      <PortFormDialog
        open={portDialogOpen}
        onOpenChange={setPortDialogOpen}
        deviceId={deviceId}
        defaultRole="pon"
        onSuccess={() => refetchPorts()}
      />

      {/* Dialog de Desativação */}
      <DeactivationDialog
        open={deactivateDialogOpen}
        onOpenChange={setDeactivateDialogOpen}
        title="Desativar Dispositivo"
        entityName={device.code}
        entityTypeLabel="Dispositivo"
        version={device.version}
        dependencies={dependencies}
        onConfirm={() => deleteDevice(device.id, device.version)}
        onSuccess={() => router.push("/devices")}
      />
    </div>
  );
}
