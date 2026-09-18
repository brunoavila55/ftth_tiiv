"use client";

import * as React from "react";
import { User, KeyRound, LogOut, CheckCircle2, TriangleAlert, Loader2 } from "lucide-react";
import { useAuth } from "@/features/auth/auth-context";
import { changePassword as apiChangePassword } from "@/features/auth/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ApiError } from "@/lib/api/types";

export default function ProfilePage() {
  const { user, logout, isLoading: authLoading } = useAuth();

  // Troca de Senha State
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [isChangingPassword, setIsChangingPassword] = React.useState(false);
  const [passwordSuccess, setPasswordSuccess] = React.useState<string | null>(null);
  const [passwordError, setPasswordError] = React.useState<string | null>(null);

  // Logout State
  const [logoutDialogOpen, setLogoutDialogOpen] = React.useState(false);
  const [isLoggingOut, setIsLoggingOut] = React.useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordSuccess(null);
    setPasswordError(null);

    if (!currentPassword) {
      setPasswordError("Informe sua senha atual.");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("A nova senha deve ter no mínimo 8 caracteres.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError("A confirmação da nova senha não confere.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await apiChangePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      setPasswordSuccess("Senha alterada com sucesso!");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      if (err instanceof ApiError) {
        setPasswordError(err.detail || err.message);
      } else if (err instanceof Error) {
        setPasswordError(err.message);
      } else {
        setPasswordError("Ocorreu um erro ao alterar a senha. Verifique os dados.");
      }
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
    } finally {
      setIsLoggingOut(false);
      setLogoutDialogOpen(false);
    }
  };

  if (authLoading && !user) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Cabeçalho */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Perfil e Sessão</h1>
        <p className="text-sm text-muted-foreground">
          Gerencie seus dados de acesso, visualize suas permissões e altere sua senha.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Dados do Usuário */}
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <User className="h-4 w-4 text-primary" />
              <span>Informações da Conta</span>
            </CardTitle>
            <CardDescription>Dados cadastrais da sua sessão no FTTH Manager</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground">Nome de exibição</span>
              <p className="text-sm font-semibold text-foreground">{user?.name || "Operador"}</p>
            </div>

            <div className="space-y-1">
              <span className="text-xs text-muted-foreground">E-mail corporativo</span>
              <p className="text-sm font-mono text-foreground">{user?.email || "—"}</p>
            </div>

            <div className="space-y-1">
              <span className="text-xs text-muted-foreground">Perfil de acesso (Papel)</span>
              <div className="mt-1">
                <Badge variant="connected" className="uppercase text-xs font-semibold">
                  {user?.role || "viewer"}
                </Badge>
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-xs text-muted-foreground">Permissões ativas</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {user?.permissions && user.permissions.length > 0 ? (
                  user.permissions.map((p) => (
                    <Badge key={p} variant="secondary" className="font-mono text-[10px]">
                      {p}
                    </Badge>
                  ))
                ) : (
                  <span className="text-xs text-muted-foreground">Somente leitura padrão</span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Formulário Troca de Senha */}
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <KeyRound className="h-4 w-4 text-primary" />
              <span>Alterar Senha</span>
            </CardTitle>
            <CardDescription>Mantenha sua conta corporativa segura</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleChangePassword} className="space-y-3.5">
              {passwordSuccess && (
                <div
                  role="status"
                  className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 p-2.5 text-xs text-emerald-600 dark:text-emerald-400 animate-in fade-in-0"
                >
                  <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                  <span>{passwordSuccess}</span>
                </div>
              )}

              {passwordError && (
                <div
                  role="alert"
                  className="flex items-center gap-2 rounded-md bg-destructive/10 border border-destructive/20 p-2.5 text-xs text-destructive animate-in fade-in-0"
                >
                  <TriangleAlert className="h-4 w-4 flex-shrink-0" />
                  <span>{passwordError}</span>
                </div>
              )}

              <div className="space-y-1">
                <Label htmlFor="current-password" className="text-xs">
                  Senha atual
                </Label>
                <Input
                  id="current-password"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                  disabled={isChangingPassword}
                  className="text-sm"
                  placeholder="••••••••"
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="new-password" className="text-xs">
                  Nova senha (mínimo 8 caracteres)
                </Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  disabled={isChangingPassword}
                  className="text-sm"
                  placeholder="••••••••"
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="confirm-password" className="text-xs">
                  Confirmar nova senha
                </Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  disabled={isChangingPassword}
                  className="text-sm"
                  placeholder="••••••••"
                />
              </div>

              <Button
                type="submit"
                size="sm"
                className="w-full mt-2 gap-2"
                disabled={isChangingPassword}
              >
                {isChangingPassword ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Atualizando...</span>
                  </>
                ) : (
                  <span>Atualizar Senha</span>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Seção Encerrar Sessão */}
      <Card className="border-destructive/20 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-destructive">
            <LogOut className="h-4 w-4" />
            <span>Encerrar Sessão</span>
          </CardTitle>
          <CardDescription>
            Revoga o cookie de sessão HttpOnly no servidor e limpa todo o cache em memória deste navegador.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setLogoutDialogOpen(true)}
            className="gap-2"
          >
            <LogOut className="h-4 w-4" />
            <span>Sair do Sistema</span>
          </Button>
        </CardContent>
      </Card>

      {/* Confirmação de Logout */}
      <ConfirmDialog
        open={logoutDialogOpen}
        onOpenChange={setLogoutDialogOpen}
        title="Encerrar Sessão"
        description="Tem certeza que deseja sair do sistema? O cache local de dados será imediatamente invalidado."
        confirmLabel="Sair Agora"
        cancelLabel="Permanecer"
        variant="destructive"
        isLoading={isLoggingOut}
        onConfirm={handleLogout}
      />
    </div>
  );
}
