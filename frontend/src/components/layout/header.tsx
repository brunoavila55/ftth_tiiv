"use client";

import * as React from "react";
import { Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

export interface HeaderProps {
  onOpenMobileMenu?: () => void;
  onOpenSearch?: () => void;
  className?: string;
}

export function Header({ onOpenMobileMenu, onOpenSearch, className }: HeaderProps) {
  const [isMac, setIsMac] = React.useState(false);

  React.useEffect(() => {
    setIsMac(navigator.platform.toUpperCase().indexOf("MAC") >= 0);
  }, []);

  return (
    <header
      role="banner"
      aria-label="Cabeçalho da aplicação"
      className={cn(
        "sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-md transition-colors",
        className
      )}
    >
      {/* Left side: Hamburger menu (mobile) + Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-11 min-h-[44px] min-w-[44px] md:hidden text-muted-foreground hover:text-foreground"
          onClick={onOpenMobileMenu}
          aria-label="Abrir menu lateral"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="min-w-0 overflow-hidden">
          <Breadcrumbs />
        </div>
      </div>

      {/* Right side: Global Search + Theme Toggle */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenSearch}
          className="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground gap-2 border-border/80 bg-background/50 hover:bg-accent"
          aria-label="Buscar no sistema (Ctrl+K)"
          title="Buscar no sistema"
        >
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Buscar...</span>
          <kbd className="pointer-events-none hidden sm:inline-flex h-4 select-none items-center gap-0.5 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
            {isMac ? "⌘K" : "Ctrl+K"}
          </kbd>
        </Button>

        <ThemeToggle />
      </div>
    </header>
  );
}
