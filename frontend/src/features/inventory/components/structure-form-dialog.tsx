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
import { CoordinateInput } from "@/components/ui/coordinate-input";
import { ApiError } from "@/lib/api/types";
import type { StructureRead } from "@/features/inventory/api";
import { createStructure, updateStructure, listSites } from "@/features/inventory/api";
import { Loader2, AlertCircle } from "lucide-react";

const structureSchema = z.object({
  code: z
    .string()
    .min(2, "Código deve ter pelo menos 2 caracteres")
    .max(50, "Código deve ter no máximo 50 caracteres")
    .regex(/^[A-Z0-9_-]+$/i, "Código deve conter apenas letras, números, hífens ou underlines"),
  kind: z.enum(["pole", "ceo", "cto", "manhole", "pedestal"]),
  capacity: z.coerce.number().int().min(0, "Capacidade deve ser maior ou igual a zero"),
  site_id: z.string().optional().nullable(),
  status: z.enum(["planned", "installed", "retired"]),
  condition: z.enum(["ok", "degraded", "damaged"]),
  notes: z.string().max(1000).optional().nullable(),
});

type StructureFormValues = z.infer<typeof structureSchema>;

export interface StructureFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  structure?: StructureRead | null;
  defaultKind?: "pole" | "ceo" | "cto" | "manhole" | "pedestal";
  onSuccess: (structure: StructureRead) => void;
}

export function StructureFormDialog({
  open,
  onOpenChange,
  structure,
  defaultKind = "pole",
  onSuccess,
}: StructureFormDialogProps) {
  const isEditing = Boolean(structure);
  const [coordinates, setCoordinates] = React.useState<{ lat: number | null; lon: number | null }>({
    lat: structure?.location?.coordinates ? structure.location.coordinates[1] : -23.55052,
    lon: structure?.location?.coordinates ? structure.location.coordinates[0] : -46.633308,
  });
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [availableSites, setAvailableSites] = React.useState<Array<{ id: string; code: string; name: string }>>([]);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<StructureFormValues>({
    resolver: zodResolver(structureSchema),
    defaultValues: {
      code: structure?.code || "",
      kind: (structure?.kind as StructureFormValues["kind"]) || defaultKind,
      capacity: structure?.capacity ?? (defaultKind === "cto" ? 16 : defaultKind === "ceo" ? 24 : 0),
      site_id: structure?.site_id || "",
      status: (structure?.status as StructureFormValues["status"]) || "installed",
      condition: (structure?.condition as StructureFormValues["condition"]) || "ok",
      notes: structure?.notes || "",
    },
  });

  const selectedKind = watch("kind");

  // Carrega lista de sites para seleção de associação opcional
  React.useEffect(() => {
    if (open) {
      listSites({ page_size: 100 })
        .then((res) => {
          setAvailableSites(res.items.map((s) => ({ id: s.id, code: s.code, name: s.name })));
        })
        .catch(() => {});
    }
  }, [open]);

  // Atualiza formulário com valores da entidade em edição
  React.useEffect(() => {
    if (structure) {
      reset({
        code: structure.code,
        kind: (structure.kind as StructureFormValues["kind"]) || defaultKind,
        capacity: structure.capacity ?? 0,
        site_id: structure.site_id || "",
        status: (structure.status as StructureFormValues["status"]) || "installed",
        condition: (structure.condition as StructureFormValues["condition"]) || "ok",
        notes: structure.notes || "",
      });
      if (structure.location?.coordinates) {
        setCoordinates({
          lat: structure.location.coordinates[1],
          lon: structure.location.coordinates[0],
        });
      }
    } else {
      reset({
        code: "",
        kind: defaultKind,
        capacity: defaultKind === "cto" ? 16 : defaultKind === "ceo" ? 24 : 0,
        site_id: "",
        status: "installed",
        condition: "ok",
        notes: "",
      });
      setCoordinates({ lat: -23.55052, lon: -46.633308 });
    }
    setServerError(null);
  }, [structure, defaultKind, reset, open]);

  const onSubmit = async (values: StructureFormValues) => {
    if (coordinates.lat === null || coordinates.lon === null) {
      setServerError("Coordenadas geográficas válidas são obrigatórias.");
      return;
    }

    setIsSubmitting(true);
    setServerError(null);

    try {
      if (isEditing && structure) {
        const updated = await updateStructure(
          structure.id,
          {
            location: {
              type: "Point",
              coordinates: [coordinates.lon, coordinates.lat],
            },
            capacity: values.capacity,
            site_id: values.site_id ? values.site_id : null,
            status: values.status,
            condition: values.condition,
            notes: values.notes || null,
          },
          structure.version
        );
        onSuccess(updated);
        onOpenChange(false);
      } else {
        const created = await createStructure({
          code: values.code.trim().toUpperCase(),
          kind: values.kind,
          location: {
            type: "Point",
            coordinates: [coordinates.lon, coordinates.lat],
          },
          capacity: values.capacity,
          site_id: values.site_id ? values.site_id : null,
          status: values.status,
          condition: values.condition,
          notes: values.notes || null,
        });
        onSuccess(created);
        onOpenChange(false);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 412 || err.status === 409) {
          setServerError(
            "Conflito de versão ou recurso já alterado por outro usuário. Recarregue os dados para sincronizar."
          );
        } else {
          setServerError(err.detail || err.message || "Erro ao salvar estrutura física.");
        }
      } else {
        setServerError("Erro inesperado ao processar formulário.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const kindLabels: Record<string, string> = {
    pole: "Poste",
    ceo: "Caixa de Emenda (CEO)",
    cto: "Caixa de Terminação (CTO)",
    manhole: "Caixa Subterrânea",
    pedestal: "Pedestal",
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? `Editar ${kindLabels[structure?.kind || "pole"]} — ${structure?.code}` : `Cadastrar Nova Estrutura`}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize as características físicas, capacidade e coordenadas da estrutura."
              : "Defina o código identificador, tipo, capacidade e localização geográfica no mapa."}
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p>{serverError}</p>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          {/* Código identificador único */}
          <div className="space-y-1.5">
            <Label htmlFor="structure-code">Código da Estrutura *</Label>
            <Input
              id="structure-code"
              {...register("code")}
              placeholder={defaultKind === "cto" ? "ex: CTO-04" : defaultKind === "ceo" ? "ex: CEO-01" : "ex: POSTE-12"}
              disabled={isEditing || isSubmitting}
              className="uppercase font-mono"
            />
            {errors.code && <p className="text-[11px] text-destructive">{errors.code.message}</p>}
          </div>

          {/* Tipo de Estrutura e Capacidade */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="structure-kind">Tipo de Estrutura</Label>
              <select
                id="structure-kind"
                {...register("kind")}
                disabled={isEditing || isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="pole">Poste</option>
                <option value="ceo">Caixa CEO (Emenda)</option>
                <option value="cto">Caixa CTO (Terminação)</option>
                <option value="manhole">Caixa Subterrânea</option>
                <option value="pedestal">Pedestal</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="structure-capacity">
                {selectedKind === "cto" ? "Capacidade (Portas)" : selectedKind === "ceo" ? "Capacidade (Fusões)" : "Capacidade"}
              </Label>
              <Input
                id="structure-capacity"
                type="number"
                {...register("capacity")}
                disabled={isSubmitting}
              />
              {errors.capacity && <p className="text-[11px] text-destructive">{errors.capacity.message}</p>}
            </div>
          </div>

          {/* Localização Geográfica */}
          <div className="space-y-1.5 pt-1">
            <Label>Localização Geográfica (WGS-84) *</Label>
            <CoordinateInput
              value={coordinates}
              onChange={(coords) => setCoordinates(coords)}
              disabled={isSubmitting}
            />
          </div>

          {/* Site Pai Associado (opcional) */}
          <div className="space-y-1.5">
            <Label htmlFor="structure-site">Alocado no Site / POP (Opcional)</Label>
            <select
              id="structure-site"
              {...register("site_id")}
              disabled={isSubmitting}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="">Nenhum (Instalação Externa / Via Pública)</option>
              {availableSites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.code} — {site.name}
                </option>
              ))}
            </select>
          </div>

          {/* Situação e Condição Física */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="structure-status">Situação Administrativa</Label>
              <select
                id="structure-status"
                {...register("status")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="installed">Instalado / Ativo</option>
                <option value="planned">Planejado / Em Projeto</option>
                <option value="retired">Desativado / Arquivado</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="structure-condition">Condição Física</Label>
              <select
                id="structure-condition"
                {...register("condition")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="ok">Operacional (OK)</option>
                <option value="degraded">Degradado</option>
                <option value="damaged">Danificado</option>
              </select>
            </div>
          </div>

          {/* Observações */}
          <div className="space-y-1.5">
            <Label htmlFor="structure-notes">Observações</Label>
            <textarea
              id="structure-notes"
              {...register("notes")}
              rows={2}
              placeholder="Informações técnicas de ancoragem, trajeto ou fechamento..."
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
              {isEditing ? "Salvar Alterações" : "Cadastrar Estrutura"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
