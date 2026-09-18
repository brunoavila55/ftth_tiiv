"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  User,
  Cable,
  Bookmark,
  AlertTriangle,
  LayoutGrid,
  List,
  Search,
  RefreshCw,
  Plus,
  ExternalLink,
  PowerOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { getCtoOccupancy, deactivateServiceLink } from "../api";
import { ServiceLinkDialog } from "./service-link-dialog";
import type { CtoPortDetail, CtoPortStatus } from "../types";

interface CtoPortsGridProps {
  structureId: string;
  structureCode: string;
}

export function CtoPortsGrid({ structureId, structureCode }: CtoPortsGridProps) {
  const queryClient = useQueryClient();
  const [filterStatus, setFilterStatus] = React.useState<string>("all");
  const [searchQuery, setSearchQuery] = React.useState<string>("");
  const [viewMode, setViewMode] = React.useState<"grid" | "table">("grid");

  // Porta selecionada para ver detalhes / ações
  const [selectedPort, setSelectedPort] = React.useState<CtoPortDetail | null>(null);

  // Modais de ativação e desativação
  const [serviceLinkDialogOpen, setServiceLinkDialogOpen] = React.useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = React.useState(false);
  const [deactivatingLink, setDeactivatingLink] = React.useState<{ id: string; version: number } | null>(null);
  const [feedbackMessage, setFeedbackMessage] = React.useState<{ type: "success" | "error"; text: string } | null>(null);

  // Consulta de ocupação em tempo real
  const { data: occupancy, isRefetching, refetch } = useQuery({
    queryKey: ["structures", structureId, "cto-occupancy"],
    queryFn: () => getCtoOccupancy(structureId),
    staleTime: 10_000,
  });

  const ports = React.useMemo(() => occupancy?.ports || [], [occupancy]);

  // Filtragem de portas
  const filteredPorts = React.useMemo(() => {
    return ports.filter((port) => {
      // Filtro de status
      if (filterStatus === "free" && port.status !== "free") return false;
      if (filterStatus === "customer_connected" && port.status !== "customer_connected") return false;
      if (filterStatus === "connected_no_customer" && port.status !== "connected_no_customer") return false;
      if (filterStatus === "connected" && port.status !== "customer_connected" && port.status !== "connected_no_customer") return false;
      if (filterStatus === "reserved" && port.status !== "reserved") return false;
      if (filterStatus === "damaged" && !port.is_damaged) return false;

      // Busca textual
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = port.name.toLowerCase().includes(q);
        const matchesCustomer = port.customer?.name.toLowerCase().includes(q) || port.customer?.code.toLowerCase().includes(q);
        const matchesOnu = port.onu?.code.toLowerCase().includes(q) || port.onu?.serial_number?.toLowerCase().includes(q);
        return matchesName || matchesCustomer || matchesOnu;
      }

      return true;
    });
  }, [ports, filterStatus, searchQuery]);

  // Mutação para desativar atendimento com preservação de histórico
  const deactivateMutation = useMutation({
    mutationFn: ({ linkId, version }: { linkId: string; version: number }) =>
      deactivateServiceLink(linkId, version),
    onSuccess: () => {
      setFeedbackMessage({
        type: "success",
        text: "Atendimento óptico desativado com sucesso. O histórico foi preservado.",
      });
      setSelectedPort(null);
      setDeactivateDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ["structures", structureId, "cto-occupancy"] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Erro ao desativar atendimento.";
      setFeedbackMessage({ type: "error", text: msg });
    },
  });

  const handleOpenDeactivate = (port: CtoPortDetail) => {
    if (port.service_link) {
      setDeactivatingLink({ id: port.service_link.id, version: port.service_link.version });
      setDeactivateDialogOpen(true);
    }
  };

  const handleConfirmDeactivate = () => {
    if (deactivatingLink) {
      deactivateMutation.mutate({ linkId: deactivatingLink.id, version: deactivatingLink.version });
    }
  };

  const getStatusBadge = (status: CtoPortStatus) => {
    switch (status) {
      case "free":
        return (
          <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white gap-1 text-[10px] font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
            <span>Livre</span>
          </Badge>
        );
      case "customer_connected":
        return (
          <Badge className="bg-sky-600 hover:bg-sky-600 text-white gap-1 text-[10px] font-medium">
            <User className="h-3 w-3" />
            <span>Conectada ao Cliente</span>
          </Badge>
        );
      case "connected_no_customer":
        return (
          <Badge className="bg-amber-600 hover:bg-amber-600 text-white gap-1 text-[10px] font-medium">
            <Cable className="h-3 w-3" />
            <span>Conectada sem Cliente</span>
          </Badge>
        );
      case "reserved":
        return (
          <Badge className="bg-purple-600 hover:bg-purple-600 text-white gap-1 text-[10px] font-medium">
            <Bookmark className="h-3 w-3" />
            <span>Reservada</span>
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Banner de Mensagens / Feedback */}
      {feedbackMessage && (
        <div
          role="alert"
          className={`flex items-center justify-between p-3 rounded-lg border text-xs ${
            feedbackMessage.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-950/40 dark:border-emerald-800 dark:text-emerald-300"
              : "bg-destructive/10 border-destructive/20 text-destructive"
          }`}
        >
          <span>{feedbackMessage.text}</span>
          <button
            type="button"
            onClick={() => setFeedbackMessage(null)}
            className="text-xs underline hover:opacity-80 ml-2"
          >
            Fechar
          </button>
        </div>
      )}

      {/* PAINEL SUPERIOR: RESUMO DE OCUPAÇÃO DA CTO */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        <div className="rounded-lg border border-border bg-card p-3 flex flex-col">
          <span className="text-[11px] text-muted-foreground uppercase font-semibold">
            Total de Portas
          </span>
          <span className="text-xl font-bold font-mono text-foreground">
            {occupancy ? occupancy.total_ports : "—"}
          </span>
          <span className="text-[10px] text-muted-foreground mt-0.5">Capacidade física</span>
        </div>

        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 flex flex-col">
          <span className="text-[11px] text-emerald-700 dark:text-emerald-400 uppercase font-semibold">
            Portas Livres
          </span>
          <span className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {occupancy ? occupancy.free_ports : "—"}
          </span>
          <span className="text-[10px] text-muted-foreground mt-0.5">Prontas p/ atendimento</span>
        </div>

        <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-3 flex flex-col">
          <span className="text-[11px] text-sky-700 dark:text-sky-400 uppercase font-semibold">
            Conectadas
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-bold font-mono text-sky-600 dark:text-sky-400">
              {occupancy ? occupancy.occupied_ports : "—"}
            </span>
            {occupancy && occupancy.connected_without_customer > 0 && (
              <span className="text-[10px] text-amber-600 dark:text-amber-400 font-mono">
                ({occupancy.connected_without_customer} s/ cliente)
              </span>
            )}
          </div>
          <span className="text-[10px] text-muted-foreground mt-0.5">Circuitos drop ativos</span>
        </div>

        <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3 flex flex-col">
          <span className="text-[11px] text-purple-700 dark:text-purple-400 uppercase font-semibold">
            Reservadas
          </span>
          <span className="text-xl font-bold font-mono text-purple-600 dark:text-purple-400">
            {occupancy ? occupancy.reserved_ports : "—"}
          </span>
          <span className="text-[10px] text-muted-foreground mt-0.5">Reserva técnica</span>
        </div>

        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 flex flex-col">
          <span className="text-[11px] text-destructive uppercase font-semibold">Danificadas</span>
          <span className="text-xl font-bold font-mono text-destructive">
            {ports.filter((p) => p.is_damaged).length}
          </span>
          <span className="text-[10px] text-muted-foreground mt-0.5">Condição física</span>
        </div>
      </div>

      {/* BARRA DE FILTROS E AÇÕES */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setFilterStatus("all")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              filterStatus === "all"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Todas ({ports.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus("free")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              filterStatus === "free"
                ? "bg-emerald-600 text-white"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Livres ({occupancy?.free_ports ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus("customer_connected")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              filterStatus === "customer_connected"
                ? "bg-sky-600 text-white"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Com Cliente
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus("connected_no_customer")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              filterStatus === "connected_no_customer"
                ? "bg-amber-600 text-white"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Sem Cliente ({occupancy?.connected_without_customer ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus("reserved")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              filterStatus === "reserved"
                ? "bg-purple-600 text-white"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Reservadas ({occupancy?.reserved_ports ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus("damaged")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              filterStatus === "damaged"
                ? "bg-destructive text-destructive-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Danificadas ({ports.filter((p) => p.is_damaged).length})
          </button>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative flex-1 sm:w-48">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Buscar porta ou cliente..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-7 pl-8 text-xs"
            />
          </div>

          <div className="flex items-center border border-border rounded-md p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              className={`p-1 rounded ${viewMode === "grid" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              title="Grade de Portas"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`p-1 rounded ${viewMode === "table" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              title="Lista Acessível"
            >
              <List className="h-3.5 w-3.5" />
            </button>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
            className="h-7 w-7 p-0"
            title="Atualizar Ocupação"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
          </Button>

          <Button
            type="button"
            size="sm"
            onClick={() => {
              setSelectedPort(null);
              setServiceLinkDialogOpen(true);
            }}
            className="h-7 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Novo Atendimento</span>
          </Button>
        </div>
      </div>

      {/* MODO 1: GRADE VISUAL DE PORTAS NUMERADAS (1..N) */}
      {viewMode === "grid" && (
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-4 lg:grid-cols-4 gap-3">
          {filteredPorts.length > 0 ? (
            filteredPorts.map((port) => {
              const isSelected = selectedPort?.id === port.id;
              const isCustomer = port.status === "customer_connected";
              const isNoCustomer = port.status === "connected_no_customer";
              const isReserved = port.status === "reserved";

              return (
                <button
                  type="button"
                  key={port.id}
                  onClick={() => setSelectedPort(port)}
                  className={`relative p-3 rounded-xl border text-left flex flex-col justify-between transition-all duration-150 hover:shadow-md ${
                    isSelected
                      ? "ring-2 ring-primary border-primary bg-card"
                      : isCustomer
                      ? "border-sky-500/40 bg-sky-500/5 hover:border-sky-500"
                      : isNoCustomer
                      ? "border-amber-500/40 bg-amber-500/5 hover:border-amber-500"
                      : isReserved
                      ? "border-purple-500/40 bg-purple-500/5 hover:border-purple-500"
                      : "border-emerald-500/40 bg-emerald-500/5 hover:border-emerald-500"
                  }`}
                >
                  {/* Cabeçalho da porta */}
                  <div className="flex items-start justify-between gap-1 w-full">
                    <div>
                      <div className="font-mono text-xs font-bold text-foreground">
                        {port.name}
                      </div>
                      <div className="text-[10px] font-mono text-muted-foreground">
                        {port.connector_type}
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1">
                      {getStatusBadge(port.status)}
                      {port.is_damaged && (
                        <Badge
                          variant="destructive"
                          className="text-[9px] py-0 px-1 gap-0.5 font-semibold"
                        >
                          <AlertTriangle className="h-2.5 w-2.5" />
                          <span>Danificada</span>
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Corpo com identificação do cliente ou status */}
                  <div className="mt-3 pt-2 border-t border-border/40 text-xs min-h-[44px] flex flex-col justify-center">
                    {isCustomer && port.customer ? (
                      <div>
                        <div className="font-semibold text-foreground truncate text-xs">
                          {port.customer.name}
                        </div>
                        <div className="font-mono text-[10px] text-muted-foreground truncate">
                          {port.customer.code} • {port.onu?.code || "ONU"}
                        </div>
                      </div>
                    ) : isNoCustomer ? (
                      <div className="text-[11px] text-amber-700 dark:text-amber-300 italic">
                        Drop óptico sem assinante
                      </div>
                    ) : isReserved && port.reservation ? (
                      <div className="text-[11px] text-purple-700 dark:text-purple-300 truncate">
                        {port.reservation.reason}
                      </div>
                    ) : (
                      <div className="text-[11px] text-emerald-700 dark:text-emerald-400 font-medium">
                        Disponível para ativação
                      </div>
                    )}
                  </div>
                </button>
              );
            })
          ) : (
            <div className="col-span-full rounded-lg border border-dashed border-border p-8 text-center text-xs text-muted-foreground">
              Nenhuma porta encontrada com os filtros selecionados.
            </div>
          )}
        </div>
      )}

      {/* MODO 2: TABELA ACESSÍVEL */}
      {viewMode === "table" && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-xs text-left" role="table" aria-label="Lista de Portas da CTO">
            <thead className="bg-muted/50 text-muted-foreground uppercase text-[10px] border-b border-border">
              <tr>
                <th className="p-3">Porta</th>
                <th className="p-3">Conector</th>
                <th className="p-3">Status de Ocupação</th>
                <th className="p-3">Condição Física</th>
                <th className="p-3">Assinante / Detalhes</th>
                <th className="p-3 text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredPorts.length > 0 ? (
                filteredPorts.map((port) => (
                  <tr
                    key={port.id}
                    className="hover:bg-muted/40 transition-colors cursor-pointer"
                    onClick={() => setSelectedPort(port)}
                  >
                    <td className="p-3 font-mono font-bold text-foreground">{port.name}</td>
                    <td className="p-3 font-mono text-muted-foreground">{port.connector_type}</td>
                    <td className="p-3">{getStatusBadge(port.status)}</td>
                    <td className="p-3">
                      {port.is_damaged ? (
                        <Badge variant="destructive" className="text-[10px]">
                          Danificada
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground text-[11px]">Normal</span>
                      )}
                    </td>
                    <td className="p-3">
                      {port.customer ? (
                        <div>
                          <div className="font-semibold text-foreground">{port.customer.name}</div>
                          <div className="font-mono text-[11px] text-muted-foreground">
                            {port.customer.code} • {port.onu?.code}
                          </div>
                        </div>
                      ) : port.status === "connected_no_customer" ? (
                        <span className="text-amber-600 dark:text-amber-400 italic">
                          Conexão drop sem cliente
                        </span>
                      ) : port.reservation ? (
                        <span className="text-purple-600 dark:text-purple-400">
                          {port.reservation.reason}
                        </span>
                      ) : (
                        <span className="text-emerald-600 dark:text-emerald-400">Livre</span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedPort(port);
                        }}
                        className="h-6 text-xs px-2"
                      >
                        Ver Detalhes
                      </Button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-muted-foreground">
                    Nenhuma porta encontrada.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* DIALOG DE DETALHES DA PORTA CLICADA */}
      {selectedPort && (
        <Dialog open={Boolean(selectedPort)} onOpenChange={(open) => !open && setSelectedPort(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <div className="flex items-center justify-between pr-6">
                <DialogTitle className="text-base flex items-center gap-2">
                  <span>{selectedPort.name}</span>
                  <span className="font-mono text-xs font-normal text-muted-foreground">
                    ({structureCode})
                  </span>
                </DialogTitle>
                {getStatusBadge(selectedPort.status)}
              </div>
            </DialogHeader>

            <div className="space-y-4 text-xs py-1">
              {/* Informações Físicas da Porta */}
              <div className="rounded-lg border border-border bg-card p-3 space-y-2">
                <div className="text-[11px] font-semibold text-muted-foreground uppercase">
                  Parâmetros Físicos da Porta
                </div>
                <dl className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <dt className="text-muted-foreground">Tipo de Conector</dt>
                    <dd className="font-mono font-semibold text-foreground">
                      {selectedPort.connector_type}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Função / Role</dt>
                    <dd className="capitalize text-foreground">{selectedPort.role}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Condição Mecânica</dt>
                    <dd>
                      {selectedPort.is_damaged ? (
                        <Badge variant="destructive" className="text-[10px]">
                          Danificada / Com Defeito
                        </Badge>
                      ) : (
                        <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                          Operacional (OK)
                        </span>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Terminal ID</dt>
                    <dd className="font-mono text-[10px] text-muted-foreground truncate">
                      {selectedPort.terminal_id || "Interno"}
                    </dd>
                  </div>
                  {selectedPort.notes && (
                    <div className="col-span-2">
                      <dt className="text-muted-foreground">Notas da Porta</dt>
                      <dd className="italic text-foreground">{selectedPort.notes}</dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Se Conectada ao Cliente */}
              {selectedPort.status === "customer_connected" && selectedPort.customer && (
                <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-3 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-sky-700 dark:text-sky-300 uppercase">
                      Assinante Vinculado
                    </span>
                    <Link
                      href={`/customers/${selectedPort.customer.id}`}
                      className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
                    >
                      <span>Ficha do Cliente</span>
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  </div>

                  <dl className="grid grid-cols-2 gap-2 text-xs">
                    <div className="col-span-2">
                      <dt className="text-muted-foreground">Nome do Cliente</dt>
                      <dd className="font-semibold text-foreground text-sm">
                        {selectedPort.customer.name}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Código Assinante</dt>
                      <dd className="font-mono text-foreground font-semibold">
                        {selectedPort.customer.code}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Telefone</dt>
                      <dd className="text-foreground">{selectedPort.customer.phone || "—"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Equipamento ONU</dt>
                      <dd className="font-mono text-foreground font-semibold">
                        {selectedPort.onu?.code || "ONU Padrão"}
                      </dd>
                      {selectedPort.onu?.serial_number && (
                        <dd className="font-mono text-[10px] text-muted-foreground">
                          SN: {selectedPort.onu.serial_number}
                        </dd>
                      )}
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Ativado em</dt>
                      <dd className="text-foreground">
                        {selectedPort.service_link
                          ? new Date(selectedPort.service_link.activated_at).toLocaleDateString("pt-BR")
                          : "—"}
                      </dd>
                    </div>
                  </dl>

                  <div className="pt-2 border-t border-sky-500/20 flex justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => handleOpenDeactivate(selectedPort)}
                      className="text-xs text-destructive hover:bg-destructive/10 border-destructive/30 gap-1.5"
                    >
                      <PowerOff className="h-3 w-3" />
                      <span>Desativar Atendimento</span>
                    </Button>
                  </div>
                </div>
              )}

              {/* Se Conectada sem Cliente */}
              {selectedPort.status === "connected_no_customer" && (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 space-y-2">
                  <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300 font-semibold text-xs">
                    <AlertTriangle className="h-4 w-4" />
                    <span>Drop conectado sem cliente associado</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Esta porta já possui uma conexão física (cabo drop ou patch cord), porém nenhum
                    assinante foi provisionado a ela no sistema.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => {
                      setServiceLinkDialogOpen(true);
                    }}
                    className="w-full text-xs gap-1 mt-1 bg-amber-600 hover:bg-amber-700 text-white"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Vincular Assinante a esta Porta</span>
                  </Button>
                </div>
              )}

              {/* Se Reservada */}
              {selectedPort.status === "reserved" && (
                <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3 space-y-2">
                  <div className="text-[11px] font-semibold text-purple-700 dark:text-purple-300 uppercase">
                    Reserva Técnica
                  </div>
                  <dl className="space-y-1.5 text-xs">
                    <div>
                      <dt className="text-muted-foreground">Motivo da Reserva</dt>
                      <dd className="font-semibold text-foreground">
                        {selectedPort.reservation?.reason || "Reserva técnica administrativa"}
                      </dd>
                    </div>
                    {selectedPort.reservation?.reserved_by && (
                      <div>
                        <dt className="text-muted-foreground">Responsável</dt>
                        <dd className="text-foreground">{selectedPort.reservation.reserved_by}</dd>
                      </div>
                    )}
                    {selectedPort.reservation?.expires_at && (
                      <div>
                        <dt className="text-muted-foreground">Expiração</dt>
                        <dd className="text-foreground">
                          {new Date(selectedPort.reservation.expires_at).toLocaleString("pt-BR")}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}

              {/* Se Livre */}
              {selectedPort.status === "free" && (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 space-y-2.5">
                  <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-semibold text-xs">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Porta Livre para Atendimento</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Esta porta frontal está disponível para nova ativação de assinante.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => {
                      setServiceLinkDialogOpen(true);
                    }}
                    className="w-full text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Ativar Assinante nesta Porta</span>
                  </Button>
                </div>
              )}
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSelectedPort(null)}
              >
                Fechar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* DIALOG DE CONFIRMAÇÃO DE DESATIVAÇÃO (PRESERVA HISTÓRICO) */}
      <ConfirmDialog
        open={deactivateDialogOpen}
        onOpenChange={setDeactivateDialogOpen}
        title="Desativar Atendimento ao Assinante"
        description="Atenção: Esta ação encerrará o atendimento óptico nesta porta e liberará a porta da CTO para outros assinantes. O registro histórico será mantido com a data e hora do encerramento."
        confirmLabel="Desativar Atendimento"
        cancelLabel="Manter Ativo"
        variant="destructive"
        onConfirm={handleConfirmDeactivate}
        isLoading={deactivateMutation.isPending}
      />

      {/* MODAL DE ATIVAÇÃO DE ATENDIMENTO */}
      <ServiceLinkDialog
        open={serviceLinkDialogOpen}
        onOpenChange={setServiceLinkDialogOpen}
        structureId={structureId}
        structureCode={structureCode}
        selectedPort={selectedPort}
        availablePorts={ports}
        onSuccess={() => {
          setFeedbackMessage({
            type: "success",
            text: "Atendimento óptico ativado com sucesso!",
          });
          setSelectedPort(null);
          queryClient.invalidateQueries({ queryKey: ["structures", structureId, "cto-occupancy"] });
          queryClient.invalidateQueries({ queryKey: ["customers"] });
        }}
      />
    </div>
  );
}
