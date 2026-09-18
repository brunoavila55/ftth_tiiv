"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Network, Eye, EyeOff, Loader2, TriangleAlert, Lock, Mail } from "lucide-react";
import { useAuth } from "@/features/auth/auth-context";
import { sanitizeReturnUrl } from "@/features/auth/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ThemeToggle } from "@/components/theme-toggle";
import { ApiError } from "@/lib/api/types";
import { getCsrf } from "@/features/auth/api";
import { setCachedCsrfToken } from "@/lib/api/csrf";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isAuthenticated, isLoading: authLoading } = useAuth();

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const rawReturnUrl = searchParams.get("returnUrl") || searchParams.get("redirect");
  const targetUrl = React.useMemo(() => sanitizeReturnUrl(rawReturnUrl, "/"), [rawReturnUrl]);

  // Inicializa o token e cookie CSRF no carregamento da tela
  React.useEffect(() => {
    getCsrf()
      .then((res) => {
        if (res?.csrf_token) {
          setCachedCsrfToken(res.csrf_token);
        }
      })
      .catch(() => {});
  }, []);

  // Se já estiver autenticado, redireciona para o destino
  React.useEffect(() => {
    if (isAuthenticated && !authLoading) {
      router.replace(targetUrl);
    }
  }, [isAuthenticated, authLoading, router, targetUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setErrorMessage("Por favor, informe seu e-mail corporativo.");
      return;
    }

    if (!password) {
      setErrorMessage("Por favor, informe sua senha de acesso.");
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: cleanEmail, password });
      router.replace(targetUrl);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setErrorMessage("E-mail ou senha incorretos. Verifique suas credenciais.");
        } else if (err.status === 403) {
          setErrorMessage(err.detail || "Acesso negado. Token de segurança expirado ou usuário suspenso.");
        } else {
          setErrorMessage(err.detail || err.message);
        }
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Falha de autenticação no servidor FTTH. Tente novamente.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-muted/40 p-4 sm:p-6 lg:p-8">
      {/* Botão de Tema no Topo Direito */}
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-md space-y-6">
        {/* Identidade Visual */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md">
            <Network className="h-6 w-6" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">FTTH Manager</h1>
          <p className="text-xs text-muted-foreground max-w-xs">
            Documentação física e óptica de rede de telecomunicações
          </p>
        </div>

        {/* Card de Autenticação */}
        <Card className="border-border shadow-lg">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-lg font-semibold text-center">Acesso ao Sistema</CardTitle>
            <CardDescription className="text-center text-xs">
              Entre com suas credenciais para gerenciar a rede óptica
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Alerta de Erro */}
              {errorMessage && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive animate-in fade-in-0"
                >
                  <TriangleAlert className="h-4 w-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
                  <span className="font-medium">{errorMessage}</span>
                </div>
              )}

              {/* Campo E-mail */}
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs font-medium">
                  E-mail corporativo
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="operador@empresa.com.br"
                    autoComplete="email"
                    required
                    disabled={isSubmitting}
                    className="pl-9 text-sm"
                    autoFocus
                  />
                </div>
              </div>

              {/* Campo Senha */}
              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs font-medium">
                  Senha de acesso
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    required
                    disabled={isSubmitting}
                    className="pl-9 pr-10 text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
                    aria-label={showPassword ? "Ocultar senha" : "Exibir senha"}
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Botão Entrar */}
              <Button
                type="submit"
                className="w-full gap-2 mt-2"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    <span>Autenticando...</span>
                  </>
                ) : (
                  <span>Acessar Painel</span>
                )}
              </Button>
            </form>

            {/* Helper de Credenciais de Acesso */}
            <div className="mt-4 pt-3 border-t border-dashed border-border/80">
              <div className="rounded-lg bg-muted/60 p-3 text-xs space-y-2">
                <div className="flex items-center justify-between text-muted-foreground font-medium">
                  <span>Credenciais de Demonstração:</span>
                  <button
                    type="button"
                    onClick={() => {
                      setEmail("admin@provedor.com.br");
                      setPassword("AdminPass123!");
                      setErrorMessage(null);
                    }}
                    className="text-primary hover:underline font-semibold cursor-pointer"
                  >
                    Preencher automático
                  </button>
                </div>
                <div className="font-mono text-[11px] text-foreground bg-background/90 p-2 rounded border border-border/40 space-y-0.5 select-all">
                  <div><span className="text-muted-foreground">E-mail:</span> admin@provedor.com.br</div>
                  <div><span className="text-muted-foreground">Senha:</span> AdminPass123!</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Rodapé de Segurança */}
        <p className="text-center text-[11px] text-muted-foreground">
          Sessão protegida por cookies HttpOnly seguros e CSRF duplo.
          <br />
          FTTH Manager v0.1.0 • Acesso restrito a pessoal autorizado.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-muted/40">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <LoginForm />
    </React.Suspense>
  );
}

