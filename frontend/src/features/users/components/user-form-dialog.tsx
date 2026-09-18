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
import { createUser, updateUser } from "@/features/users/api";
import type { UserRead, UserRole } from "@/features/users/types";
import { USER_ROLE_LABELS } from "@/features/users/types";
import { Loader2, AlertCircle } from "lucide-react";

const userCreateSchema = z.object({
  name: z.string().min(2, "Nome deve ter pelo menos 2 caracteres").max(100),
  email: z.string().email("Endereço de e-mail inválido").max(100),
  role: z.enum(["admin", "engineer", "technician", "viewer"]),
  password: z.string().min(8, "A senha deve ter no mínimo 8 caracteres"),
  is_active: z.boolean().default(true),
});

const userEditSchema = z.object({
  name: z.string().min(2, "Nome deve ter pelo menos 2 caracteres").max(100),
  email: z.string().email("Endereço de e-mail inválido").max(100),
  role: z.enum(["admin", "engineer", "technician", "viewer"]),
  password: z.string().optional(),
  is_active: z.boolean().default(true),
});

type UserFormValues = z.infer<typeof userCreateSchema>;

export interface UserFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user?: UserRead | null;
  onSuccess: (user: UserRead) => void;
}

export function UserFormDialog({
  open,
  onOpenChange,
  user,
  onSuccess,
}: UserFormDialogProps) {
  const isEditing = Boolean(user);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<UserFormValues>({
    resolver: zodResolver(isEditing ? userEditSchema : userCreateSchema),
    defaultValues: {
      name: "",
      email: "",
      role: "viewer",
      password: "",
      is_active: true,
    },
  });

  const selectedRole = watch("role") as UserRole;

  React.useEffect(() => {
    if (open) {
      setServerError(null);
      if (user) {
        reset({
          name: user.name,
          email: user.email,
          role: user.role,
          password: "",
          is_active: user.is_active,
        });
      } else {
        reset({
          name: "",
          email: "",
          role: "viewer",
          password: "",
          is_active: true,
        });
      }
    }
  }, [open, user, reset]);

  const onSubmit = async (values: UserFormValues) => {
    setIsSubmitting(true);
    setServerError(null);

    try {
      if (isEditing && user) {
        const updated = await updateUser(
          user.id,
          {
            name: values.name,
            email: values.email,
            role: values.role as UserRole,
            is_active: values.is_active,
          },
          user.version
        );
        onSuccess(updated);
        onOpenChange(false);
      } else {
        const created = await createUser({
          name: values.name,
          email: values.email,
          role: values.role as UserRole,
          password: values.password,
        });
        onSuccess(created);
        onOpenChange(false);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setServerError("Já existe um usuário cadastrado com este e-mail.");
        } else if (err.status === 412) {
          setServerError("O usuário foi alterado por outro administrador. Recarregue a página.");
        } else {
          setServerError(err.detail || err.message);
        }
      } else if (err instanceof Error) {
        setServerError(err.message);
      } else {
        setServerError("Ocorreu um erro ao salvar o usuário.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Editar Operador" : "Novo Operador / Usuário"}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {isEditing
              ? "Atualize os dados cadastrais, e-mail de acesso ou nível de permissão RBAC."
              : "Defina os dados de acesso do novo operador da rede FTTH."}
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive border border-destructive/20">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="user-name" className="text-xs">
              Nome Completo <span className="text-destructive">*</span>
            </Label>
            <Input
              id="user-name"
              placeholder="Ex: Carlos Silva"
              {...register("name")}
              className="text-xs"
            />
            {errors.name && (
              <p className="text-[11px] text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="user-email" className="text-xs">
              E-mail de Acesso <span className="text-destructive">*</span>
            </Label>
            <Input
              id="user-email"
              type="email"
              placeholder="Ex: carlos.silva@provedor.com.br"
              {...register("email")}
              className="text-xs"
            />
            {errors.email && (
              <p className="text-[11px] text-destructive">{errors.email.message}</p>
            )}
          </div>

          {!isEditing && (
            <div className="space-y-1.5">
              <Label htmlFor="user-password" className="text-xs">
                Senha Inicial <span className="text-destructive">*</span>
              </Label>
              <Input
                id="user-password"
                type="password"
                placeholder="Mínimo de 8 caracteres"
                {...register("password")}
                className="text-xs"
              />
              {errors.password && (
                <p className="text-[11px] text-destructive">{errors.password.message}</p>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="user-role" className="text-xs">
              Perfil de Permissão (RBAC) <span className="text-destructive">*</span>
            </Label>
            <select
              id="user-role"
              {...register("role")}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="viewer">Visualizador (viewer)</option>
              <option value="technician">Técnico de Campo (technician)</option>
              <option value="engineer">Engenheiro (engineer)</option>
              <option value="admin">Administrador (admin)</option>
            </select>
            {selectedRole && USER_ROLE_LABELS[selectedRole] && (
              <p className="text-[11px] text-muted-foreground mt-1">
                {USER_ROLE_LABELS[selectedRole].description}
              </p>
            )}
          </div>

          {isEditing && (
            <div className="flex items-center gap-2 pt-2">
              <input
                id="user-is-active"
                type="checkbox"
                {...register("is_active")}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <Label htmlFor="user-is-active" className="text-xs font-medium cursor-pointer">
                Usuário ativo no sistema (permite login)
              </Label>
            </div>
          )}

          <DialogFooter className="pt-4 gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
              className="text-xs"
            >
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={isSubmitting} className="text-xs">
              {isSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />}
              {isEditing ? "Salvar Alterações" : "Cadastrar Usuário"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
