"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  User,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/features/auth/auth-context";
import { NAVIGATION_GROUPS, type NavItem } from "@/lib/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
  className?: string;
}

export function Sidebar({
  collapsed = false,
  onToggleCollapse,
  mobileOpen = false,
  onMobileClose,
  className,
}: SidebarProps) {
  const pathname = usePathname() || "/";
  const { user, logout } = useAuth();

  // Fecha mobile drawer ao mudar de rota
  React.useEffect(() => {
    if (mobileOpen) {
      onMobileClose?.();
    }
  }, [pathname, mobileOpen, onMobileClose]);

  // Tecla Escape para fechar drawer mobile
  React.useEffect(() => {
    if (!mobileOpen || !onMobileClose) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onMobileClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen, onMobileClose]);

  const renderNavGroup = (groupTitle: string, items: NavItem[], isCollapsed: boolean) => {
    return (
      <div key={groupTitle} className="py-2">
        {!isCollapsed && (
          <h3 className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            {groupTitle}
          </h3>
        )}
        <nav aria-label={groupTitle} className="space-y-0.5">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href + "/"));

            return (
              <Link
                key={item.href}
                href={item.href}
                title={isCollapsed ? `${item.title}${item.badge ? ` (${item.badge})` : ""}` : undefined}
                className={cn(
                  "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors relative",
                  isActive
                    ? "bg-primary/10 text-primary font-semibold"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  isCollapsed && "justify-center px-2 py-2.5"
                )}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 flex-shrink-0 transition-transform group-hover:scale-110",
                    isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                  )}
                  aria-hidden="true"
                />

                {!isCollapsed && (
                  <div className="flex flex-1 items-center justify-between min-w-0">
                    <span className="truncate">{item.title}</span>
                    {item.badge && (
                      <Badge
                        variant="secondary"
                        className="ml-2 text-[10px] px-1.5 py-0 font-normal leading-4 border border-border/50 text-muted-foreground/80"
                      >
                        {item.badge}
                      </Badge>
                    )}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>
      </div>
    );
  };

  const sidebarContent = (isCollapsed: boolean, isMobileView: boolean) => (
    <div className="flex h-full flex-col justify-between bg-card">
      {/* Top Brand Header */}
      <div>
        <div
          className={cn(
            "flex h-14 items-center border-b border-border px-3.5",
            isCollapsed ? "justify-center" : "justify-between"
          )}
        >
          <Link
            href="/"
            className={cn(
              "flex items-center gap-2.5 font-bold tracking-tight text-foreground transition-opacity hover:opacity-90",
              isCollapsed && "justify-center"
            )}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <Network className="h-4 w-4" aria-hidden="true" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col min-w-0">
                <span className="text-sm font-bold leading-tight">FTTH Manager</span>
                <span className="text-[10px] font-mono text-muted-foreground leading-none">v0.1.0-alpha</span>
              </div>
            )}
          </Link>

          {isMobileView ? (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground"
              onClick={onMobileClose}
              aria-label="Fechar menu lateral"
            >
              <X className="h-4 w-4" />
            </Button>
          ) : (
            onToggleCollapse && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground hidden lg:flex"
                onClick={onToggleCollapse}
                aria-label={isCollapsed ? "Expandir menu lateral" : "Recolher menu lateral"}
                title={isCollapsed ? "Expandir menu" : "Recolher menu"}
              >
                {isCollapsed ? (
                  <PanelLeftOpen className="h-4 w-4" />
                ) : (
                  <PanelLeftClose className="h-4 w-4" />
                )}
              </Button>
            )
          )}
        </div>

        {/* Navigation list */}
        <div
          className={cn(
            "overflow-y-auto px-2 py-3 space-y-2",
            isCollapsed ? "max-h-[calc(100vh-8rem)]" : "max-h-[calc(100vh-8.5rem)]"
          )}
        >
          {NAVIGATION_GROUPS.map((group) => renderNavGroup(group.title, group.items, isCollapsed))}
        </div>
      </div>

      {/* Bottom Footer: System status & Profile */}
      <div className="border-t border-border p-2 bg-muted/20">
        {!isCollapsed ? (
          <div className="space-y-1.5 px-2 py-1">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="font-medium">Rede Online</span>
              </span>
              <span className="font-mono text-[10px]">v1 API</span>
            </div>

            <div className="flex items-center justify-between pt-1">
              <Link
                href="/profile"
                className="flex items-center gap-2 min-w-0 rounded-md px-1.5 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                title="Abrir perfil e preferências"
              >
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] flex-shrink-0">
                  {user?.name ? user.name.charAt(0).toUpperCase() : <User className="h-3 w-3" />}
                </div>
                <div className="flex flex-col min-w-0">
                  <span className="truncate font-semibold text-foreground leading-none text-xs">
                    {user?.name || "Operador"}
                  </span>
                  <span className="text-[10px] text-muted-foreground capitalize leading-none mt-0.5">
                    {user?.role || "viewer"}
                  </span>
                </div>
              </Link>

              {user ? (
                <button
                  type="button"
                  onClick={() => logout()}
                  className="text-muted-foreground hover:text-destructive p-1 rounded transition-colors"
                  title="Encerrar sessão"
                  aria-label="Encerrar sessão"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              ) : (
                <Link
                  href="/login"
                  className="text-xs text-primary hover:underline"
                  title="Fazer login"
                >
                  Entrar
                </Link>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 py-1">
            <span
              className="h-2 w-2 rounded-full bg-emerald-500"
              title="Rede Online (v1 API)"
              aria-label="Rede Online"
            />
            <Link
              href="/profile"
              className="p-1.5 text-muted-foreground hover:text-foreground rounded"
              title={user ? `${user.name} (${user.role})` : "Perfil do Usuário"}
            >
              <User className="h-4 w-4" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col border-r border-border transition-all duration-200 ease-in-out shrink-0 z-20",
          collapsed ? "w-16" : "w-64",
          className
        )}
      >
        {sidebarContent(collapsed, false)}
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in-0"
            onClick={onMobileClose}
            aria-hidden="true"
          />

          {/* Drawer container */}
          <div className="relative z-50 flex h-full w-72 max-w-[80vw] flex-col border-r border-border bg-card shadow-2xl animate-in slide-in-from-left">
            {sidebarContent(false, true)}
          </div>
        </div>
      )}
    </>
  );
}
