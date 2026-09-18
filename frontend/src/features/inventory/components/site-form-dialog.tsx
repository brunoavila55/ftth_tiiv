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
import type { SiteRead } from "@/lib/api/types";
import { createSite, updateSite } from "@/features/inventory/api";
import { Loader2, AlertCircle } from "lucide-react";

const siteSchema = z.object({
  code: z
    .string()
    .min(2, "Código deve ter pelo menos 2 caracteres")
    .max(50, "Código deve ter no máximo 50 caracteres")
    .regex(/^[A-Z0-9_-]+$/i, "Código deve conter apenas letras, números, hífens ou underlines"),
  name: z
    .string()
    .min(2, "Nome deve ter pelo menos 2 caracteres")
    .max(100, "Nome deve ter no máximo 100 caracteres"),
  kind: z.enum(["pop", "cabinet", "technical_facility"]),
  status: z.enum(["planned", "installed", "retired"]),
  address: z.string().max(255).optional().nullable(),
  notes: z.string().max(1000).optional().nullable(),
});

type SiteFormValues = z.infer<typeof siteSchema>;

export interface SiteFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  site?: SiteRead | null;
  onSuccess: (site: SiteRead) => void;
}

export function SiteFormDialog({
  open,
  onOpenChange,
  site,
  onSuccess,
}: SiteFormDialogProps) {
  const isEditing = Boolean(site);
  const [coordinates, setCoordinates] = React.useState<{ lat: number | null; lon: number | null }>({
    lat: site?.location?.coordinates ? site.location.coordinates[1] : -23.55052,
    lon: site?.location?.coordinates ? site.location.coordinates[0] : -46.633308,
  });
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SiteFormValues>({
    resolver: zodResolver(siteSchema),
    defaultValues: {
      code: site?.code || "",
      name: site?.name || "",
      kind: (site?.kind as SiteFormValues["kind"]) || "pop",
      status: (site?.status as SiteFormValues["status"]) || "installed",
      address: site?.address || "",
      notes: site?.notes || "",
    },
  });

  // Atualiza valores quando o site em edição muda
  React.useEffect(() => {
    if (site) {
      reset({
        code: site.code,
        name: site.name,
        kind: (site.kind as SiteFormValues["kind"]) || "pop",
        status: (site.status as SiteFormValues["status"]) || "installed",
        address: site.address || "",
        notes: site.notes || "",
      });
      if (site.location?.coordinates) {
        setCoordinates({
          lat: site.location.coordinates[1],
          lon: site.location.coordinates[0],
        });
      }
    } else {
      reset({
        code: "",
        name: "",
        kind: "pop",
        status: "installed",
        address: "",
        notes: "",
      });
      setCoordinates({ lat: -23.55052, lon: -46.633308 });
    }
    setServerError(null);
  }, [site, reset, open]);

  const onSubmit = async (values: SiteFormValues) => {
    if (coordinates.lat === null || coordinates.lon === null) {
      setServerError("Coordenadas geográficas válidas são obrigatórias.");
      return;
    }

    setIsSubmitting(true);
    setServerError(null);

    try {
      if (isEditing && site) {
        const updated = await updateSite(
          site.id,
          {
            name: values.name,
            kind: values.kind,
            location: {
              type: "Point",
              coordinates: [coordinates.lon, coordinates.lat],
            },
            status: values.status,
            address: values.address || null,
            notes: values.notes || null,
          },
          site.version
        );
        onSuccess(updated);
        onOpenChange(false);
      } else {
        const created = await createSite({
          code: values.code.trim().toUpperCase(),
          name: values.name.trim(),
          kind: values.kind,
          location: {
            type: "Point",
            coordinates: [coordinates.lon, coordinates.lat],
          },
          status: values.status,
          address: values.address || null,
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
          setServerError(err.detail || err.message || "Erro ao salvar site.");
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
          <DialogTitle>{isEditing ? `Editar Site — ${site?.code}` : "Cadastrar Novo Site / POP"}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize as informações cadastrais e geográficas da estação técnica."
              : "Defina a identificação, tipo e localização do novo local técnico de telecomunicações."}
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
            <Label htmlFor="site-code">Código Único *</Label>
            <Input
              id="site-code"
              {...register("code")}
              placeholder="ex: POP-CENTRO"
              disabled={isEditing || isSubmitting}
              className="uppercase font-mono"
            />
            {errors.code && <p className="text-[11px] text-destructive">{errors.code.message}</p>}
          </div>

          {/* Nome amigável */}
          <div className="space-y-1.5">
            <Label htmlFor="site-name">Nome do Local Técnico *</Label>
            <Input
              id="site-name"
              {...register("name")}
              placeholder="ex: Estação Central Matriz"
              disabled={isSubmitting}
            />
            {errors.name && <p className="text-[11px] text-destructive">{errors.name.message}</p>}
          </div>

          {/* Tipo e Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="site-kind">Tipo de Site</Label>
              <select
                id="site-kind"
                {...register("kind")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="pop">POP de Telecom</option>
                <option value="cabinet">Armário Técnico</option>
                <option value="technical_facility">Instalação Técnica</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="site-status">Situação Administrativa</Label>
              <select
                id="site-status"
                {...register("status")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="installed">Instalado / Operacional</option>
                <option value="planned">Planejado / Em Projeto</option>
                <option value="retired">Desativado / Arquivado</option>
              </select>
            </div>
          </div>

          {/* Coordenadas Geográficas com CoordinateInput */}
          <div className="space-y-1.5 pt-1">
            <Label>Localização Geográfica (WGS-84) *</Label>
            <CoordinateInput
              value={coordinates}
              onChange={(coords) => setCoordinates(coords)}
              disabled={isSubmitting}
            />
          </div>

          {/* Endereço */}
          <div className="space-y-1.5">
            <Label htmlFor="site-address">Endereço / Referência</Label>
            <Input
              id="site-address"
              {...register("address")}
              placeholder="ex: Av. Paulista, 1000 - Bela Vista, SP"
              disabled={isSubmitting}
            />
          </div>

          {/* Observações */}
          <div className="space-y-1.5">
            <Label htmlFor="site-notes">Observações</Label>
            <textarea
              id="site-notes"
              {...register("notes")}
              rows={2}
              placeholder="Informações adicionais de acesso, segurança ou energia..."
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
              {isEditing ? "Salvar Alterações" : "Cadastrar Site"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
