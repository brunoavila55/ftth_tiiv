import * as React from "react";
import Link from "next/link";
import {
  Building2,
  MapPin,
  Box,
  Network,
  Server,
  Cable,
  GitBranch,
  Users,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type EntityType =
  | "site"
  | "structure"
  | "pole"
  | "ceo"
  | "cto"
  | "device"
  | "cable"
  | "splitter"
  | "customer";

export interface EntityLinkProps {
  type: EntityType;
  id: string;
  code?: string | null;
  name?: string | null;
  href?: string;
  showIcon?: boolean;
  className?: string;
}

const ENTITY_ICONS: Record<EntityType, LucideIcon> = {
  site: Building2,
  structure: Box,
  pole: MapPin,
  ceo: Box,
  cto: Network,
  device: Server,
  cable: Cable,
  splitter: GitBranch,
  customer: Users,
};

const ENTITY_ROUTES: Record<EntityType, string> = {
  site: "/sites",
  structure: "/structures",
  pole: "/poles",
  ceo: "/ceos",
  cto: "/ctos",
  device: "/devices",
  cable: "/cables",
  splitter: "/splitters",
  customer: "/customers",
};

export function EntityLink({
  type,
  id,
  code,
  name,
  href,
  showIcon = true,
  className,
}: EntityLinkProps) {
  const Icon = ENTITY_ICONS[type] || Box;
  const targetHref = href || `${ENTITY_ROUTES[type]}/${id}`;

  const displayText = code && name ? `${code} — ${name}` : code || name || `#${id.slice(0, 8)}…`;

  return (
    <Link
      href={targetHref}
      className={cn(
        "inline-flex items-center gap-1.5 font-medium text-foreground hover:text-primary transition-colors text-sm group underline-offset-4 hover:underline",
        className
      )}
      title={`${code || name || id}`}
    >
      {showIcon && (
        <Icon className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary flex-shrink-0 transition-colors" />
      )}
      <span className="truncate max-w-[240px]">{displayText}</span>
    </Link>
  );
}
