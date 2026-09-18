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
import type { DeviceRead } from "@/features/inventory/api";
import { createDevice, updateDevice, listSites, listStructures } from "@/features/inventory/api";
import { Loader2, AlertCircle } from "lucide-react";

const deviceSchema = z
  .object({
    code: z
      .string()
      .min(2, "Código deve ter pelo menos 2 caracteres")
      .max(50, "Código deve ter no máximo 50 caracteres")
      .regex(/^[A-Z0-9_-]+$/i, "Código deve conter apenas letras, números, hífens ou underlines"),
    kind: z.enum(["olt", "dio", "onu", "switch"]),
    manufacturer: z.string().min(1, "Fabricante é obrigatório").max(100),
    model: z.string().min(1, "Modelo é obrigatório").max(100),
    serial_number: z.string().max(100).optional().nullable(),
    location_type: z.enum(["site", "structure"]),
    site_id: z.string().optional().nullable(),
    structure_id: z.string().optional().nullable(),
    status: z.enum(["planned", "installed", "retired"]),
    condition: z.enum(["ok", "degraded", "damaged"]),
    notes: z.string().max(1000).optional().nullable(),
  })
  .refine(
    (data) => {
      if (data.location_type === "site") {
        return Boolean(data.site_id && data.site_id.trim().length > 0);
      }
      if (data.location_type === "structure") {
        return Boolean(data.structure_id && data.structure_id.trim().length > 0);
      }
      return false;
    },
    {
      message: "Selecione o local técnico (Site ou Estrutura) onde o dispositivo está instalado.",
      path: ["location_type"],
    }
  );

type DeviceFormValues = z.infer<typeof deviceSchema>;

export interface DeviceFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  device?: DeviceRead | null;
  defaultKind?: "olt" | "dio" | "onu" | "switch";
  defaultSiteId?: string | null;
  defaultStructureId?: string | null;
  onSuccess: (device: DeviceRead) => void;
}

export function DeviceFormDialog({
  open,
  onOpenChange,
  device,
  defaultKind = "olt",
  defaultSiteId = null,
  defaultStructureId = null,
  onSuccess,
}: DeviceFormDialogProps) {
  const isEditing = Boolean(device);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const [sitesList, setSitesList] = React.useState<Array<{ id: string; code: string; name: string }>>([]);
  const [structuresList, setStructuresList] = React.useState<Array<{ id: string; code: string; kind: string }>>([]);

  const initialLocationType: "site" | "structure" =
    device?.structure_id || defaultStructureId ? "structure" : "site";

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<DeviceFormValues>({
    resolver: zodResolver(deviceSchema),
    defaultValues: {
      code: device?.code || "",
      kind: (device?.kind as DeviceFormValues["kind"]) || defaultKind,
      manufacturer: device?.manufacturer || "",
      model: device?.model || "",
      serial_number: device?.serial_number || "",
      location_type: initialLocationType,
      site_id: device?.site_id || defaultSiteId || "",
      structure_id: device?.structure_id || defaultStructureId || "",
      status: (device?.status as DeviceFormValues["status"]) || "installed",
      condition: (device?.condition as DeviceFormValues["condition"]) || "ok",
      notes: device?.notes || "",
    },
  });

  const locationType = watch("location_type");

  // Carrega listas de sites e estruturas para o seletor de localização
  React.useEffect(() => {
    if (open) {
      listSites({ page_size: 100 })
        .then((res) => setSitesList(res.items.map((s) => ({ id: s.id, code: s.code, name: s.name }))))
        .catch(() => {});

      listStructures({ page_size: 100 })
        .then((res) => setStructuresList(res.items.map((st) => ({ id: st.id, code: st.code, kind: st.kind }))))
        .catch(() => {});
    }
  }, [open]);

  // Sincroniza formulário ao abrir ou alterar entidade
  React.useEffect(() => {
    if (device) {
      const locType: "site" | "structure" = device.structure_id ? "structure" : "site";
      reset({
        code: device.code,
        kind: (device.kind as DeviceFormValues["kind"]) || defaultKind,
        manufacturer: device.manufacturer,
        model: device.model,
        serial_number: device.serial_number || "",
        location_type: locType,
        site_id: device.site_id || "",
        structure_id: device.structure_id || "",
        status: (device.status as DeviceFormValues["status"]) || "installed",
        condition: (device.condition as DeviceFormValues["condition"]) || "ok",
        notes: device.notes || "",
      });
    } else {
      const locType: "site" | "structure" = defaultStructureId ? "structure" : "site";
      reset({
        code: "",
        kind: defaultKind,
        manufacturer: "",
        model: "",
        serial_number: "",
        location_type: locType,
        site_id: defaultSiteId || "",
        structure_id: defaultStructureId || "",
        status: "installed",
        condition: "ok",
        notes: "",
      });
    }
    setServerError(null);
  }, [device, defaultKind, defaultSiteId, defaultStructureId, reset, open]);

  const onSubmit = async (values: DeviceFormValues) => {
    setIsSubmitting(true);
    setServerError(null);

    const siteId = values.location_type === "site" && values.site_id ? values.site_id : null;
    const structureId = values.location_type === "structure" && values.structure_id ? values.structure_id : null;

    try {
      if (isEditing && device) {
        const updated = await updateDevice(
          device.id,
          {
            manufacturer: values.manufacturer.trim(),
            model: values.model.trim(),
            serial_number: values.serial_number ? values.serial_number.trim() : null,
            site_id: siteId,
            structure_id: structureId,
            status: values.status,
            condition: values.condition,
            notes: values.notes || null,
          },
          device.version
        );
        onSuccess(updated);
        onOpenChange(false);
      } else {
        const created = await createDevice({
          code: values.code.trim().toUpperCase(),
          kind: values.kind,
          manufacturer: values.manufacturer.trim(),
          model: values.model.trim(),
          serial_number: values.serial_number ? values.serial_number.trim() : null,
          site_id: siteId,
          structure_id: structureId,
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
            "Conflito de versão ou recurso já alterado por outro operador. Recarregue os dados para sincronizar."
          );
        } else {
          setServerError(err.detail || err.message || "Erro ao salvar dispositivo.");
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
            {isEditing ? `Editar Dispositivo — ${device?.code}` : "Cadastrar Novo Dispositivo"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize o modelo, número de série, localização física e situação operacional do equipamento."
              : "Cadastre um elemento de rede (OLT, DIO, Switch, ONU) alocado estritamente em um Site ou Estrutura."}
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p>{serverError}</p>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          {/* Código e Tipo */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="device-code">Código do Dispositivo *</Label>
              <Input
                id="device-code"
                {...register("code")}
                placeholder="ex: OLT-01"
                disabled={isEditing || isSubmitting}
                className="uppercase font-mono"
              />
              {errors.code && <p className="text-[11px] text-destructive">{errors.code.message}</p>}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="device-kind">Tipo de Equipamento</Label>
              <select
                id="device-kind"
                {...register("kind")}
                disabled={isEditing || isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="olt">OLT (Terminal Óptico de Linha)</option>
                <option value="dio">DIO (Distribuidor Interno Óptico)</option>
                <option value="switch">Switch de Agregação / Borda</option>
                <option value="onu">ONU / ONT</option>
              </select>
            </div>
          </div>

          {/* Fabricante e Modelo */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="device-manufacturer">Fabricante *</Label>
              <Input
                id="device-manufacturer"
                {...register("manufacturer")}
                placeholder="ex: Furukawa, Huawei, Datacom"
                disabled={isSubmitting}
              />
              {errors.manufacturer && (
                <p className="text-[11px] text-destructive">{errors.manufacturer.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="device-model">Modelo *</Label>
              <Input
                id="device-model"
                {...register("model")}
                placeholder="ex: SmartAX MA5800-X7"
                disabled={isSubmitting}
              />
              {errors.model && <p className="text-[11px] text-destructive">{errors.model.message}</p>}
            </div>
          </div>

          {/* Número de Série */}
          <div className="space-y-1.5">
            <Label htmlFor="device-serial">
              Número de Série (Serial)
              <span className="text-[10px] text-muted-foreground font-normal ml-1">
                (identificador físico do equipamento)
              </span>
            </Label>
            <Input
              id="device-serial"
              {...register("serial_number")}
              placeholder="ex: HWTC12345678"
              disabled={isSubmitting}
              className="font-mono"
            />
            {errors.serial_number && (
              <p className="text-[11px] text-destructive">{errors.serial_number.message}</p>
            )}
          </div>

          {/* Localização Técnica (Site OU Estrutura - Mutuamente Exclusivos) */}
          <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-3">
            <div className="space-y-1">
              <Label className="text-xs font-semibold">Alocação Física do Dispositivo *</Label>
              <p className="text-[11px] text-muted-foreground">
                Equipamentos devem residir em um POP/Site ou em uma Estrutura (poste, armário, caixa).
              </p>
            </div>

            <div className="flex items-center gap-4 text-xs">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  value="site"
                  checked={locationType === "site"}
                  onChange={() => {
                    setValue("location_type", "site");
                    setValue("structure_id", "");
                  }}
                  disabled={isSubmitting}
                  className="text-primary focus:ring-ring"
                />
                <span>Alocado em Site / POP</span>
              </label>

              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  value="structure"
                  checked={locationType === "structure"}
                  onChange={() => {
                    setValue("location_type", "structure");
                    setValue("site_id", "");
                  }}
                  disabled={isSubmitting}
                  className="text-primary focus:ring-ring"
                />
                <span>Alocado em Estrutura Externa</span>
              </label>
            </div>

            {locationType === "site" ? (
              <div className="space-y-1.5 pt-1">
                <Label htmlFor="device-site-select">Selecione o Site / POP *</Label>
                <select
                  id="device-site-select"
                  {...register("site_id")}
                  disabled={isSubmitting}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <option value="">-- Escolha o Site / POP --</option>
                  {sitesList.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.code} — {site.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="space-y-1.5 pt-1">
                <Label htmlFor="device-structure-select">Selecione a Estrutura *</Label>
                <select
                  id="device-structure-select"
                  {...register("structure_id")}
                  disabled={isSubmitting}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <option value="">-- Escolha a Estrutura (Poste/Caixa) --</option>
                  {structuresList.map((st) => (
                    <option key={st.id} value={st.id}>
                      {st.code} ({st.kind.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {errors.location_type && (
              <p className="text-[11px] text-destructive">{errors.location_type.message}</p>
            )}
          </div>

          {/* Situação e Condição Física */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="device-status">Situação Administrativa</Label>
              <select
                id="device-status"
                {...register("status")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="installed">Instalado / Ativo</option>
                <option value="planned">Planejado / Em Almoxarifado</option>
                <option value="retired">Desativado / Baixado</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="device-condition">Condição Física</Label>
              <select
                id="device-condition"
                {...register("condition")}
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="ok">Operacional (OK)</option>
                <option value="degraded">Degradado</option>
                <option value="damaged">Danificado / Com Falha</option>
              </select>
            </div>
          </div>

          {/* Observações */}
          <div className="space-y-1.5">
            <Label htmlFor="device-notes">Observações</Label>
            <textarea
              id="device-notes"
              {...register("notes")}
              rows={2}
              placeholder="Informações de firmware, slot, rack ou patrimônio..."
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
              {isEditing ? "Salvar Alterações" : "Cadastrar Dispositivo"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
