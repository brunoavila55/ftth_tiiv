import * as React from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface DataTableColumnHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  isSorted?: "asc" | "desc" | false;
  onSort?: (direction: "asc" | "desc" | null) => void;
}

export function DataTableColumnHeader({
  title,
  isSorted = false,
  onSort,
  className,
}: DataTableColumnHeaderProps) {
  if (!onSort) {
    return <div className={cn("text-xs font-semibold text-foreground", className)}>{title}</div>;
  }

  const handleToggle = () => {
    if (isSorted === "asc") {
      onSort("desc");
    } else if (isSorted === "desc") {
      onSort(null);
    } else {
      onSort("asc");
    }
  };

  return (
    <div className={cn("flex items-center space-x-1", className)}>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleToggle}
        className="-ml-3 h-8 text-xs font-semibold data-[state=open]:bg-accent hover:text-foreground text-muted-foreground"
      >
        <span>{title}</span>
        {isSorted === "desc" ? (
          <ArrowDown className="ml-1.5 h-3.5 w-3.5 text-foreground" />
        ) : isSorted === "asc" ? (
          <ArrowUp className="ml-1.5 h-3.5 w-3.5 text-foreground" />
        ) : (
          <ArrowUpDown className="ml-1.5 h-3.5 w-3.5 opacity-50" />
        )}
      </Button>
    </div>
  );
}
