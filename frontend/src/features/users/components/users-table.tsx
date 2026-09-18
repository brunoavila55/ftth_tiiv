"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  UserPlus,
  Search,
  RotateCcw,
  Edit2,
  UserX,
  UserCheck,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  ShieldCheck,
  Shield,
  Eye,
  AlertCircle,
} from "lucide-react";
import { listUsers, deleteUser, updateUser } from "@/features/users/api";
import type { UserRead, UserRole } from "@/features/users/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { LoadingState, EmptyState, ErrorState } from "@/components/ui/state-displays";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { UserFormDialog } from "./user-form-dialog";
import { ApiError } from "@/lib/api/types";

export function UsersTable() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const pageSize = 15;

  const [searchInput, setSearchInput] = React.useState("");
  const [appliedSearch, setAppliedSearch] = React.useState("");

  // Diálogos de formulário e confirmação
  const [isFormOpen, setIsFormOpen] = React.useState(false);
  const [selectedUser, setSelectedUser] = React.useState<UserRead | null>(null);

  const [deactivateUser, setDeactivateUser] = React.useState<UserRead | null>(null);
  const [isDeactivating, setIsDeactivating] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["users", page, appliedSearch],
    queryFn: ({ signal }) =>
      listUsers(
        {
          page,
          page_size: pageSize,
          q: appliedSearch || undefined,
        },
        signal
      ),
    staleTime: 30_000,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setAppliedSearch(searchInput.trim());
  };

  const handleResetSearch = () => {
    setSearchInput("");
    setAppliedSearch("");
    setPage(1);
  };

  const handleOpenCreate = () => {
    setSelectedUser(null);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (user: UserRead) => {
    setSelectedUser(user);
    setIsFormOpen(true);
  };

  const handleConfirmDeactivate = async () => {
    if (!deactivateUser) return;
    setIsDeactivating(true);
    setActionError(null);

    try {
      if (deactivateUser.is_active) {
        // Desativa via DELETE
        await deleteUser(deactivateUser.id);
      } else {
        // Reativa via PATCH
        await updateUser(
          deactivateUser.id,
          { is_active: true },
          deactivateUser.version
        );
      }
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setDeactivateUser(null);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setActionError("Não é permitido desativar o último administrador ativo do sistema.");
        } else {
          setActionError(err.detail || err.message);
        }
      } else if (err instanceof Error) {
        setActionError(err.message);
      } else {
        setActionError("Erro ao alterar o status do usuário.");
      }
    } finally {
      setIsDeactivating(false);
    }
  };

  const items = data?.items ?? [];
  const totalItems = data?.total ?? 0;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;

  const getRoleBadge = (role: UserRole) => {
    switch (role) {
      case "admin":
        return (
          <Badge variant="outline" className="bg-purple-500/10 text-purple-700 border-purple-500/30 dark:text-purple-400 gap-1 text-[11px]">
            <ShieldAlert className="h-3 w-3" />
            <span>Administrador</span>
          </Badge>
        );
      case "engineer":
        return (
          <Badge variant="outline" className="bg-blue-500/10 text-blue-700 border-blue-500/30 dark:text-blue-400 gap-1 text-[11px]">
            <ShieldCheck className="h-3 w-3" />
            <span>Engenheiro</span>
          </Badge>
        );
      case "technician":
        return (
          <Badge variant="outline" className="bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-400 gap-1 text-[11px]">
            <Shield className="h-3 w-3" />
            <span>Técnico</span>
          </Badge>
        );
      case "viewer":
      default:
        return (
          <Badge variant="outline" className="bg-slate-500/10 text-slate-700 border-slate-500/30 dark:text-slate-400 gap-1 text-[11px]">
            <Eye className="h-3 w-3" />
            <span>Visualizador</span>
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Alerta de erro de ação (ex: último admin) */}
      {actionError && (
        <div className="flex items-center justify-between p-3 text-xs rounded-md bg-destructive/10 text-destructive border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{actionError}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActionError(null)}
            className="h-6 text-xs px-2"
          >
            Fechar
          </Button>
        </div>
      )}

      {/* Barra de Ações e Busca */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
        <form onSubmit={handleSearch} className="flex gap-2 w-full sm:w-80">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar por nome ou e-mail..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-9 text-xs h-9"
            />
          </div>
          <Button type="submit" size="sm" className="h-9 text-xs">
            Buscar
          </Button>
          {appliedSearch && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleResetSearch}
              className="h-9 text-xs"
              title="Limpar busca"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          )}
        </form>

        <Button
          onClick={handleOpenCreate}
          size="sm"
          className="h-9 text-xs gap-1.5 w-full sm:w-auto"
        >
          <UserPlus className="h-4 w-4" />
          <span>Novo Usuário</span>
        </Button>
      </div>

      {/* Tabela de Usuários */}
      {isLoading ? (
        <div className="py-12">
          <LoadingState
            message="Consultando operadores e perfis de acesso..."
            description="Carregando lista autorizada de usuários e permissões RBAC."
          />
        </div>
      ) : isError ? (
        <ErrorState
          title="Erro ao carregar usuários"
          error={error}
          onRetry={() => refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Nenhum usuário encontrado"
          description={
            appliedSearch
              ? `Nenhum operador corresponde ao termo "${appliedSearch}".`
              : "Nenhum usuário cadastrado no momento."
          }
          actionLabel={appliedSearch ? "Limpar Busca" : "Cadastrar Primeiro Usuário"}
          onAction={appliedSearch ? handleResetSearch : handleOpenCreate}
        />
      ) : (
        <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 border-b text-muted-foreground uppercase text-[10px] font-semibold tracking-wider">
                <tr>
                  <th className="px-4 py-3">Operador</th>
                  <th className="px-4 py-3">E-mail</th>
                  <th className="px-4 py-3">Perfil RBAC</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-center">Versão</th>
                  <th className="px-4 py-3 text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((user) => (
                  <tr key={user.id} className="hover:bg-muted/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-foreground">
                      {user.name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground font-mono text-[11px]">
                      {user.email}
                    </td>
                    <td className="px-4 py-3">
                      {getRoleBadge(user.role)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge
                        variant={user.is_active ? "outline" : "secondary"}
                        className={`text-[10px] px-2 py-0.5 ${
                          user.is_active
                            ? "bg-emerald-500/10 text-emerald-700 border-emerald-500/30 dark:text-emerald-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {user.is_active ? "Ativo" : "Inativo"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-center text-muted-foreground font-mono text-[11px]">
                      v{user.version}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenEdit(user)}
                          className="h-7 text-xs px-2 gap-1 text-muted-foreground hover:text-foreground"
                          title="Editar usuário"
                        >
                          <Edit2 className="h-3 w-3" />
                          <span>Editar</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeactivateUser(user)}
                          className={`h-7 text-xs px-2 gap-1 ${
                            user.is_active
                              ? "text-destructive hover:bg-destructive/10"
                              : "text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400"
                          }`}
                          title={user.is_active ? "Desativar operador" : "Reativar operador"}
                        >
                          {user.is_active ? (
                            <>
                              <UserX className="h-3 w-3" />
                              <span>Desativar</span>
                            </>
                          ) : (
                            <>
                              <UserCheck className="h-3 w-3" />
                              <span>Reativar</span>
                            </>
                          )}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Paginação */}
          <div className="flex items-center justify-between px-4 py-3 border-t bg-card text-xs text-muted-foreground">
            <div>
              Mostrando {items.length} de {totalItems} operadores
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
                <span className="sr-only">Página anterior</span>
              </Button>
              <span className="text-xs">
                Página {page} de {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
                <span className="sr-only">Próxima página</span>
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Diálogo de Criação/Edição */}
      <UserFormDialog
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        user={selectedUser}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["users"] });
        }}
      />

      {/* Diálogo de Confirmação de Desativação / Reativação */}
      <ConfirmDialog
        open={Boolean(deactivateUser)}
        onOpenChange={(open) => {
          if (!open) setDeactivateUser(null);
        }}
        title={
          deactivateUser?.is_active
            ? `Desativar operador "${deactivateUser?.name}"?`
            : `Reativar operador "${deactivateUser?.name}"?`
        }
        description={
          deactivateUser?.is_active
            ? "O usuário não poderá mais realizar login no sistema nem executar operações de rede. Todas as ações anteriores permanecem registradas na trilha de auditoria."
            : "O usuário terá o acesso restabelecido e poderá autenticar-se normalmente com suas credenciais."
        }
        confirmLabel={deactivateUser?.is_active ? "Sim, Desativar" : "Sim, Reativar"}
        cancelLabel="Cancelar"
        variant={deactivateUser?.is_active ? "destructive" : "default"}
        onConfirm={handleConfirmDeactivate}
        isLoading={isDeactivating}
      />
    </div>
  );
}
