"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/types";
import type { PortRead } from "@/features/inventory/api";
import { createPort } from "@/features/inventory/api";
import { Loader2, AlertCircle } from "lucide-react";

const portSchema = z.object({
  name: z.string().min(1, "Nome da porta é obrigatório").max(50),
  role: z.enum(["pon", "uplink", "client_access", "pass_through", "internal"]),
  connector_type: z.string().min(1, "Tipo de conector é obrigatório"),
  has_internal_pass_through: z.boolean().default(false),
  notes: z.string().max(500).optional().nullable(),
});

type PortFormValues = z.infer<typeof portSchema>;

export interface PortFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deviceId?: string | null;
  structureId?: string | null;
  defaultRole?: "pon" | "uplink" | "client_access" | "pass_through" | "internal";
  onSuccess: (port: PortRead) => void;
}

export function PortFormDialog({
  open,
  onOpenChange,
  deviceId = null,
  structureId = null,
  defaultRole = "pon",
  onSuccess,
}: PortFormDialogProps) {
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PortFormValues>({
    resolver: zodResolver(portSchema),
    defaultValues: {
      name: "",
      role: defaultRole,
      connector_type: "SC/APC",
      has_internal_pass_through: false,
      notes: "",
    },
  });

  React.useEffect(() => {
    if (open) {
      reset({
        name: "",
        role: defaultRole,
        connector_type: "SC/APC",
        has_internal_pass_through: false,
        notes: "",
      });
      setServerError(null);
    }
  }, [open, defaultRole, reset]);

  const onSubmit = async (values: PortFormValues) => {
    setIsSubmitting(true);
    setServerError(null);

    try {
      const created = await createPort({
        name: values.name.trim(),
        role: values.role,
        device_id: deviceId || null,
        structure_id: structureId || null,
        connector_type: values.connector_type,
        has_internal_pass_through: values.has_internal_pass_through,
        notes: values.notes || null,
      });
      onSuccess(created);
      onOpenChange(false);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setServerError(err.detail || err.message || "Erro ao cadastrar porta.");
      } else {
        setServerError("Erro inesperado ao cadastrar porta.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Cadastrar Nova Porta Óptica</DialogTitle>
          <DialogDescription>
            Defina o identificador, perfil funcional e tipo de conector da porta.
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p>{serverError}</p>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          {/* Nome / Identificador da porta */}
          <div className="space-y-1.5">
            <Label htmlFor="port-name">Identificador da Porta *</Label>
            <Input
              id="port-name"
              {...register("name")}
              placeholder="ex: PON-01, Porta 01, Uplink 10G"
              disabled={isSubmitting}
            />
            {errors.name && <p className="text-[11px] text-destructive">{errors.name.message}</p>}
          </div>

          {/* Função da porta e conector */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="port-role">Função da Porta</Label>
              <select
                id="port-role"
                {...register("role")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="pon">Porta PON (GPON/XGS-PON)</option>
                <option value="client_access">Atendimento ao Cliente</option>
                <option value="uplink">Uplink / Agregação</option>
                <option value="pass_through">Travessia (Pass-Through)</option>
                <option value="internal">Conexão Interna</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="port-connector">Padrão do Conector</Label>
              <select
                id="port-connector"
                {...register("connector_type")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="SC/APC">SC/APC (Verde)</option>
                <option value="SC/UPC">SC/UPC (Azul)</option>
                <option value="LC/APC">LC/APC (Verde)</option>
                <option value="LC/UPC">LC/UPC (Azul)</option>
              </select>
            </div>
          </div>

          {/* Opção de Travessia Interna */}
          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="port-pass-through"
              {...register("has_internal_pass_through")}
              disabled={isSubmitting}
              className="h-4 w-4 rounded border-input text-primary focus:ring-ring"
            />
            <Label htmlFor="port-pass-through" className="text-xs font-normal cursor-pointer">
              Porta com travessia física interna (frente/trás em DIO ou caixa)
            </Label>
          </div>

          {/* Observações */}
          <div className="space-y-1.5">
            <Label htmlFor="port-notes">Observações</Label>
            <Input
              id="port-notes"
              {...register("notes")}
              placeholder="ex: Módulo SFP+ C+ alocado"
              disabled={isSubmitting}
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting} className="gap-1.5">
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Adicionar Porta
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
