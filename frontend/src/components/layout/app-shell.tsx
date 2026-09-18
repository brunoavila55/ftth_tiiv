"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { ConnectionStatusBanner } from "@/components/layout/connection-status-banner";
import { GlobalSearchDialog } from "@/components/ui/global-search-dialog";
import { cn } from "@/lib/utils";

export interface AppShellProps {
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
}

const SIDEBAR_COLLAPSED_KEY = "ftth:sidebar-collapsed";

export function AppShell({ children, className, contentClassName }: AppShellProps) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [searchOpen, setSearchOpen] = React.useState(false);

  // Carrega preferência persistida da sidebar
  React.useEffect(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
      if (stored !== null) {
        setCollapsed(stored === "true");
      }
    } catch {
      // Ignora erro de acesso ao localStorage em contextos restritos
    }
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      } catch {
        // Ignora erro de escrita
      }
      return next;
    });
  };

  const pathname = usePathname();
  const isMapRoute = pathname === "/map" || pathname?.startsWith("/map/");

  return (
    <div className={cn("flex h-screen w-full overflow-hidden bg-background text-foreground", className)}>
      {/* Skip Link para acessibilidade de teclado (WCAG 2.2 AA) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-ring font-medium text-xs"
      >
        Pular para o conteúdo principal
      </a>

      {/* Sidebar lateral (Desktop + Mobile Drawer) */}
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={toggleCollapsed}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      {/* Área central principal */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Banner de alerta de conexão (offline / restabelecida) */}
        <ConnectionStatusBanner />

        <Header
          onOpenMobileMenu={() => setMobileOpen(true)}
          onOpenSearch={() => setSearchOpen(true)}
        />

        <main
          id="main-content"
          role="main"
          className={cn(
            "flex-1 min-w-0 transition-colors",
            isMapRoute
              ? "flex flex-col h-full overflow-hidden p-0"
              : "overflow-y-auto p-4 sm:p-6 lg:p-8",
            contentClassName
          )}
        >
          {children}
        </main>
      </div>

      {/* Diálogo de busca rápida global acessível por Ctrl+K */}
      <GlobalSearchDialog open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  );
}
