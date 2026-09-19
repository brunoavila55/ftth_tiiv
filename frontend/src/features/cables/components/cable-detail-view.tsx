"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getCable,
  deleteCable,
  listCableSegments,
  deleteCableSegment,
  type CableSegmentRead,
} from "@/features/cables/api";
import { listStructures } from "@/features/inventory/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { ErrorState, LoadingState } from "@/components/ui/state-displays";
import { formatPtBrNumber } from "@/lib/format/numbers";
import { CableFormDialog } from "@/features/cables/components/cable-form-dialog";
import { CableFibersView } from "@/features/cables/components/cable-fibers-view";
import { SplitSegmentDialog } from "@/features/cables/components/split-segment-dialog";
import { DeactivationDialog } from "@/features/inventory/components/deactivation-dialog";
import {
  Cable as CableIcon,
  Layers,
  MapPin,
  Edit,
  Trash2,
  Scissors,
  ArrowLeft,
  Map,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { PermissionGate } from "@/components/auth/permission-gate";

export interface CableDetailViewProps {
  cableId: string;
}

export function CableDetailView({ cableId }: CableDetailViewProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = React.useState<"summary" | "segments" | "fibers" | "map">(
    "summary"
  );
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = React.useState(false);
  const [splitDialogOpen, setSplitDialogOpen] = React.useState(false);
  const [splittingSegment, setSplittingSegment] = React.useState<CableSegmentRead | null>(null);

  const {
    data: cable,
    isLoading,
    error,
    refetch: refetchCable,
  } = useQuery({
    queryKey: ["cables", "detail", cableId],
    queryFn: () => getCable(cableId),
  });

  const {
    data: segmentsData,
    refetch: refetchSegments,
  } = useQuery({
    queryKey: ["cables", "segments", cableId],
    queryFn: () => listCableSegments({ cable_id: cableId, page_size: 100 }),
    enabled: Boolean(cable),
  });

  // Carrega mapeamento de códigos de estruturas para exibição amigável dos trechos
  const { data: structuresData } = useQuery({
    queryKey: ["inventory", "structures", "all"],
    queryFn: () => listStructures({ page_size: 200 }),
  });

  const structureCodeMap = React.useMemo(() => {
    const map: Record<string, string> = {};
    structuresData?.items?.forEach((st) => {
      map[st.id] = `${st.code} (${st.kind.toUpperCase()})`;
    });
    return map;
  }, [structuresData]);

  if (isLoading) {
    return (
      <div className="py-12">
        <LoadingState message="Carregando ficha técnica do cabo óptico..." />
      </div>
    );
  }

  if (error || !cable) {
    return (
      <div className="py-12">
        <ErrorState
          title="Cabo óptico não encontrado"
          error={error}
          onRetry={() => refetchCable()}
        />
      </div>
    );
  }

  const segments = segmentsData?.items || [];

  // Calcula extensão óptica total acumulada
  const totalLengthMeters = segments.reduce((acc, seg) => acc + seg.effective_length_m, 0);

  const dependencies = [
    { label: "Trechos / Segmentos instalados", count: segments.length },
  ];

  const handleDeleteSegment = async (segmentId: string, version: number) => {
    try {
      await deleteCableSegment(segmentId, version);
      refetchSegments();
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
            <Link href="/cables">
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Voltar para Cabos</span>
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground font-mono">
                {cable.code}
              </h1>
              <Badge variant="outline" className="text-xs font-mono font-bold">
                {cable.fiber_count} FO
              </Badge>
              <Badge variant="secondary" className="text-[10px]">
                Norma {cable.color_standard}
              </Badge>
              <StatusBadge status={cable.status === "installed" ? "free" : "reserved"} />
              <Badge variant="secondary" className="font-mono text-[10px]">
                v{cable.version}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">{cable.model}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
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
          onClick={() => setActiveTab("summary")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors ${
            activeTab === "summary"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Resumo & Métricas
        </button>

        <button
          onClick={() => setActiveTab("segments")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "segments"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Layers className="h-3 w-3" />
          <span>Segmentos (Trechos)</span>
          <span className="rounded-full bg-muted px-1.5 py-0.2 text-[10px] font-mono">
            {segments.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("fibers")}
          className={`pb-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "fibers"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <CableIcon className="h-3 w-3" />
          <span>Tubos & Fibras</span>
          <span className="rounded-full bg-muted px-1.5 py-0.2 text-[10px] font-mono">
            {cable.fiber_count} FO
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
          <span>Traçado Geográfico</span>
        </button>
      </div>

      {/* Conteúdo da Aba: Resumo */}
      {activeTab === "summary" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground">Especificações Técnicas do Cabo</h3>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Código Único</dt>
                <dd className="font-mono font-bold text-foreground">{cable.code}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Modelo / Fabricante</dt>
                <dd className="font-medium text-foreground">{cable.model}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Capacidade Total</dt>
                <dd className="font-bold text-foreground">
                  {cable.fiber_count} Fibras ({cable.tube_count} Tubos Loose)
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Padrão de Cores</dt>
                <dd className="font-mono text-foreground font-semibold">
                  Norma {cable.color_standard}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Situação</dt>
                <dd className="capitalize text-foreground">{cable.status}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Total de Trechos</dt>
                <dd className="font-mono font-semibold text-foreground">
                  {segments.length} trecho{segments.length === 1 ? "" : "s"}
                </dd>
              </div>
            </dl>
          </div>

          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground">Métricas Ópticas e Extensão</h3>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div className="col-span-2">
                <dt className="text-muted-foreground">Comprimento Óptico Acumulado</dt>
                <dd className="text-lg font-bold font-mono text-primary pt-1">
                  {formatPtBrNumber(totalLengthMeters, { minDecimals: 1, maxDecimals: 1 })} metros
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Versão Concorrente</dt>
                <dd className="font-mono text-foreground font-semibold">v{cable.version}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Cadastrado em</dt>
                <dd className="text-foreground">
                  {cable.created_at ? new Date(cable.created_at).toLocaleDateString("pt-BR") : "—"}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Observações Técnicas</dt>
                <dd className="text-foreground italic">
                  {cable.notes || "Nenhuma anotação técnica registrada."}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {/* Conteúdo da Aba: Segmentos */}
      {activeTab === "segments" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">Trechos Físicos do Cabo Óptico</h3>
              <p className="text-xs text-muted-foreground">
                Traçados geodésicos conectando estruturas de ancoragem e terminação A e B.
              </p>
            </div>
            <Button size="sm" asChild className="gap-1.5 text-xs">
              <Link href={`/map?mode=draw_cable`}>
                <Plus className="h-4 w-4" />
                <span>Traçar Trecho no Mapa</span>
              </Link>
            </Button>
          </div>

          {segments.length > 0 ? (
            <div className="rounded-lg border border-border divide-y divide-border">
              {segments.map((seg, idx) => {
                const originLabel = structureCodeMap[seg.origin_structure_id] || "Estrutura A";
                const destLabel = structureCodeMap[seg.destination_structure_id] || "Estrutura B";
                return (
                  <div
                    key={seg.id}
                    className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-foreground">Trecho #{idx + 1}</span>
                        <Badge variant="outline" className="font-mono text-[10px]">
                          {seg.length_source === "measured" ? "Medido em Campo" : "Calculado no Mapa"}
                        </Badge>
                      </div>
                      <p className="text-muted-foreground">
                        {originLabel} ➔ {destLabel}
                      </p>
                      <div className="flex items-center gap-3 font-mono text-[11px] text-muted-foreground pt-0.5">
                        <span>Mapa: {seg.map_length_m.toFixed(1)}m</span>
                        {seg.measured_length_m !== null && (
                          <span>Campo: {seg.measured_length_m.toFixed(1)}m</span>
                        )}
                        <span>Reserva: {seg.slack_length_m.toFixed(1)}m</span>
                        <span className="font-bold text-primary">
                          Efetivo: {seg.effective_length_m.toFixed(1)}m
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <PermissionGate permission="network:write">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSplittingSegment(seg);
                            setSplitDialogOpen(true);
                          }}
                          className="h-8 gap-1.5 text-xs"
                        >
                          <Scissors className="h-3.5 w-3.5 text-primary" />
                          <span>Dividir Trecho</span>
                        </Button>
                      </PermissionGate>

                      <PermissionGate permission="network:write">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteSegment(seg.id, seg.version)}
                          className="h-8 px-2 text-xs text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          <span className="sr-only">Excluir Trecho</span>
                        </Button>
                      </PermissionGate>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-xs text-muted-foreground space-y-2">
              <p>Nenhum trecho cadastrado para este cabo óptico.</p>
              <Button size="sm" variant="outline" asChild className="gap-1.5 text-xs">
                <Link href="/map">
                  <Map className="h-3.5 w-3.5" />
                  <span>Traçar Trecho no Mapa Operacional</span>
                </Link>
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Conteúdo da Aba: Tubos & Fibras */}
      {activeTab === "fibers" && (
        <CableFibersView cable={cable} segments={segments} />
      )}

      {/* Conteúdo da Aba: Mapa */}
      {activeTab === "map" && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div>
            <h3 className="text-xs font-semibold">Traçado do Cabo no Mapa</h3>
            <p className="text-xs text-muted-foreground">
              Visualização de todos os trechos conectados do cabo óptico.
            </p>
          </div>

          <div className="rounded-md border border-border bg-muted/40 p-4 text-xs font-mono space-y-1">
            <p>Total de trechos vetorizados: {segments.length}</p>
            <p>Comprimento acumulado: {totalLengthMeters.toFixed(1)} metros</p>
          </div>

          <Button asChild className="gap-1.5 text-xs">
            <Link href={`/map?selected=${cable.id}`}>
              <Map className="h-4 w-4" />
              <span>Visualizar no Mapa Operacional</span>
            </Link>
          </Button>
        </div>
      )}

      {/* Dialog de Edição */}
      <CableFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        cable={cable}
        onSuccess={() => refetchCable()}
      />

      {/* Dialog de Divisão de Trecho */}
      <SplitSegmentDialog
        open={splitDialogOpen}
        onOpenChange={setSplitDialogOpen}
        segment={splittingSegment}
        totalFibers={cable.fiber_count}
        onSuccess={() => {
          refetchSegments();
          refetchCable();
        }}
      />

      {/* Dialog de Desativação */}
      <DeactivationDialog
        open={deactivateDialogOpen}
        onOpenChange={setDeactivateDialogOpen}
        title="Desativar Cabo Óptico"
        entityName={cable.code}
        entityTypeLabel="Cabo"
        version={cable.version}
        dependencies={dependencies}
        onConfirm={() => deleteCable(cable.id, cable.version)}
        onSuccess={() => router.push("/cables")}
      />
    </div>
  );
}
