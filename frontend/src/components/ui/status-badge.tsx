import * as React from "react";
import { CheckCircle2, Link2, Clock, TriangleAlert, HelpCircle } from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type OpticalStatus = "free" | "connected" | "reserved" | "damaged" | "unknown";

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  status: OpticalStatus | string;
  showIcon?: boolean;
}

const STATUS_CONFIG: Record<
  OpticalStatus,
  {
    label: string;
    variant: BadgeProps["variant"];
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  free: {
    label: "Livre",
    variant: "free",
    icon: CheckCircle2,
  },
  connected: {
    label: "Conectada",
    variant: "connected",
    icon: Link2,
  },
  reserved: {
    label: "Reservada",
    variant: "reserved",
    icon: Clock,
  },
  damaged: {
    label: "Danificada",
    variant: "damaged",
    icon: TriangleAlert,
  },
  unknown: {
    label: "Não documentada",
    variant: "secondary",
    icon: HelpCircle,
  },
};

export function StatusBadge({
  status,
  showIcon = true,
  className,
  ...props
}: StatusBadgeProps) {
  const normalizedKey = (status?.toLowerCase() as OpticalStatus) || "unknown";
  const config = STATUS_CONFIG[normalizedKey] || STATUS_CONFIG.unknown;
  const Icon = config.icon;

  return (
    <Badge
      variant={config.variant}
      className={cn("gap-1.5 font-medium px-2 py-0.5 text-xs inline-flex items-center", className)}
      {...props}
    >
      {showIcon && <Icon className="h-3.5 w-3.5 flex-shrink-0" />}
      <span>{config.label}</span>
    </Badge>
  );
}
