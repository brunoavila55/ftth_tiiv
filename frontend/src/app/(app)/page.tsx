"use client";

import * as React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  ArrowRight,
  CheckCircle2,
  Cpu,
  Database,
  Network,
  ShieldCheck,
  LayoutDashboard,
  Building2,
  Trash2,
  Cable,
  Boxes,
} from "lucide-react";

export default function HomePage() {
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const handleConfirmAction = async () => {
    setIsDeleting(true);
    // Simula delay de rede para teste do spinner de loading no ConfirmDialog
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsDeleting(false);
    setConfirmOpen(false);
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Cabeçalho de Boas-vindas */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Visão Geral do Sistema
            </h1>
            <Badge variant="connected">F02–F05 Operacional</Badge>
          </div>
          <p className="text-sm text-muted-foreground max-w-2xl">
            FTTH Manager — Sistema de documentação física e óptica de rede com rastreamento determinístico, GIS e auditoria append-only.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button asChild size="sm" className="gap-1.5">
            <Link href="/dashboard">
              <LayoutDashboard className="h-4 w-4" />
              <span>Painel Operacional</span>
            </Link>
          </Button>

          <Button asChild size="sm" variant="outline" className="gap-1.5">
            <Link href="/sites">
              <Building2 className="h-4 w-4" />
              <span>POPs & Sites</span>
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirmOpen(true)}
            className="gap-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive border-destructive/30"
          >
            <Trash2 className="h-4 w-4" />
            <span>Testar Confirmação</span>
          </Button>
        </div>
      </div>

      {/* Grade de Estado dos Módulos Integrados */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-border">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <Database className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Backend API & PostGIS
              </CardTitle>
              <Badge variant="free">B01–B07 Ativo</Badge>
            </div>
            <CardDescription>FastAPI + PostgreSQL 16 PostGIS + Concorrência Otimista</CardDescription>
          </CardHeader>
          <CardContent className="text-sm space-y-2 text-muted-foreground">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>Inventário físico: Sites, Postes, Caixas CEO/CTO e DIOs</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>GIS espacial: BBox GiST e comprimentos geodésicos</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>Cabos e Fibras: Divisão atômica e continuidade óptica</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>Motor de Fusões B07: Lote atômico, reservas e locks determinísticos</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <Cpu className="w-4 h-4 text-primary" />
                Frontend Shell & Design System
              </CardTitle>
              <Badge variant="connected">Etapas F01–F02</Badge>
            </div>
            <CardDescription>Next.js 15 App Router + Tailwind + shadcn/ui + Lucide</CardDescription>
          </CardHeader>
          <CardContent className="text-sm space-y-2 text-muted-foreground">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              <span>Cliente de API centralizado com tratamento RFC 7807 e CSRF</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              <span>AppShell com Sidebar recolhível e Drawer responsivo para mobile</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              <span>Header com Breadcrumbs hierárquicos em pt-BR e ThemeToggle</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              <span>Busca global via Ctrl+K / ⌘K e diálogos acessíveis de confirmação</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Atalhos Rápidos para Módulos de Rede */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold text-foreground">Acesso Rápido aos Módulos</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            href="/sites"
            className="flex items-center gap-3 p-3.5 rounded-lg border border-border bg-card hover:bg-accent/50 hover:border-primary/40 transition-all text-sm group"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:scale-105 transition-transform">
              <Network className="h-4 w-4" />
            </div>
            <div>
              <p className="font-medium text-foreground">POPs & Sites</p>
              <p className="text-xs text-muted-foreground">Estações técnicas</p>
            </div>
          </Link>

          <Link
            href="/cables"
            className="flex items-center gap-3 p-3.5 rounded-lg border border-border bg-card hover:bg-accent/50 hover:border-primary/40 transition-all text-sm group"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:scale-105 transition-transform">
              <Cable className="h-4 w-4" />
            </div>
            <div>
              <p className="font-medium text-foreground">Cabos Ópticos</p>
              <p className="text-xs text-muted-foreground">Trechos e fibras</p>
            </div>
          </Link>

          <Link
            href="/ceos"
            className="flex items-center gap-3 p-3.5 rounded-lg border border-border bg-card hover:bg-accent/50 hover:border-primary/40 transition-all text-sm group"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:scale-105 transition-transform">
              <Boxes className="h-4 w-4" />
            </div>
            <div>
              <p className="font-medium text-foreground">Caixas CEO</p>
              <p className="text-xs text-muted-foreground">Fusões e bandejas</p>
            </div>
          </Link>

          <Link
            href="/ctos"
            className="flex items-center gap-3 p-3.5 rounded-lg border border-border bg-card hover:bg-accent/50 hover:border-primary/40 transition-all text-sm group"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:scale-105 transition-transform">
              <Network className="h-4 w-4" />
            </div>
            <div>
              <p className="font-medium text-foreground">Caixas CTO</p>
              <p className="text-xs text-muted-foreground">Portas e clientes</p>
            </div>
          </Link>
        </div>
      </div>

      {/* Próximos Passos */}
      <Card className="border-border bg-muted/20">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-primary" />
            Próximo Marco: Autenticação & Sessão (F03)
          </CardTitle>
          <CardDescription>
            Implementação da tela de login com cookie seguro HttpOnly, rota `/auth/me`, logout, CSRF e controle RBAC estrito de rotas.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Button asChild className="gap-2">
              <Link href="/login">
                Ir para Tela de Login (F03)
                <ArrowRight className="w-4 h-4" />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Modal de Confirmação para Teste */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Desativar Trecho de Cabo Óptico"
        description="Esta ação desativará logicamente o cabo selecionado e invalidará todas as rotas ópticas ativas que passam por ele. A ação é registrada na trilha de auditoria."
        confirmLabel="Desativar Trecho"
        cancelLabel="Cancelar"
        variant="destructive"
        verificationText="DESATIVAR"
        isLoading={isDeleting}
        onConfirm={handleConfirmAction}
      />
    </div>
  );
}
