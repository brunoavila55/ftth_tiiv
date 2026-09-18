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
import type { CableRead } from "@/features/cables/api";
import { createCable, updateCable } from "@/features/cables/api";
import { Loader2, AlertCircle } from "lucide-react";

const STANDARD_CAPACITIES = [
  { fibers: 6, tubes: 1, label: "6 FO (1 tubo de 6 fibras)" },
  { fibers: 12, tubes: 1, label: "12 FO (1 tubo de 12 fibras)" },
  { fibers: 24, tubes: 2, label: "24 FO (2 tubos de 12 fibras)" },
  { fibers: 36, tubes: 3, label: "36 FO (3 tubos de 12 fibras)" },
  { fibers: 48, tubes: 4, label: "48 FO (4 tubos de 12 fibras)" },
  { fibers: 72, tubes: 6, label: "72 FO (6 tubos de 12 fibras)" },
  { fibers: 96, tubes: 8, label: "96 FO (8 tubos de 12 fibras)" },
  { fibers: 144, tubes: 12, label: "144 FO (12 tubos de 12 fibras)" },
];

const cableSchema = z.object({
  code: z
    .string()
    .min(2, "Código deve ter pelo menos 2 caracteres")
    .max(50, "Código deve ter no máximo 50 caracteres")
    .regex(/^[A-Z0-9_-]+$/i, "Código deve conter apenas letras, números, hífens ou underlines"),
  model: z.string().min(2, "Modelo comercial é obrigatório").max(100),
  capacityIndex: z.coerce.number().int().min(0),
  color_standard: z.enum(["NBR", "TIA-598"]),
  status: z.enum(["planned", "installed", "retired"]),
  notes: z.string().max(1000).optional().nullable(),
});

type CableFormValues = z.infer<typeof cableSchema>;

export interface CableFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  cable?: CableRead | null;
  onSuccess: (cable: CableRead) => void;
}

export function CableFormDialog({
  open,
  onOpenChange,
  cable,
  onSuccess,
}: CableFormDialogProps) {
  const isEditing = Boolean(cable);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  // Determina índice de capacidade inicial com base na entidade
  const initialCapIndex = React.useMemo(() => {
    if (!cable) return 1; // 12 FO padrão
    const idx = STANDARD_CAPACITIES.findIndex((c) => c.fibers === cable.fiber_count);
    return idx >= 0 ? idx : 1;
  }, [cable]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CableFormValues>({
    resolver: zodResolver(cableSchema),
    defaultValues: {
      code: cable?.code || "",
      model: cable?.model || "",
      capacityIndex: initialCapIndex,
      color_standard: (cable?.color_standard as "NBR" | "TIA-598") || "NBR",
      status: (cable?.status as "planned" | "installed" | "retired") || "installed",
      notes: cable?.notes || "",
    },
  });

  React.useEffect(() => {
    if (cable) {
      const idx = STANDARD_CAPACITIES.findIndex((c) => c.fibers === cable.fiber_count);
      reset({
        code: cable.code,
        model: cable.model,
        capacityIndex: idx >= 0 ? idx : 1,
        color_standard: (cable.color_standard as "NBR" | "TIA-598") || "NBR",
        status: (cable.status as "planned" | "installed" | "retired") || "installed",
        notes: cable.notes || "",
      });
    } else {
      reset({
        code: "",
        model: "CFOA-SM-AS80-S-12F",
        capacityIndex: 1,
        color_standard: "NBR",
        status: "installed",
        notes: "",
      });
    }
    setServerError(null);
  }, [cable, reset, open]);

  const onSubmit = async (values: CableFormValues) => {
    setIsSubmitting(true);
    setServerError(null);

    const selectedCap = STANDARD_CAPACITIES[values.capacityIndex] || STANDARD_CAPACITIES[1];

    try {
      if (isEditing && cable) {
        const updated = await updateCable(
          cable.id,
          {
            status: values.status,
            notes: values.notes || null,
          },
          cable.version
        );
        onSuccess(updated);
        onOpenChange(false);
      } else {
        const created = await createCable({
          code: values.code.trim().toUpperCase(),
          model: values.model.trim(),
          fiber_count: selectedCap.fibers,
          tube_count: selectedCap.tubes,
          color_standard: values.color_standard,
          status: values.status,
          notes: values.notes || null,
        });
        onSuccess(created);
        onOpenChange(false);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 412 || err.status === 409) {
          setServerError(
            "Conflito de versão ou recurso já alterado por outro operador. Recarregue os dados para sincronizar."
          );
        } else {
          setServerError(err.detail || err.message || "Erro ao salvar cabo óptico.");
        }
      } else {
        setServerError("Erro inesperado ao processar formulário.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? `Editar Cabo — ${cable?.code}` : "Cadastrar Novo Cabo Óptico"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize as anotações e a situação operacional do cabo óptico."
              : "Defina o código identificador, modelo comercial, capacidade de tubos/fibras e padrão de cores."}
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p>{serverError}</p>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          {/* Código do Cabo */}
          <div className="space-y-1.5">
            <Label htmlFor="cable-code">Código do Cabo *</Label>
            <Input
              id="cable-code"
              {...register("code")}
              placeholder="ex: CAB-TRONCAL-01"
              disabled={isEditing || isSubmitting}
              className="uppercase font-mono"
            />
            {errors.code && <p className="text-[11px] text-destructive">{errors.code.message}</p>}
          </div>

          {/* Modelo Comercial */}
          <div className="space-y-1.5">
            <Label htmlFor="cable-model">Modelo Comercial / Fabricante *</Label>
            <Input
              id="cable-model"
              {...register("model")}
              placeholder="ex: CFOA-SM-AS80-S-12F"
              disabled={isEditing || isSubmitting}
            />
            {errors.model && <p className="text-[11px] text-destructive">{errors.model.message}</p>}
          </div>

          {/* Capacidade Padrão de Fibras e Tubos */}
          <div className="space-y-1.5">
            <Label htmlFor="cable-capacity">Capacidade Fibras / Tubos Loose</Label>
            <select
              id="cable-capacity"
              {...register("capacityIndex")}
              disabled={isEditing || isSubmitting}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {STANDARD_CAPACITIES.map((cap, idx) => (
                <option key={cap.fibers} value={idx}>
                  {cap.label}
                </option>
              ))}
            </select>
            {isEditing && (
              <p className="text-[10px] text-muted-foreground">
                A capacidade física de fibras não pode ser alterada livremente após o cabo ser gerado.
              </p>
            )}
          </div>

          {/* Padrão de Cores e Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="cable-colors">Norma de Cores</Label>
              <select
                id="cable-colors"
                {...register("color_standard")}
                disabled={isEditing || isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="NBR">ABNT NBR 14106</option>
                <option value="TIA-598">ANSI / TIA-598</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="cable-status">Situação Operacional</Label>
              <select
                id="cable-status"
                {...register("status")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="installed">Instalado / Ativo</option>
                <option value="planned">Planejado / Em Projeto</option>
                <option value="retired">Desativado / Baixado</option>
              </select>
            </div>
          </div>

          {/* Observações */}
          <div className="space-y-1.5">
            <Label htmlFor="cable-notes">Observações</Label>
            <textarea
              id="cable-notes"
              {...register("notes")}
              rows={2}
              placeholder="Informações de lote, bobina ou especificação óptica..."
              disabled={isSubmitting}
              className="w-full rounded-md border border-input bg-background p-2 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
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
              {isEditing ? "Salvar Alterações" : "Cadastrar Cabo"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
