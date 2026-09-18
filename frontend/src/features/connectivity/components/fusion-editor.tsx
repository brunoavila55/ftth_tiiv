"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getStructureConnectivity,
  executeBatchConnections,
  type TerminalRead,
  type ConnectionRead,
  type BatchOperationItem,
} from "@/features/connectivity/api";
import { ConnectionModal, formatTerminalKind } from "./connection-modal";
import { DisconnectDialog } from "./disconnect-dialog";
import { ReservationDialog } from "./reservation-dialog";
import { TopologyConflictDialog } from "./topology-conflict-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { Input } from "@/components/ui/input";
import { LoadingState, ErrorState } from "@/components/ui/state-displays";
import { ApiError } from "@/lib/api/types";
import {
  Zap,
  Unlink,
  Bookmark,
  Layers,
  Table as TableIcon,
  Activity,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Send,
  Search,
  Split,
} from "lucide-react";

export interface FusionEditorProps {
  structureId: string;
  structureCode?: string;
  structureKind?: string;
}

export function FusionEditor({
  structureId,
  structureCode,
}: FusionEditorProps) {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = React.useState<"panels" | "table" | "active-connections">("panels");
  const [draftOperations, setDraftOperations] = React.useState<BatchOperationItem[]>([]);
  const [searchQuery, setSearchQuery] = React.useState<string>("");
  const [kindFilter, setKindFilter] = React.useState<string>("all");
  const [occupancyFilter, setOccupancyFilter] = React.useState<string>("all");

  // Modais
  const [isConnectionModalOpen, setIsConnectionModalOpen] = React.useState<boolean>(false);
  const [selectedTerminalAId, setSelectedTerminalAId] = React.useState<string | null>(null);
  const [disconnectModalConn, setDisconnectModalConn] = React.useState<ConnectionRead | null>(null);
  const [reservationModalTerminal, setReservationModalTerminal] = React.useState<TerminalRead | null>(null);

  // Conflito de Concorrência Topológica (409)
  const [conflictDialogOpen, setConflictDialogOpen] = React.useState<boolean>(false);
  const [lastExpectedRevision, setLastExpectedRevision] = React.useState<number>(0);

  // Mensagens de status da submissão
  const [feedback, setFeedback] = React.useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Query de dados de conectividade da estrutura
  const {
    data: connectivity,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["structure-connectivity", structureId],
    queryFn: () => getStructureConnectivity(structureId),
    enabled: Boolean(structureId),
  });

  // Mutação em lote
  const batchMutation = useMutation({
    mutationFn: (vars: Parameters<typeof executeBatchConnections>[0]) => executeBatchConnections(vars),
    onSuccess: (data) => {
      setFeedback({
        type: "success",
        message: `Lote aplicado com sucesso! ${data.applied_operations_count} operações transacionadas. Nova revisão topológica: rev #${data.new_topology_revision}.`,
      });
      setDraftOperations([]);
      queryClient.invalidateQueries({ queryKey: ["structure-connectivity", structureId] });
      queryClient.invalidateQueries({ queryKey: ["structures", structureId] });
    },
    onError: (err: unknown) => {
      const isConflict =
        (err instanceof ApiError && err.status === 409) ||
        (typeof err === "object" && err !== null && (err as { status?: number }).status === 409);

      if (isConflict) {
        setLastExpectedRevision(connectivity?.topology_revision || 0);
        setConflictDialogOpen(true);
      } else {
        const errorDetail =
          err instanceof ApiError
            ? err.detail || err.message
            : "Falha ao aplicar lote de conexões no servidor.";
        setFeedback({
          type: "error",
          message: errorDetail,
        });
      }
    },
  });

  const terminals = React.useMemo(() => connectivity?.terminals || [], [connectivity?.terminals]);
  const connections = React.useMemo(() => connectivity?.connections || [], [connectivity?.connections]);
  const reservations = React.useMemo(() => connectivity?.reservations || [], [connectivity?.reservations]);
  const topologyRevision = connectivity?.topology_revision ?? 0;

  // Mapa de ocupação considerando servidor + rascunho local
  const occupiedTerminalIds = React.useMemo(() => {
    const set = new Set<string>();

    // 1. Terminais ocupados no servidor
    terminals.forEach((t) => {
      if (t.is_occupied) set.add(t.id);
    });

    // 2. Terminais com reservas ativas no servidor
    reservations.forEach((r) => {
      if (r.is_active) set.add(r.terminal_id);
    });

    // 3. Modificações do rascunho local
    draftOperations.forEach((op) => {
      if (op.action === "connect") {
        set.add(op.terminal_a_id);
        if (op.terminal_b_id) set.add(op.terminal_b_id);
      } else if (op.action === "reserve") {
        set.add(op.terminal_a_id);
      } else if (op.action === "disconnect") {
        // Libera no rascunho para reuso
        set.delete(op.terminal_a_id);
        if (op.terminal_b_id) set.delete(op.terminal_b_id);
      } else if (op.action === "release") {
        set.delete(op.terminal_a_id);
      }
    });

    return set;
  }, [terminals, reservations, draftOperations]);

  // Mapa de conexão ativa para cada terminal (para exibição rápida)
  const terminalConnectionMap = React.useMemo(() => {
    const map = new Map<string, ConnectionRead>();
    connections.forEach((c) => {
      if (c.is_active) {
        map.set(c.terminal_a_id, c);
        map.set(c.terminal_b_id, c);
      }
    });
    return map;
  }, [connections]);

  // Adiciona operação ao rascunho de lote
  const handleAddOperation = (op: BatchOperationItem) => {
    setFeedback(null);
    setDraftOperations((prev) => [...prev, op]);
  };

  // Remove operação do rascunho (desfazer local)
  const handleRemoveDraftOperation = (index: number) => {
    setDraftOperations((prev) => prev.filter((_, i) => i !== index));
  };

  // Limpa todo o rascunho
  const handleClearDraft = () => {
    setDraftOperations([]);
    setFeedback(null);
  };

  // Submete lote ao servidor com a revisão esperada
  const handleSubmitBatch = () => {
    if (draftOperations.length === 0) return;
    setFeedback(null);
    batchMutation.mutate({
      structure_id: structureId,
      expected_topology_revision: topologyRevision,
      operations: draftOperations,
    });
  };

  // Reconciliação após conflito 409: recarrega servidor preservando rascunho
  const handleReconcile = async () => {
    await refetch();
    setFeedback({
      type: "success",
      message: "Topologia atualizada com a revisão mais recente do servidor. Propostas locais mantidas no rascunho para revisão.",
    });
  };

  // Filtros de terminais
  const filteredTerminals = React.useMemo(() => {
    return terminals.filter((t) => {
      if (kindFilter !== "all" && t.kind !== kindFilter) return false;
      const isOccupied = occupiedTerminalIds.has(t.id);
      const isReserved = reservations.some((r) => r.terminal_id === t.id && r.is_active);

      if (occupancyFilter === "free" && isOccupied) return false;
      if (occupancyFilter === "occupied" && !isOccupied) return false;
      if (occupancyFilter === "reserved" && !isReserved) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          t.label.toLowerCase().includes(q) ||
          t.id.toLowerCase().includes(q) ||
          t.kind.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [terminals, kindFilter, occupancyFilter, searchQuery, occupiedTerminalIds, reservations]);

  // Agrupamentos para o modo painéis
  const fiberTerminals = React.useMemo(
    () => filteredTerminals.filter((t) => t.kind === "fiber_endpoint"),
    [filteredTerminals]
  );
  const splitterTerminals = React.useMemo(
    () => filteredTerminals.filter((t) => t.kind === "splitter_input" || t.kind === "splitter_output"),
    [filteredTerminals]
  );
  const portTerminals = React.useMemo(
    () => filteredTerminals.filter((t) => t.kind === "port_front" || t.kind === "port_back"),
    [filteredTerminals]
  );

  if (isLoading) {
    return <LoadingState message="Carregando matriz de fusões e terminais da estrutura..." />;
  }

  if (isError) {
    return (
      <ErrorState
        title="Erro ao carregar conectividade óptica"
        error={error}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Cabeçalho do Editor de Fusões */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            <h2 className="text-base font-bold text-foreground">
              Editor de Fusões e Terminais: {structureCode || structureId}
            </h2>
            <Badge variant="outline" className="font-mono text-xs">
              rev #{topologyRevision}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Gerenciamento transacional de fusões ópticas, cordões de manobra (patch cords), splitters e reservas.
          </p>
        </div>

        {/* Botão de Conexão Rápida e Abas de Visualização */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => {
              setSelectedTerminalAId(null);
              setIsConnectionModalOpen(true);
            }}
          >
            <Zap className="h-4 w-4 mr-1.5 text-amber-300" />
            Nova Conexão
          </Button>
        </div>
      </div>

      {/* Banner de Feedback */}
      {feedback && (
        <div
          className={`p-3 rounded-lg border text-xs flex items-center justify-between gap-2 ${
            feedback.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-300"
              : "bg-destructive/10 border-destructive/20 text-destructive"
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => setFeedback(null)}
          >
            Fechar
          </Button>
        </div>
      )}

      {/* Seletor de Visão e Barra de Filtros */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Abas */}
        <div className="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground text-xs">
          <button
            type="button"
            onClick={() => setActiveTab("panels")}
            className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 font-medium transition-all ${
              activeTab === "panels"
                ? "bg-background text-foreground shadow-sm"
                : "hover:text-foreground"
            }`}
          >
            <Layers className="h-3.5 w-3.5 mr-1.5" />
            Painéis de Rede
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("table")}
            className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 font-medium transition-all ${
              activeTab === "table"
                ? "bg-background text-foreground shadow-sm"
                : "hover:text-foreground"
            }`}
          >
            <TableIcon className="h-3.5 w-3.5 mr-1.5" />
            Tabela Textual Acessível ({terminals.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("active-connections")}
            className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 font-medium transition-all ${
              activeTab === "active-connections"
                ? "bg-background text-foreground shadow-sm"
                : "hover:text-foreground"
            }`}
          >
            <Activity className="h-3.5 w-3.5 mr-1.5" />
            Conexões Ativas ({connections.filter((c) => c.is_active).length})
          </button>
        </div>

        {/* Filtros e Busca */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[180px]">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Buscar terminal..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 pl-8 text-xs"
            />
          </div>

          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label="Filtrar por tipo de terminal"
          >
            <option value="all">Todos os Tipos</option>
            <option value="fiber_endpoint">Fibras Ópticas</option>
            <option value="splitter_input">Splitter (Entrada)</option>
            <option value="splitter_output">Splitter (Saída)</option>
            <option value="port_front">Porta (Frente)</option>
            <option value="port_back">Porta (Traseira)</option>
          </select>

          <select
            value={occupancyFilter}
            onChange={(e) => setOccupancyFilter(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label="Filtrar por ocupação"
          >
            <option value="all">Todas as Situações</option>
            <option value="free">Livre</option>
            <option value="occupied">Ocupado</option>
            <option value="reserved">Reservado</option>
          </select>
        </div>
      </div>

      {/* Conteúdo da Aba Selecionada */}
      {activeTab === "panels" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Painel 1: Pontas de Fibra Óptica */}
          <div className="rounded-lg border border-border bg-card overflow-hidden shadow-sm flex flex-col">
            <div className="px-3 py-2.5 bg-muted/40 border-b border-border flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Layers className="h-4 w-4 text-primary" />
                Pontas de Cabos / Fibras ({fiberTerminals.length})
              </span>
              <Badge variant="outline" className="text-[10px]">
                {fiberTerminals.filter((t) => !occupiedTerminalIds.has(t.id)).length} livres
              </Badge>
            </div>
            <div className="p-3 space-y-2 flex-1 max-h-[500px] overflow-y-auto">
              {fiberTerminals.length === 0 ? (
                <p className="text-xs text-muted-foreground italic text-center py-6">
                  Nenhuma ponta de fibra nesta estrutura.
                </p>
              ) : (
                fiberTerminals.map((t) => renderTerminalCard(t))
              )}
            </div>
          </div>

          {/* Painel 2: Splitters Ópticos */}
          <div className="rounded-lg border border-border bg-card overflow-hidden shadow-sm flex flex-col">
            <div className="px-3 py-2.5 bg-muted/40 border-b border-border flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Split className="h-4 w-4 text-amber-500" />
                Splitters Ópticos ({splitterTerminals.length})
              </span>
              <Badge variant="outline" className="text-[10px]">
                {splitterTerminals.filter((t) => !occupiedTerminalIds.has(t.id)).length} livres
              </Badge>
            </div>
            <div className="p-3 space-y-2 flex-1 max-h-[500px] overflow-y-auto">
              {splitterTerminals.length === 0 ? (
                <p className="text-xs text-muted-foreground italic text-center py-6">
                  Nenhum splitter instalado nesta estrutura.
                </p>
              ) : (
                splitterTerminals.map((t) => renderTerminalCard(t))
              )}
            </div>
          </div>

          {/* Painel 3: Portas de Equipamentos / Atendimento */}
          <div className="rounded-lg border border-border bg-card overflow-hidden shadow-sm flex flex-col">
            <div className="px-3 py-2.5 bg-muted/40 border-b border-border flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Zap className="h-4 w-4 text-emerald-500" />
                Portas (Frente / Traseira) ({portTerminals.length})
              </span>
              <Badge variant="outline" className="text-[10px]">
                {portTerminals.filter((t) => !occupiedTerminalIds.has(t.id)).length} livres
              </Badge>
            </div>
            <div className="p-3 space-y-2 flex-1 max-h-[500px] overflow-y-auto">
              {portTerminals.length === 0 ? (
                <p className="text-xs text-muted-foreground italic text-center py-6">
                  Nenhuma porta cadastrada nesta estrutura.
                </p>
              ) : (
                portTerminals.map((t) => renderTerminalCard(t))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Aba: Tabela Textual Acessível */}
      {activeTab === "table" && (
        <div className="rounded-lg border border-border bg-card overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground uppercase text-[10px] font-semibold">
                <tr>
                  <th className="p-2.5">Terminal ID</th>
                  <th className="p-2.5">Rótulo / Descrição</th>
                  <th className="p-2.5">Tipo Físico</th>
                  <th className="p-2.5">Situação</th>
                  <th className="p-2.5">Conectado a</th>
                  <th className="p-2.5 text-right">Ações Acessíveis</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredTerminals.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-muted-foreground italic">
                      Nenhum terminal atende aos filtros atuais.
                    </td>
                  </tr>
                ) : (
                  filteredTerminals.map((t) => {
                    const isOccupied = occupiedTerminalIds.has(t.id);
                    const conn = terminalConnectionMap.get(t.id);
                    const otherTermId = conn ? (conn.terminal_a_id === t.id ? conn.terminal_b_id : conn.terminal_a_id) : null;
                    const otherTerm = otherTermId ? terminals.find((x) => x.id === otherTermId) : null;

                    return (
                      <tr key={t.id} className="hover:bg-muted/20 transition-colors">
                        <td className="p-2.5 font-mono text-[11px] font-medium text-foreground select-all">
                          {t.id}
                        </td>
                        <td className="p-2.5 font-semibold text-foreground">
                          {t.label}
                        </td>
                        <td className="p-2.5">
                          <Badge variant="outline" className="text-[10px]">
                            {formatTerminalKind(t.kind)}
                          </Badge>
                        </td>
                        <td className="p-2.5">
                          <StatusBadge status={isOccupied ? "connected" : "free"} />
                        </td>
                        <td className="p-2.5 text-muted-foreground font-mono text-[11px]">
                          {otherTerm ? (
                            <span className="text-foreground font-medium">
                              {otherTerm.label} ({conn?.loss_db} dB)
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="p-2.5 text-right space-x-1.5 whitespace-nowrap">
                          {!isOccupied ? (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                onClick={() => {
                                  setSelectedTerminalAId(t.id);
                                  setIsConnectionModalOpen(true);
                                }}
                              >
                                <Zap className="h-3 w-3 mr-1 text-amber-500" />
                                Conectar
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 text-xs"
                                onClick={() => setReservationModalTerminal(t)}
                              >
                                <Bookmark className="h-3 w-3 mr-1 text-primary" />
                                Reservar
                              </Button>
                            </>
                          ) : conn ? (
                            <Button
                              size="sm"
                              variant="destructive"
                              className="h-7 text-xs"
                              onClick={() => setDisconnectModalConn(conn)}
                            >
                              <Unlink className="h-3 w-3 mr-1" />
                              Desconectar
                            </Button>
                          ) : (
                            <span className="text-muted-foreground italic text-[11px]">Ocupado / Reservado</span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Aba: Conexões Ativas e Histórico */}
      {activeTab === "active-connections" && (
        <div className="rounded-lg border border-border bg-card overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground uppercase text-[10px] font-semibold">
                <tr>
                  <th className="p-2.5">Terminal A</th>
                  <th className="p-2.5">Terminal B</th>
                  <th className="p-2.5">Tipo Físico</th>
                  <th className="p-2.5">Perda (dB)</th>
                  <th className="p-2.5">Data de Criação</th>
                  <th className="p-2.5 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {connections.filter((c) => c.is_active).length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-muted-foreground italic">
                      Nenhuma conexão óptica ativa registrada nesta estrutura.
                    </td>
                  </tr>
                ) : (
                  connections
                    .filter((c) => c.is_active)
                    .map((conn) => {
                      const termA = terminals.find((t) => t.id === conn.terminal_a_id);
                      const termB = terminals.find((t) => t.id === conn.terminal_b_id);

                      return (
                        <tr key={conn.id} className="hover:bg-muted/20 transition-colors">
                          <td className="p-2.5">
                            <p className="font-semibold text-foreground">{termA?.label || conn.terminal_a_id}</p>
                            <p className="font-mono text-[10px] text-muted-foreground">{conn.terminal_a_id}</p>
                          </td>
                          <td className="p-2.5">
                            <p className="font-semibold text-foreground">{termB?.label || conn.terminal_b_id}</p>
                            <p className="font-mono text-[10px] text-muted-foreground">{conn.terminal_b_id}</p>
                          </td>
                          <td className="p-2.5 capitalize text-foreground">
                            {conn.connection_type.replace("_", " ")}
                          </td>
                          <td className="p-2.5 font-mono font-medium text-foreground">
                            {conn.loss_db} dB
                          </td>
                          <td className="p-2.5 text-muted-foreground">
                            {new Date(conn.created_at).toLocaleString("pt-BR")}
                          </td>
                          <td className="p-2.5 text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-destructive hover:text-destructive text-xs"
                              onClick={() => setDisconnectModalConn(conn)}
                            >
                              <Unlink className="h-3 w-3 mr-1" />
                              Desconectar
                            </Button>
                          </td>
                        </tr>
                      );
                    })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Painel Fixo de Rascunho de Lote (Draft Operations Bar) */}
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-border/40 pb-2">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            <h3 className="text-xs font-bold text-foreground uppercase tracking-wide">
              Lote de Alterações em Rascunho ({draftOperations.length})
            </h3>
            <Badge variant="outline" className="text-[10px] font-mono">
              Revisão Esperada: #{topologyRevision}
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            {draftOperations.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs text-muted-foreground hover:text-foreground"
                onClick={handleClearDraft}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                Descartar Rascunho
              </Button>
            )}
            <Button
              size="sm"
              disabled={draftOperations.length === 0 || batchMutation.isPending}
              onClick={handleSubmitBatch}
            >
              {batchMutation.isPending ? (
                <>Gravando Lote...</>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5 mr-1.5" />
                  Confirmar e Aplicar Lote ({draftOperations.length})
                </>
              )}
            </Button>
          </div>
        </div>

        {draftOperations.length === 0 ? (
          <p className="text-xs text-muted-foreground italic py-1">
            Nenhuma operação em rascunho. Clique em &quot;Nova Conexão&quot; ou use os botões nos terminais para preparar fusões e desconexões. Nenhuma alteração é salva no banco até você clicar em &quot;Confirmar e Aplicar Lote&quot;.
          </p>
        ) : (
          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {draftOperations.map((op, idx) => {
              const termA = terminals.find((t) => t.id === op.terminal_a_id);
              const termB = op.terminal_b_id ? terminals.find((t) => t.id === op.terminal_b_id) : null;

              return (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded bg-background border border-border text-xs"
                >
                  <div className="flex items-center gap-2 truncate">
                    <Badge
                      variant={
                        op.action === "connect"
                          ? "default"
                          : op.action === "disconnect"
                          ? "destructive"
                          : "outline"
                      }
                      className="text-[10px] uppercase font-mono shrink-0"
                    >
                      {op.action}
                    </Badge>
                    <span className="font-semibold text-foreground truncate">
                      {termA?.label || op.terminal_a_id}
                    </span>
                    {op.terminal_b_id && (
                      <>
                        <span className="text-muted-foreground">→</span>
                        <span className="font-semibold text-foreground truncate">
                          {termB?.label || op.terminal_b_id}
                        </span>
                      </>
                    )}
                    {op.connection_type && (
                      <span className="text-[10px] text-muted-foreground">
                        ({op.connection_type.replace("_", " ")}, {op.loss_db} dB)
                      </span>
                    )}
                    {op.reservation_reason && (
                      <span className="text-[10px] text-muted-foreground italic">
                        Motivo: &quot;{op.reservation_reason}&quot;
                      </span>
                    )}
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive shrink-0"
                    onClick={() => handleRemoveDraftOperation(idx)}
                    title="Remover esta operação do rascunho local"
                    aria-label={`Remover operação ${idx + 1} do rascunho`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modais de Ação */}
      <ConnectionModal
        open={isConnectionModalOpen}
        onOpenChange={setIsConnectionModalOpen}
        terminals={terminals}
        initialTerminalAId={selectedTerminalAId}
        occupiedTerminalIds={occupiedTerminalIds}
        onAddOperation={handleAddOperation}
      />

      <DisconnectDialog
        open={Boolean(disconnectModalConn)}
        onOpenChange={(open) => !open && setDisconnectModalConn(null)}
        connection={disconnectModalConn}
        terminals={terminals}
        onAddOperation={handleAddOperation}
      />

      <ReservationDialog
        open={Boolean(reservationModalTerminal)}
        onOpenChange={(open) => !open && setReservationModalTerminal(null)}
        terminal={reservationModalTerminal}
        onAddOperation={handleAddOperation}
      />

      <TopologyConflictDialog
        open={conflictDialogOpen}
        onOpenChange={setConflictDialogOpen}
        expectedRevision={lastExpectedRevision}
        serverRevision={connectivity?.topology_revision}
        draftOperationsCount={draftOperations.length}
        onReconcile={handleReconcile}
      />
    </div>
  );

  // Renderiza cartão de terminal individual
  function renderTerminalCard(t: TerminalRead) {
    const isOccupied = occupiedTerminalIds.has(t.id);
    const isReserved = reservations.some((r) => r.terminal_id === t.id && r.is_active);
    const conn = terminalConnectionMap.get(t.id);
    const otherTermId = conn ? (conn.terminal_a_id === t.id ? conn.terminal_b_id : conn.terminal_a_id) : null;
    const otherTerm = otherTermId ? terminals.find((x) => x.id === otherTermId) : null;

    return (
      <div
        key={t.id}
        className="p-2.5 rounded-md border border-border bg-background hover:bg-muted/10 transition-colors text-xs space-y-1.5"
      >
        <div className="flex items-center justify-between gap-1">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              className={`h-2.5 w-2.5 rounded-full shrink-0 ${
                isOccupied
                  ? "bg-amber-500"
                  : isReserved
                  ? "bg-purple-500"
                  : "bg-emerald-500"
              }`}
              aria-hidden="true"
            />
            <p className="font-semibold text-foreground truncate" title={t.label}>
              {t.label}
            </p>
          </div>
          <Badge variant="outline" className="text-[9px] shrink-0">
            {formatTerminalKind(t.kind)}
          </Badge>
        </div>

        <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
          <span className="font-mono text-[10px] truncate max-w-[120px]">
            ID: {t.id}
          </span>
          <StatusBadge status={isOccupied ? "connected" : isReserved ? "reserved" : "free"} />
        </div>

        {/* Informação de Conexão Ativa ou Ações */}
        {conn && otherTerm ? (
          <div className="pt-1.5 border-t border-border/50 flex items-center justify-between text-[11px]">
            <span className="text-muted-foreground truncate max-w-[160px]" title={`Conectado a ${otherTerm.label}`}>
              → {otherTerm.label} ({conn.loss_db} dB)
            </span>
            <Button
              size="sm"
              variant="ghost"
              className="h-5 px-1.5 text-[10px] text-destructive hover:bg-destructive/10"
              onClick={() => setDisconnectModalConn(conn)}
            >
              <Unlink className="h-3 w-3 mr-1" />
              Desconectar
            </Button>
          </div>
        ) : !isOccupied ? (
          <div className="pt-1.5 border-t border-border/50 flex items-center justify-end gap-1.5">
            <Button
              size="sm"
              variant="outline"
              className="h-6 px-2 text-[11px]"
              onClick={() => {
                setSelectedTerminalAId(t.id);
                setIsConnectionModalOpen(true);
              }}
            >
              <Zap className="h-3 w-3 mr-1 text-amber-500" />
              Conectar
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 px-2 text-[11px]"
              onClick={() => setReservationModalTerminal(t)}
            >
              <Bookmark className="h-3 w-3 mr-1 text-primary" />
              Reservar
            </Button>
          </div>
        ) : null}
      </div>
    );
  }
}
