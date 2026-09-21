import { describe, it, expect, vi } from "vitest";
import * as React from "react";
import { existsSync } from "node:fs";
import path from "node:path";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  NAVIGATION_GROUPS,
  ROUTE_SEGMENT_LABELS,
  parseBreadcrumbs,
} from "@/lib/navigation";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import {
  LoadingState,
  EmptyState,
  ErrorState,
  DevFeatureState,
} from "@/components/ui/state-displays";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ApiError } from "@/lib/api/types";
import NotFoundPage from "@/app/not-found";

describe("Navegação e Breadcrumbs (F02 Design System & Shell)", () => {
  it("contém todos os 4 grupos estruturais exigidos pelo frontend.md", () => {
    const groupTitles = NAVIGATION_GROUPS.map((g) => g.title);
    expect(groupTitles).toContain("Visão Geral");
    expect(groupTitles).toContain("Rede Física");
    expect(groupTitles).toContain("Engenharia");
    expect(groupTitles).toContain("Administração");
  });

  it("mapeia as rotas de inventário e engenharia com status 'Em breve' sem simulação falsa", () => {
    const allItems = NAVIGATION_GROUPS.flatMap((g) => g.items);
    const hrefs = allItems.map((i) => i.href);

    // Rotas chave do FTTH Manager
    expect(hrefs).toContain("/dashboard");
    expect(hrefs).toContain("/map");
    expect(hrefs).toContain("/sites");
    expect(hrefs).toContain("/poles");
    expect(hrefs).toContain("/ceos");
    expect(hrefs).toContain("/ctos");
    expect(hrefs).toContain("/cables");
    expect(hrefs).toContain("/splitters");
    expect(hrefs).toContain("/topology");
    expect(hrefs).toContain("/optical-budget");
    expect(hrefs).toContain("/measurements");
    expect(hrefs).toContain("/simulations");
    expect(hrefs).toContain("/audit");
    expect(hrefs).toContain("/settings");
    expect(hrefs).toContain("/settings/users");

    // Valida que nenhum recurso não entregue anuncia falsamente estar pronto
    const devItems = allItems.filter((i) => !i.implemented);
    for (const item of devItems) {
      expect(item.badge).toBe("Em breve");
    }
  });

  it("mantém uma página real para cada item de menu marcado como implementado", () => {
    const implementedItems = NAVIGATION_GROUPS.flatMap((group) => group.items).filter(
      (item) => item.implemented
    );

    for (const item of implementedItems) {
      const routeSegments = item.href.split("/").filter(Boolean);
      const pagePath = path.join(
        process.cwd(),
        "src",
        "app",
        "(app)",
        ...routeSegments,
        "page.tsx"
      );
      expect(existsSync(pagePath), `${item.href} deve possuir page.tsx`).toBe(true);
    }

    expect(
      existsSync(path.join(process.cwd(), "src", "app", "(app)", "[...slug]", "page.tsx")),
      "rotas desconhecidas não podem ser mascaradas por um catch-all"
    ).toBe(false);
  });

  it("converte caminhos de URL para breadcrumbs legíveis em pt-BR", () => {
    // Raiz
    const rootCrumbs = parseBreadcrumbs("/");
    expect(rootCrumbs).toEqual([{ label: "Início", href: "/", isLast: true }]);

    // Rota simples
    const cablesCrumbs = parseBreadcrumbs("/cables");
    expect(cablesCrumbs).toHaveLength(2);
    expect(cablesCrumbs[0]).toEqual({ label: "Início", href: "/", isLast: false });
    expect(cablesCrumbs[1]).toEqual({ label: "Cabos", href: "/cables", isLast: true });

    // Rota aninhada
    const usersCrumbs = parseBreadcrumbs("/settings/users");
    expect(usersCrumbs).toHaveLength(3);
    expect(usersCrumbs[0].label).toBe("Início");
    expect(usersCrumbs[1].label).toBe("Configurações");
    expect(usersCrumbs[2].label).toBe("Usuários");
    expect(usersCrumbs[2].isLast).toBe(true);

    // Rota com UUID e sub-ação
    const uuidPath = "/cables/550e8400-e29b-41d4-a716-446655440000/edit";
    const uuidCrumbs = parseBreadcrumbs(uuidPath);
    expect(uuidCrumbs).toHaveLength(4);
    expect(uuidCrumbs[1].label).toBe("Cabos");
    expect(uuidCrumbs[2].label).toBe("#550e8400…");
    expect(uuidCrumbs[3].label).toBe("Editar");
    expect(uuidCrumbs[3].isLast).toBe(true);
  });

  it("renderiza Breadcrumbs acessível com aria-label e aria-current", () => {
    render(<Breadcrumbs pathname="/ceos" />);

    const nav = screen.getByRole("navigation", { name: "Navegação estrutural" });
    expect(nav).toBeDefined();

    const currentPage = screen.getByText("Caixas CEO");
    expect(currentPage.getAttribute("aria-current")).toBe("page");

    const homeLink = screen.getByRole("link", { name: /início/i });
    expect(homeLink.getAttribute("href")).toBe("/");
  });
});

describe("Página não encontrada", () => {
  it("exibe HTTP 404 e oferece retorno seguro ao painel", () => {
    render(<NotFoundPage />);

    expect(screen.getByText("HTTP 404")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Página não encontrada" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /voltar ao painel/i }).getAttribute("href")).toBe(
      "/dashboard"
    );
  });
});

describe("StateDisplays (Loading, Empty, Error, DevFeature)", () => {
  it("renderiza LoadingState com role='status' e animação", () => {
    render(<LoadingState message="Buscando fusões da CEO..." />);
    const status = screen.getByRole("status");
    expect(status).toBeDefined();
    expect(screen.getByText("Buscando fusões da CEO...")).toBeDefined();
  });

  it("renderiza EmptyState com título, descrição e botão de ação", () => {
    const handleAction = vi.fn();
    render(
      <EmptyState
        title="Nenhum cabo cadastrado"
        description="Cadastre o primeiro cabo troncal ou de distribuição."
        actionLabel="Novo Cabo"
        onAction={handleAction}
      />
    );

    expect(screen.getByText("Nenhum cabo cadastrado")).toBeDefined();
    expect(screen.getByText("Cadastre o primeiro cabo troncal ou de distribuição.")).toBeDefined();

    const btn = screen.getByRole("button", { name: "Novo Cabo" });
    fireEvent.click(btn);
    expect(handleAction).toHaveBeenCalledTimes(1);
  });

  it("renderiza ErrorState exibindo detalhes da ApiError RFC 7807", () => {
    const apiError = new ApiError(
      {
        status: 409,
        title: "Conflito de Conexão",
        detail: "O terminal de fibra especificado já está conectado em outra ponta ativa.",
        code: "terminal_already_connected",
        request_id: "req-ftth-12345",
      },
      409
    );

    const handleRetry = vi.fn();
    render(
      <ErrorState
        title="Falha na Conexão Óptica"
        error={apiError}
        onRetry={handleRetry}
      />
    );

    expect(screen.getByRole("alert")).toBeDefined();
    expect(screen.getByText("Falha na Conexão Óptica")).toBeDefined();
    expect(
      screen.getByText("O terminal de fibra especificado já está conectado em outra ponta ativa.")
    ).toBeDefined();
    expect(screen.getByText("HTTP 409")).toBeDefined();
    expect(screen.getByText("ID: req-ftth-12345")).toBeDefined();

    const retryBtn = screen.getByRole("button", { name: /tentar novamente/i });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it("renderiza DevFeatureState identificando honestamente módulo em desenvolvimento", () => {
    render(
      <DevFeatureState
        title="Visualizador de Rastreamento Óptico"
        stageName="Fase F12"
        description="Módulo de cálculo OTDR e potência fim a fim."
      />
    );

    expect(screen.getByText("Visualizador de Rastreamento Óptico")).toBeDefined();
    expect(screen.getByText("Fase F12")).toBeDefined();
    expect(screen.getByRole("link", { name: /voltar ao início/i })).toBeDefined();
  });
});

describe("ConfirmDialog (Ações Críticas e Destrutivas)", () => {
  it("renderiza alertdialog quando aberto e executa onConfirm", async () => {
    const handleConfirm = vi.fn();
    const handleOpenChange = vi.fn();

    render(
      <ConfirmDialog
        open={true}
        onOpenChange={handleOpenChange}
        title="Remover Splitter"
        description="Tem certeza que deseja remover este splitter 1:8?"
        confirmLabel="Remover"
        onConfirm={handleConfirm}
      />
    );

    expect(screen.getByRole("alertdialog")).toBeDefined();
    expect(screen.getByText("Remover Splitter")).toBeDefined();

    const confirmBtn = screen.getByRole("button", { name: "Remover" });
    fireEvent.click(confirmBtn);
    expect(handleConfirm).toHaveBeenCalledTimes(1);
  });

  it("exige digitação exata de verificationText antes de habilitar confirmação", () => {
    const handleConfirm = vi.fn();
    const handleOpenChange = vi.fn();

    render(
      <ConfirmDialog
        open={true}
        onOpenChange={handleOpenChange}
        title="Desativar Trecho de Cabo"
        description="Esta ação invalidará rotas ópticas."
        confirmLabel="Desativar"
        verificationText="EXCLUIR"
        onConfirm={handleConfirm}
      />
    );

    const confirmBtn = screen.getByRole("button", { name: "Desativar" }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);

    const input = screen.getByLabelText(/Para confirmar, digite/i);
    fireEvent.change(input, { target: { value: "ERRADO" } });
    expect(confirmBtn.disabled).toBe(true);

    fireEvent.change(input, { target: { value: "EXCLUIR" } });
    expect(confirmBtn.disabled).toBe(false);

    fireEvent.click(confirmBtn);
    expect(handleConfirm).toHaveBeenCalledTimes(1);
  });

  it("desabilita botões e impede repetição quando isLoading é true", () => {
    const handleConfirm = vi.fn();
    const handleOpenChange = vi.fn();

    render(
      <ConfirmDialog
        open={true}
        onOpenChange={handleOpenChange}
        title="Excluindo..."
        description="Aguarde o commit atômico."
        confirmLabel="Confirmar"
        isLoading={true}
        onConfirm={handleConfirm}
      />
    );

    const confirmBtn = screen.getByRole("button", { name: "Confirmar" }) as HTMLButtonElement;
    const cancelBtn = screen.getByRole("button", { name: "Cancelar" }) as HTMLButtonElement;

    expect(confirmBtn.disabled).toBe(true);
    expect(cancelBtn.disabled).toBe(true);

    fireEvent.click(confirmBtn);
    expect(handleConfirm).not.toHaveBeenCalled();
  });
});
