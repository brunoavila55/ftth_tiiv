"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Plus, User, Router, CheckCircle2, AlertTriangle, ArrowRight } from "lucide-react";
import { createServiceLink, listCustomers, listAvailableOnus } from "../api";
import { CustomerFormDialog } from "./customer-form-dialog";
import type { CustomerRead, ServiceLinkRead, CtoPortDetail } from "../types";
import type { DeviceRead } from "../../inventory/api";

interface ServiceLinkDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  structureId?: string;
  structureCode: string;
  selectedPort?: CtoPortDetail | null;
  availablePorts?: CtoPortDetail[];
  onSuccess: (link: ServiceLinkRead) => void;
}

export function ServiceLinkDialog({
  open,
  onOpenChange,
  structureCode,
  selectedPort,
  availablePorts = [],
  onSuccess,
}: ServiceLinkDialogProps) {
  const [step, setStep] = React.useState<1 | 2 | 3 | 4>(1);
  const [selectedCustomerId, setSelectedCustomerId] = React.useState<string>("");
  const [targetPortId, setTargetPortId] = React.useState<string>(selectedPort?.id || "");
  const [selectedOnuId, setSelectedOnuId] = React.useState<string>("");
  const [notes, setNotes] = React.useState<string>("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [customerDialogOpen, setCustomerDialogOpen] = React.useState(false);
  const [customerSearch, setCustomerSearch] = React.useState("");

  // Carrega clientes
  const { data: customersData, refetch: refetchCustomers } = useQuery({
    queryKey: ["customers", "list", customerSearch],
    queryFn: () => listCustomers({ q: customerSearch, page_size: 50 }),
    enabled: open,
  });

  // Carrega ONUs disponíveis
  const { data: onusData } = useQuery({
    queryKey: ["devices", "onus"],
    queryFn: () => listAvailableOnus(),
    enabled: open,
  });

  const onus = React.useMemo(() => {
    return (onusData?.items || []).filter((d) => d.kind === "onu");
  }, [onusData]);

  // Sincroniza porta inicial
  React.useEffect(() => {
    if (selectedPort?.id) {
      setTargetPortId(selectedPort.id);
    } else if (availablePorts.length > 0 && !targetPortId) {
      const freePort = availablePorts.find((p) => p.status === "free");
      if (freePort) {
        setTargetPortId(freePort.id);
      }
    }
  }, [selectedPort, availablePorts, targetPortId]);

  // Reseta estado ao abrir
  React.useEffect(() => {
    if (open) {
      setStep(1);
      setErrorMessage(null);
      setNotes("");
      if (selectedPort?.id) {
        setTargetPortId(selectedPort.id);
      }
    }
  }, [open, selectedPort]);

  const selectedCustomer = (customersData?.items || []).find((c) => c.id === selectedCustomerId);
  const targetPort = (availablePorts || []).find((p) => p.id === targetPortId) || selectedPort;
  const selectedOnu = onus.find((d) => d.id === selectedOnuId);

  const handleCustomerCreated = (newCust: CustomerRead) => {
    refetchCustomers();
    setSelectedCustomerId(newCust.id);
  };

  const handleSubmit = async () => {
    if (!selectedCustomerId || !targetPortId || !selectedOnuId) {
      setErrorMessage("Por favor, preencha todos os campos obrigatórios.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const link = await createServiceLink({
        customer_id: selectedCustomerId,
        port_id: targetPortId,
        onu_device_id: selectedOnuId,
        notes: notes || null,
      });
      onSuccess(link);
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao ativar atendimento óptico.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <div className="flex items-center justify-between pr-6">
              <DialogTitle className="text-base">Ativação de Atendimento ao Assinante</DialogTitle>
              <Badge variant="outline" className="font-mono text-xs">
                {structureCode}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Passo {step} de 4:{" "}
              {step === 1 && "Identificação do Assinante"}
              {step === 2 && "Porta Óptica na CTO"}
              {step === 3 && "Equipamento ONU do Cliente"}
              {step === 4 && "Revisão e Confirmação"}
            </p>
          </DialogHeader>

          {errorMessage && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive"
            >
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>{errorMessage}</div>
            </div>
          )}

          {/* PASSO 1: SELECIONAR OU CADASTRAR CLIENTE */}
          {step === 1 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold">Selecione o Assinante</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCustomerDialogOpen(true)}
                  className="gap-1 text-xs h-7"
                >
                  <Plus className="h-3 w-3" />
                  <span>Cadastrar Novo Cliente</span>
                </Button>
              </div>

              <div className="space-y-2">
                <Input
                  placeholder="Buscar cliente por nome ou código..."
                  value={customerSearch}
                  onChange={(e) => setCustomerSearch(e.target.value)}
                  className="text-xs"
                />

                <div className="max-h-48 overflow-y-auto rounded-lg border border-border divide-y divide-border">
                  {customersData?.items && customersData.items.length > 0 ? (
                    customersData.items.map((cust) => {
                      const isSelected = cust.id === selectedCustomerId;
                      return (
                        <button
                          type="button"
                          key={cust.id}
                          onClick={() => setSelectedCustomerId(cust.id)}
                          className={`w-full p-2.5 text-left flex items-center justify-between hover:bg-muted/50 transition-colors text-xs ${
                            isSelected ? "bg-primary/10 font-semibold" : ""
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <User className="h-3.5 w-3.5 text-muted-foreground" />
                            <div>
                              <div className="text-foreground">{cust.name}</div>
                              <div className="text-[11px] text-muted-foreground font-mono">
                                {cust.code} {cust.phone ? `• ${cust.phone}` : ""}
                              </div>
                            </div>
                          </div>
                          {isSelected && <CheckCircle2 className="h-4 w-4 text-primary" />}
                        </button>
                      );
                    })
                  ) : (
                    <div className="p-4 text-center text-xs text-muted-foreground">
                      Nenhum assinante encontrado. Clique no botão acima para cadastrar.
                    </div>
                  )}
                </div>
              </div>

              {selectedCustomer && (
                <div className="rounded-md border border-primary/20 bg-primary/5 p-2.5 text-xs">
                  <div className="text-[11px] font-semibold text-primary uppercase">
                    Cliente Selecionado
                  </div>
                  <div className="font-semibold text-foreground">{selectedCustomer.name}</div>
                  <div className="text-muted-foreground font-mono text-[11px]">
                    {selectedCustomer.code} {selectedCustomer.address ? `• ${selectedCustomer.address}` : ""}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* PASSO 2: PORTA DA CTO */}
          {step === 2 && (
            <div className="space-y-4 py-2">
              <div>
                <Label className="text-xs font-semibold">Porta Óptica de Atendimento (CTO)</Label>
                <p className="text-[11px] text-muted-foreground">
                  Selecione uma porta frontal livre para o drop deste assinante.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2 max-h-56 overflow-y-auto p-1">
                {availablePorts.map((port) => {
                  const isSelected = port.id === targetPortId;
                  const isFree = port.status === "free";
                  return (
                    <button
                      type="button"
                      key={port.id}
                      disabled={!isFree && !isSelected}
                      onClick={() => setTargetPortId(port.id)}
                      className={`p-3 rounded-lg border text-left flex flex-col justify-between transition-colors text-xs ${
                        isSelected
                          ? "border-primary bg-primary/10 shadow-sm"
                          : isFree
                          ? "border-border hover:border-muted-foreground bg-card"
                          : "border-border/50 bg-muted/40 opacity-50 cursor-not-allowed"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full mb-1">
                        <span className="font-mono font-bold text-xs">{port.name}</span>
                        {isSelected && <CheckCircle2 className="h-3.5 w-3.5 text-primary" />}
                      </div>
                      <div className="text-[10px] font-mono text-muted-foreground">
                        {port.connector_type}
                      </div>
                      <div className="mt-1">
                        <Badge
                          variant={isFree ? "default" : "secondary"}
                          className={`text-[9px] py-0 px-1.5 ${
                            isFree ? "bg-emerald-600 hover:bg-emerald-600" : ""
                          }`}
                        >
                          {port.status === "free" ? "Disponível" : port.status}
                        </Badge>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* PASSO 3: ONU DO CLIENTE */}
          {step === 3 && (
            <div className="space-y-4 py-2">
              <div>
                <Label className="text-xs font-semibold">Equipamento ONU / ONT</Label>
                <p className="text-[11px] text-muted-foreground">
                  Selecione a ONU que será instalada ou já se encontra na casa do cliente.
                </p>
              </div>

              <div className="max-h-52 overflow-y-auto rounded-lg border border-border divide-y divide-border">
                {onus.length > 0 ? (
                  onus.map((device: DeviceRead) => {
                    const isSelected = device.id === selectedOnuId;
                    return (
                      <button
                        type="button"
                        key={device.id}
                        onClick={() => setSelectedOnuId(device.id)}
                        className={`w-full p-2.5 text-left flex items-center justify-between hover:bg-muted/50 transition-colors text-xs ${
                          isSelected ? "bg-primary/10 font-semibold" : ""
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Router className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <div className="text-foreground font-mono">{device.code}</div>
                            <div className="text-[11px] text-muted-foreground">
                              {device.model || "Modelo Padrão"} {device.serial_number ? `• SN: ${device.serial_number}` : ""}
                            </div>
                          </div>
                        </div>
                        {isSelected && <CheckCircle2 className="h-4 w-4 text-primary" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-4 text-center text-xs text-muted-foreground">
                    Nenhuma ONU disponível no inventário. Cadastre uma ONU em Equipamentos.
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="step-notes" className="text-xs">
                  Observações Técnicas / Notas do Drop
                </Label>
                <Input
                  id="step-notes"
                  placeholder="Ex: Drop de 80m, conector SC/APC montado em campo, potência -19.2 dBm"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="text-xs"
                />
              </div>
            </div>
          )}

          {/* PASSO 4: REVISÃO E CONFIRMAÇÃO */}
          {step === 4 && (
            <div className="space-y-3 py-2 text-xs">
              <div className="rounded-lg border border-border bg-card p-3 space-y-2">
                <div className="text-[11px] font-semibold text-muted-foreground uppercase">
                  Resumo do Atendimento Óptico
                </div>
                <dl className="grid grid-cols-2 gap-2">
                  <div>
                    <dt className="text-muted-foreground">Assinante</dt>
                    <dd className="font-semibold text-foreground">{selectedCustomer?.name}</dd>
                    <dd className="font-mono text-[11px] text-muted-foreground">
                      {selectedCustomer?.code}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">CTO / Porta</dt>
                    <dd className="font-semibold text-foreground">
                      {structureCode} • {targetPort?.name}
                    </dd>
                    <dd className="font-mono text-[11px] text-muted-foreground">
                      Conector: {targetPort?.connector_type}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Equipamento ONU</dt>
                    <dd className="font-mono font-semibold text-foreground">{selectedOnu?.code}</dd>
                    <dd className="text-[11px] text-muted-foreground">
                      {selectedOnu?.model || "ONU Óptica"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Status da Ativação</dt>
                    <dd>
                      <Badge className="bg-emerald-600 hover:bg-emerald-600 text-[10px]">
                        Ativação Imediata
                      </Badge>
                    </dd>
                  </div>
                  {notes && (
                    <div className="col-span-2">
                      <dt className="text-muted-foreground">Observações Técnicas</dt>
                      <dd className="italic text-foreground">{notes}</dd>
                    </div>
                  )}
                </dl>
              </div>

              <div className="rounded-md border border-amber-500/20 bg-amber-500/10 p-2.5 text-[11px] text-amber-900 dark:text-amber-200">
                Aviso: A porta selecionada será vinculada exclusivamente a este assinante.
                Concorrência na mesma porta ou ONU será bloqueada com verificação transacional.
              </div>
            </div>
          )}

          <DialogFooter className="pt-2 flex items-center justify-between">
            {step > 1 ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setStep((s) => (s - 1) as 1 | 2 | 3 | 4)}
                disabled={isSubmitting}
              >
                Voltar
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancelar
              </Button>
            )}

            {step < 4 ? (
              <Button
                type="button"
                size="sm"
                onClick={() => setStep((s) => (s + 1) as 1 | 2 | 3 | 4)}
                disabled={
                  (step === 1 && !selectedCustomerId) ||
                  (step === 2 && !targetPortId) ||
                  (step === 3 && !selectedOnuId)
                }
                className="gap-1.5"
              >
                <span>Avançar</span>
                <ArrowRight className="h-3 w-3" />
              </Button>
            ) : (
              <Button
                type="button"
                size="sm"
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>{isSubmitting ? "Ativando..." : "Confirmar Ativação"}</span>
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal de cadastro de cliente inline sem fechar fluxo */}
      <CustomerFormDialog
        open={customerDialogOpen}
        onOpenChange={setCustomerDialogOpen}
        onSuccess={handleCustomerCreated}
      />
    </>
  );
}
