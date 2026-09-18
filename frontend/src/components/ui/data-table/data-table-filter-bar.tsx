"use client";

import * as React from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface DataTableFilterBarProps {
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  isFiltered?: boolean;
  onClearFilters?: () => void;
  children?: React.ReactNode;
  debounceMs?: number;
  className?: string;
}

export function DataTableFilterBar({
  searchValue = "",
  onSearchChange,
  searchPlaceholder = "Filtrar por código ou nome...",
  isFiltered = false,
  onClearFilters,
  children,
  debounceMs = 350,
  className,
}: DataTableFilterBarProps) {
  const [localSearch, setLocalSearch] = React.useState(searchValue);

  // Sincroniza estado local se o valor externo mudar (ex: via URL ou reset)
  React.useEffect(() => {
    setLocalSearch(searchValue);
  }, [searchValue]);

  // Debounce para emissão de busca sem sobrecarregar a API
  React.useEffect(() => {
    if (!onSearchChange) return;
    const timer = setTimeout(() => {
      if (localSearch !== searchValue) {
        onSearchChange(localSearch);
      }
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [localSearch, onSearchChange, searchValue, debounceMs]);

  const handleClear = () => {
    setLocalSearch("");
    onSearchChange?.("");
    onClearFilters?.();
  };

  return (
    <div className={cn("flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 py-3", className)}>
      <div className="flex flex-1 flex-wrap items-center gap-2.5">
        {onSearchChange && (
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              placeholder={searchPlaceholder}
              className="pl-8 text-xs h-9"
              autoComplete="off"
            />
            {localSearch && (
              <button
                type="button"
                onClick={() => {
                  setLocalSearch("");
                  onSearchChange("");
                }}
                className="absolute right-2 top-2 text-muted-foreground hover:text-foreground p-0.5 rounded"
                aria-label="Limpar termo de busca"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}

        {/* Filtros complementares passados como filhos (ex: dropdown de tipo, status) */}
        {children}

        {/* Botão para limpar filtros ativos */}
        {isFiltered && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="h-9 text-xs text-muted-foreground hover:text-foreground gap-1.5 px-2.5"
          >
            <X className="h-3.5 w-3.5" />
            <span>Limpar Filtros</span>
          </Button>
        )}
      </div>
    </div>
  );
}
