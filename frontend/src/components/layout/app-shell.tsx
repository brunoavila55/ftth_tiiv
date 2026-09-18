"use client";

import * as React from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
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

  return (
    <div className={cn("flex h-screen w-full overflow-hidden bg-background text-foreground", className)}>
      {/* Sidebar lateral (Desktop + Mobile Drawer) */}
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={toggleCollapsed}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      {/* Área central principal */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header
          onOpenMobileMenu={() => setMobileOpen(true)}
          onOpenSearch={() => setSearchOpen(true)}
        />

        <main
          id="main-content"
          role="main"
          className={cn(
            "flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 transition-colors",
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
