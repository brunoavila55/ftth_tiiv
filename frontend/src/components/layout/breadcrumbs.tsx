"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { parseBreadcrumbs } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export interface BreadcrumbsProps {
  pathname?: string;
  className?: string;
}

export function Breadcrumbs({ pathname: propPathname, className }: BreadcrumbsProps) {
  const currentPath = usePathname() || "/";
  const activePath = propPathname !== undefined ? propPathname : currentPath;
  const items = React.useMemo(() => parseBreadcrumbs(activePath), [activePath]);

  // Se estiver na raiz e só houver "Início", podemos ocultar ou mostrar de forma compacta
  if (items.length <= 1) {
    return (
      <nav aria-label="Navegação estrutural" className={cn("flex items-center text-sm", className)}>
        <span className="flex items-center gap-1.5 font-medium text-foreground text-sm">
          <Home className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <span>Início</span>
        </span>
      </nav>
    );
  }

  return (
    <nav aria-label="Navegação estrutural" className={cn("flex items-center text-sm", className)}>
      <ol className="flex items-center space-x-1.5 text-sm">
        {items.map((item, index) => {
          const isFirst = index === 0;
          return (
            <li key={item.href} className="flex items-center space-x-1.5">
              {index > 0 && (
                <ChevronRight
                  className="h-3.5 w-3.5 text-muted-foreground/60 flex-shrink-0"
                  aria-hidden="true"
                />
              )}
              {item.isLast ? (
                <span
                  aria-current="page"
                  className="font-medium text-foreground truncate max-w-[200px]"
                  title={item.label}
                >
                  {item.label}
                </span>
              ) : (
                <Link
                  href={item.href}
                  className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors truncate max-w-[150px]"
                  title={item.label}
                >
                  {isFirst && <Home className="h-3.5 w-3.5" aria-hidden="true" />}
                  <span>{item.label}</span>
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
