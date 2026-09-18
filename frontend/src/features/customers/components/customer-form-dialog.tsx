"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createCustomer, updateCustomer } from "../api";
import type { CustomerCreate, CustomerRead, CustomerUpdate } from "../types";

const customerSchema = z.object({
  code: z
    .string()
    .min(2, "O código deve ter pelo menos 2 caracteres")
    .max(50, "O código não pode exceder 50 caracteres")
    .regex(/^[A-Za-z0-9-_]+$/, "Apenas letras, números, hífen e underscore"),
  name: z
    .string()
    .min(2, "O nome deve ter pelo menos 2 caracteres")
    .max(150, "O nome não pode exceder 150 caracteres"),
  phone: z.string().max(30, "Telefone muito longo").optional().or(z.literal("")),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  address: z.string().max(255, "Endereço muito longo").optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});

type CustomerFormData = z.infer<typeof customerSchema>;

interface CustomerFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  customerToEdit?: CustomerRead | null;
  onSuccess: (savedCustomer: CustomerRead) => void;
}

export function CustomerFormDialog({
  open,
  onOpenChange,
  customerToEdit,
  onSuccess,
}: CustomerFormDialogProps) {
  const isEditing = Boolean(customerToEdit);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CustomerFormData>({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      code: "",
      name: "",
      phone: "",
      email: "",
      address: "",
      notes: "",
    },
  });

  React.useEffect(() => {
    if (open) {
      setErrorMessage(null);
      if (customerToEdit) {
        reset({
          code: customerToEdit.code,
          name: customerToEdit.name,
          phone: customerToEdit.phone || "",
          email: customerToEdit.email || "",
          address: customerToEdit.address || "",
          notes: customerToEdit.notes || "",
        });
      } else {
        reset({
          code: `CLI-${Math.floor(10000 + Math.random() * 90000)}`,
          name: "",
          phone: "",
          email: "",
          address: "",
          notes: "",
        });
      }
    }
  }, [open, customerToEdit, reset]);

  const onSubmit = async (data: CustomerFormData) => {
    setErrorMessage(null);
    try {
      if (isEditing && customerToEdit) {
        const payload: CustomerUpdate = {
          name: data.name,
          phone: data.phone || null,
          email: data.email || null,
          address: data.address || null,
          notes: data.notes || null,
        };
        const updated = await updateCustomer(customerToEdit.id, payload, customerToEdit.version);
        onSuccess(updated);
        onOpenChange(false);
      } else {
        const payload: CustomerCreate = {
          code: data.code,
          name: data.name,
          phone: data.phone || null,
          email: data.email || null,
          address: data.address || null,
          notes: data.notes || null,
        };
        const created = await createCustomer(payload);
        onSuccess(created);
        onOpenChange(false);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao salvar dados do cliente.";
      setErrorMessage(msg);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Editar Dados do Assinante" : "Cadastrar Novo Assinante"}
          </DialogTitle>
        </DialogHeader>

        {errorMessage && (
          <div
            role="alert"
            className="rounded-md border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive"
          >
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="code" className="text-xs">
              Código Único do Cliente <span className="text-destructive">*</span>
            </Label>
            <Input
              id="code"
              {...register("code")}
              disabled={isEditing}
              placeholder="Ex: CLI-10023"
              className="font-mono text-xs"
            />
            {errors.code && (
              <p className="text-[11px] text-destructive">{errors.code.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="name" className="text-xs">
              Nome Completo ou Razão Social <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              {...register("name")}
              placeholder="Ex: Maria Silva ou Empresa LTDA"
              className="text-xs"
            />
            {errors.name && (
              <p className="text-[11px] text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="phone" className="text-xs">
                Telefone / WhatsApp
              </Label>
              <Input
                id="phone"
                {...register("phone")}
                placeholder="(11) 98765-4321"
                className="text-xs"
              />
              {errors.phone && (
                <p className="text-[11px] text-destructive">{errors.phone.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs">
                E-mail
              </Label>
              <Input
                id="email"
                type="email"
                {...register("email")}
                placeholder="cliente@email.com"
                className="text-xs"
              />
              {errors.email && (
                <p className="text-[11px] text-destructive">{errors.email.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="address" className="text-xs">
              Endereço de Instalação
            </Label>
            <Input
              id="address"
              {...register("address")}
              placeholder="Rua, número, complemento, bairro"
              className="text-xs"
            />
            {errors.address && (
              <p className="text-[11px] text-destructive">{errors.address.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="notes" className="text-xs">
              Observações Cadastrais
            </Label>
            <Input
              id="notes"
              {...register("notes")}
              placeholder="Informações adicionais do cliente"
              className="text-xs"
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={isSubmitting}>
              {isSubmitting ? "Salvando..." : isEditing ? "Salvar Alterações" : "Cadastrar Cliente"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
