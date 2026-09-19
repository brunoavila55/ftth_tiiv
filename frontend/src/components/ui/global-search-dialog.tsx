"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  CornerDownLeft,
  X,
  Building2,
  Box,
  Cable as CableIcon,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { NAVIGATION_GROUPS, type NavItem } from "@/lib/navigation";
import { Badge } from "@/components/ui/badge";
import { searchGlobal } from "@/features/reports/api";
import { cn } from "@/lib/utils";

export interface GlobalSearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface UnifiedItem {
  id: string;
  type: "page" | "site" | "structure" | "cable";
  title: string;
  subtitle?: string;
  badge?: string;
  icon: LucideIcon;
  href: string;
}

export function GlobalSearchDialog({ open, onOpenChange }: GlobalSearchDialogProps) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const [isSearchingServer, setIsSearchingServer] = React.useState(false);
  const [serverResults, setServerResults] = React.useState<UnifiedItem[]>([]);

  const inputRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);
  const previousActiveElement = React.useRef<HTMLElement | null>(null);

  // Flatten all nav items for searching
  const allNavItems = React.useMemo(() => {
    const list: (NavItem & { groupTitle: string })[] = [];
    for (const group of NAVIGATION_GROUPS) {
      for (const item of group.items) {
        list.push({ ...item, groupTitle: group.title });
      }
    }
    return list;
  }, []);

  // Filter local navigation items based on query
  const filteredNavItems = React.useMemo<UnifiedItem[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return allNavItems.slice(0, 8).map((item) => ({
        id: `nav-${item.href}`,
        type: "page",
        title: item.title,
        subtitle: item.groupTitle,
        badge: item.badge,
        icon: item.icon,
        href: item.href,
      }));
    }

    return allNavItems
      .filter(
        (item) =>
          item.title.toLowerCase().includes(q) ||
          item.description?.toLowerCase().includes(q) ||
          item.href.toLowerCase().includes(q) ||
          item.groupTitle.toLowerCase().includes(q)
      )
      .slice(0, 6)
      .map((item) => ({
        id: `nav-${item.href}`,
        type: "page",
        title: item.title,
        subtitle: `${item.groupTitle}${item.description ? ` • ${item.description}` : ""}`,
        badge: item.badge,
        icon: item.icon,
        href: item.href,
      }));
  }, [allNavItems, query]);

  // Debounced server search with abort controller
  React.useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 3) {
      setServerResults([]);
      setIsSearchingServer(false);
      return;
    }

    setIsSearchingServer(true);
    const controller = new AbortController();

    const timer = setTimeout(async () => {
      try {
        const response = await searchGlobal(trimmed, 10, controller.signal);
        const mapped: UnifiedItem[] = [];

        for (const group of response.groups) {
          for (const item of group.items) {
            if (group.entity_type === "site" || item.entity_type === "site") {
              mapped.push({
                id: `site-${item.id}`,
                type: "site",
                title: item.code,
                subtitle: item.name ? `POP: ${item.name}` : "POP / Site técnico",
                badge: item.status ?? undefined,
                icon: Building2,
                href: `/sites?q=${encodeURIComponent(item.code)}`,
              });
            } else if (
              group.entity_type === "cable" ||
              item.entity_type === "cable"
            ) {
              mapped.push({
                id: `cable-${item.id}`,
                type: "cable",
                title: item.code,
                subtitle: item.name ? `Modelo: ${item.name}` : "Cabo Óptico",
                badge: item.status ?? undefined,
                icon: CableIcon,
                href: `/cables?q=${encodeURIComponent(item.code)}`,
              });
            } else {
              // Structures (CTO, poste, caixa, pedestal)
              const isCto = item.entity_type === "cto";
              mapped.push({
                id: `struct-${item.id}`,
                type: "structure",
                title: item.code,
                subtitle: `Estrutura física (${item.entity_type.toUpperCase()})`,
                badge: item.status ?? undefined,
                icon: Box,
                href: isCto
                  ? `/ctos?q=${encodeURIComponent(item.code)}`
                  : `/poles?q=${encodeURIComponent(item.code)}`,
              });
            }
          }
        }

        setServerResults(mapped);
      } catch (err: unknown) {
        if ((err as Error)?.name !== "AbortError") {
          // Mantém resultados vazios silenciosamente em caso de erro de rede
          setServerResults([]);
        }
      } finally {
        setIsSearchingServer(false);
      }
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  // Combined item list
  const combinedItems = React.useMemo<UnifiedItem[]>(() => {
    return [...filteredNavItems, ...serverResults];
  }, [filteredNavItems, serverResults]);

  // Reset selection index when list changes
  React.useEffect(() => {
    setSelectedIndex(0);
  }, [combinedItems.length]);

  // Focus input and save previous active element
  React.useEffect(() => {
    if (open) {
      previousActiveElement.current = document.activeElement as HTMLElement;
      setQuery("");
      setServerResults([]);
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      previousActiveElement.current?.focus();
    }
  }, [open]);

  // Global Ctrl+K / Cmd+K shortcut
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onOpenChange]);

  const selectItem = (item: UnifiedItem) => {
    onOpenChange(false);
    router.push(item.href);
  };

  // Keyboard navigation inside dialog
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onOpenChange(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < combinedItems.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : combinedItems.length - 1));
    } else if (e.key === "Enter" && combinedItems.length > 0) {
      e.preventDefault();
      selectItem(combinedItems[selectedIndex]);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Busca rápida global"
      onKeyDown={handleKeyDown}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />

      {/* Dialog container */}
      <div className="relative z-50 w-full max-w-xl overflow-hidden rounded-xl border border-border bg-card shadow-2xl animate-in fade-in-0 zoom-in-95">
        {/* Search header */}
        <div className="flex items-center border-b border-border px-4 py-3">
          <Search className="h-5 w-5 text-muted-foreground mr-3 flex-shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls="search-results-list"
            aria-autocomplete="list"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar páginas, POPs, postes, CTOs ou cabos..."
            className="flex-1 bg-transparent text-sm font-medium text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
          {isSearchingServer && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground mr-2" aria-hidden="true" />
          )}
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="text-muted-foreground hover:text-foreground p-1 rounded"
              aria-label="Limpar termo de busca"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Results list */}
        <div
          ref={listRef}
          id="search-results-list"
          role="listbox"
          className="max-h-80 overflow-y-auto p-2 divide-y divide-border/40"
        >
          {combinedItems.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {query.trim().length < 3 ? (
                "Digite ao menos 3 caracteres para pesquisar na rede..."
              ) : (
                <>Nenhum resultado encontrado para &ldquo;{query}&rdquo;</>
              )}
            </div>
          ) : (
            combinedItems.map((item, index) => {
              const Icon = item.icon;
              const isSelected = index === selectedIndex;

              return (
                <div
                  key={item.id}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => selectItem(item)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    "flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm",
                    isSelected
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-foreground hover:bg-accent/60"
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={cn(
                        "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md border",
                        isSelected
                          ? "border-primary/40 bg-primary/10 text-primary"
                          : "border-border bg-muted/50 text-muted-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate">{item.title}</span>
                        {item.type !== "page" && (
                          <span className="text-[10px] uppercase font-mono px-1 py-0.5 rounded bg-muted text-muted-foreground">
                            {item.type}
                          </span>
                        )}
                      </div>
                      {item.subtitle && (
                        <p className="text-xs text-muted-foreground truncate font-normal">
                          {item.subtitle}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {item.badge && (
                      <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">
                        {item.badge}
                      </Badge>
                    )}
                    {isSelected && (
                      <CornerDownLeft className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts helper */}
        <div className="flex items-center justify-between border-t border-border bg-muted/30 px-4 py-2 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                ↑
              </kbd>
              <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                ↓
              </kbd>{" "}
              para navegar
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                ENTER
              </kbd>{" "}
              para abrir
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
              ESC
            </kbd>{" "}
            para fechar
          </span>
        </div>
      </div>
    </div>
  );
}
