"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Phone,
  Mail,
  MapPin,
  FileText,
  PowerOff,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  Edit,
  Trash2,
  Calculator,
  Route,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { LoadingState, ErrorState } from "@/components/ui/state-displays";
import { getCustomer, listServiceLinks, deactivateServiceLink, deleteCustomer } from "../api";
import { CustomerFormDialog } from "./customer-form-dialog";
import type { ServiceLinkRead } from "../types";

interface CustomerDetailViewProps {
  customerId: string;
}

export function CustomerDetailView({ customerId }: CustomerDetailViewProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = React.useState(false);
  const [linkToDeactivate, setLinkToDeactivate] = React.useState<ServiceLinkRead | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  // Consulta dados do cliente
  const {
    data: customer,
    isLoading: isLoadingCustomer,
    error: customerError,
    refetch: refetchCustomer,
  } = useQuery({
    queryKey: ["customers", customerId],
    queryFn: () => getCustomer(customerId),
  });

  // Consulta atendimentos vinculados a este cliente
  const {
    data: serviceLinksData,
    refetch: refetchLinks,
  } = useQuery({
    queryKey: ["service-links", "by-customer", customerId],
    queryFn: () => listServiceLinks({ customer_id: customerId, page_size: 100 }),
    enabled: Boolean(customerId),
  });

  const links = serviceLinksData?.items || [];
  const activeLinks = links.filter((l) => l.status === "active");
  const inactiveLinks = links.filter((l) => l.status !== "active");

  // Mutação para desativar atendimento óptico (preserva histórico)
  const deactivateMutation = useMutation({
    mutationFn: ({ linkId, version }: { linkId: string; version: number }) =>
      deactivateServiceLink(linkId, version),
    onSuccess: () => {
      setActionError(null);
      setDeactivateDialogOpen(false);
      setLinkToDeactivate(null);
      refetchLinks();
      queryClient.invalidateQueries({ queryKey: ["structures"] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Erro ao desativar atendimento.";
      setActionError(msg);
    },
  });

  // Mutação para excluir cliente (apenas sem atendimentos ativos)
  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!customer) throw new Error("Cliente não carregado");
      return deleteCustomer(customer.id, customer.version);
    },
    onSuccess: () => {
      router.push("/customers");
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Erro ao excluir cliente.";
      setActionError(msg);
      setDeleteDialogOpen(false);
    },
  });

  if (isLoadingCustomer) {
    return (
      <div className="py-12">
        <LoadingState message="Carregando ficha do assinante..." />
      </div>
    );
  }

  if (customerError || !customer) {
    return (
      <div className="py-12">
        <ErrorState
          title="Assinante não encontrado"
          error={customerError}
          onRetry={() => refetchCustomer()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cabeçalho de Navegação e Ações */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        <div className="flex items-center gap-3">
          <Link href="/customers">
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground">{customer.name}</h1>
              <Badge variant="outline" className="font-mono text-xs">
                {customer.code}
              </Badge>
              <Badge variant="secondary" className="font-mono text-[10px]">
                v{customer.version}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Assinante cadastrado em {new Date(customer.created_at).toLocaleDateString("pt-BR")}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setEditDialogOpen(true)}
            className="text-xs gap-1.5"
          >
            <Edit className="h-3.5 w-3.5" />
            <span>Editar Dados</span>
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setDeleteDialogOpen(true)}
            disabled={activeLinks.length > 0}
            title={
              activeLinks.length > 0
                ? "Não é possível excluir cliente com atendimentos ativos"
                : "Excluir cadastro do cliente"
            }
            className="text-xs gap-1.5 text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Excluir</span>
          </Button>
        </div>
      </div>

      {actionError && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="flex-1">{actionError}</div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-xs underline hover:opacity-80"
          >
            Dispensar
          </button>
        </div>
      )}

      {/* Grid de Informações Cadastrais */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Contato e Identificação */}
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-xs font-semibold text-foreground uppercase tracking-wide">
            Contato e Comunicação
          </h2>
          <dl className="space-y-2 text-xs">
            <div>
              <dt className="text-muted-foreground flex items-center gap-1">
                <Phone className="h-3 w-3" />
                <span>Telefone / WhatsApp</span>
              </dt>
              <dd className="font-semibold text-foreground pt-0.5">{customer.phone || "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground flex items-center gap-1">
                <Mail className="h-3 w-3" />
                <span>E-mail</span>
              </dt>
              <dd className="font-semibold text-foreground pt-0.5">{customer.email || "—"}</dd>
            </div>
          </dl>
        </div>

        {/* Card 2: Endereço de Instalação */}
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-xs font-semibold text-foreground uppercase tracking-wide flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5" />
            <span>Endereço de Instalação</span>
          </h2>
          <p className="text-xs text-foreground font-medium leading-relaxed">
            {customer.address || "Endereço não informado no cadastro."}
          </p>
        </div>

        {/* Card 3: Observações */}
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-xs font-semibold text-foreground uppercase tracking-wide flex items-center gap-1">
            <FileText className="h-3.5 w-3.5" />
            <span>Observações Cadastrais</span>
          </h2>
          <p className="text-xs text-foreground italic">
            {customer.notes || "Nenhuma observação técnica ou cadastral."}
          </p>
        </div>
      </div>

      {/* ATENDIMENTOS ÓPTICOS ATIVOS */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold">Atendimentos Ópticos Ativos</h2>
            <p className="text-xs text-muted-foreground">
              Portas e equipamentos atualmente provisionados para este assinante.
            </p>
          </div>
          <Badge className="bg-sky-600 hover:bg-sky-600 text-white font-mono text-xs">
            {activeLinks.length} ativo(s)
          </Badge>
        </div>

        {activeLinks.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {activeLinks.map((link) => (
              <div
                key={link.id}
                className="rounded-xl border border-sky-500/30 bg-sky-500/5 p-4 space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-sky-600" />
                    <span className="font-semibold text-xs text-foreground">Circuito Ativo</span>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    v{link.version}
                  </Badge>
                </div>

                <dl className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <dt className="text-muted-foreground">Porta da CTO</dt>
                    <dd className="font-mono font-bold text-foreground truncate">
                      ID: {link.port_id.slice(0, 8)}...
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Equipamento ONU</dt>
                    <dd className="font-mono font-bold text-foreground truncate">
                      ID: {link.onu_device_id.slice(0, 8)}...
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Data de Ativação</dt>
                    <dd className="text-foreground">
                      {new Date(link.activated_at).toLocaleString("pt-BR")}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Status</dt>
                    <dd>
                      <Badge className="bg-emerald-600 text-white text-[10px]">Ativo</Badge>
                    </dd>
                  </div>
                  {link.notes && (
                    <div className="col-span-2 pt-1 border-t border-sky-500/20">
                      <dt className="text-muted-foreground">Observações Técnicas</dt>
                      <dd className="text-foreground italic">{link.notes}</dd>
                    </div>
                  )}
                </dl>

                <div className="pt-2 border-t border-sky-500/20 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/optical-budget?serviceLinkId=${link.id}`}
                      className="inline-flex items-center gap-1.5 text-xs border rounded-md px-2.5 py-1 hover:bg-muted font-medium text-foreground transition-colors bg-background shadow-sm"
                    >
                      <Calculator className="h-3.5 w-3.5 text-primary" />
                      <span>Orçamento Óptico</span>
                    </Link>
                    <Link
                      href={`/topology?customerId=${customer.id}`}
                      className="inline-flex items-center gap-1.5 text-xs border rounded-md px-2.5 py-1 hover:bg-muted font-medium text-foreground transition-colors bg-background shadow-sm"
                    >
                      <Route className="h-3.5 w-3.5 text-sky-500" />
                      <span>Rastrear Caminho</span>
                    </Link>
                  </div>

                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setLinkToDeactivate(link);
                      setDeactivateDialogOpen(true);
                    }}
                    className="text-xs text-destructive hover:bg-destructive/10 border-destructive/30 gap-1.5"
                  >
                    <PowerOff className="h-3 w-3" />
                    <span>Desativar</span>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border p-8 text-center text-xs text-muted-foreground">
            Este assinante não possui nenhum atendimento óptico ativo no momento.
          </div>
        )}
      </div>

      {/* HISTÓRICO DE ATENDIMENTOS DESATIVADOS (PRESERVAÇÃO DO HISTÓRICO) */}
      {inactiveLinks.length > 0 && (
        <div className="space-y-3 pt-4 border-t border-border">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span>Histórico de Atendimentos Anteriores</span>
            </h2>
            <p className="text-xs text-muted-foreground">
              Registros históricos de atendimentos ópticos encerrados para auditoria técnica.
            </p>
          </div>

          <div className="rounded-lg border border-border divide-y divide-border bg-card">
            {inactiveLinks.map((link) => (
              <div key={link.id} className="p-3 flex items-center justify-between text-xs">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-muted-foreground">
                      Porta: {link.port_id.slice(0, 8)}... • ONU: {link.onu_device_id.slice(0, 8)}...
                    </span>
                    <Badge variant="secondary" className="text-[10px] capitalize">
                      {link.status}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Ativado em {new Date(link.activated_at).toLocaleDateString("pt-BR")} • Encerrado
                    em{" "}
                    {link.deactivated_at
                      ? new Date(link.deactivated_at).toLocaleString("pt-BR")
                      : "—"}
                  </div>
                </div>
                {link.notes && (
                  <span className="text-[11px] text-muted-foreground italic max-w-xs truncate">
                    {link.notes}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modal de Edição de Cliente */}
      <CustomerFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        customerToEdit={customer}
        onSuccess={() => {
          refetchCustomer();
        }}
      />

      {/* Modal de Confirmação de Desativação */}
      <ConfirmDialog
        open={deactivateDialogOpen}
        onOpenChange={setDeactivateDialogOpen}
        title="Desativar Atendimento Óptico"
        description="Esta ação desligará o serviço do assinante nesta porta da CTO. O histórico permanecerá registrado para consultas futuras."
        confirmLabel="Confirmar Desativação"
        cancelLabel="Cancelar"
        variant="destructive"
        onConfirm={() => {
          if (linkToDeactivate) {
            deactivateMutation.mutate({
              linkId: linkToDeactivate.id,
              version: linkToDeactivate.version,
            });
          }
        }}
        isLoading={deactivateMutation.isPending}
      />

      {/* Modal de Exclusão de Cliente */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Excluir Cadastro do Assinante"
        description={`Tem certeza que deseja excluir o cadastro de ${customer.name}? Esta ação não pode ser desfeita.`}
        confirmLabel="Excluir Definitivamente"
        cancelLabel="Voltar"
        variant="destructive"
        onConfirm={() => deleteMutation.mutate()}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
