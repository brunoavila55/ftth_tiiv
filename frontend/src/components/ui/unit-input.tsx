"use client";

import * as React from "react";
import { Input, type InputProps } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface UnitInputProps extends Omit<InputProps, "onChange"> {
  unit: string;
  unitPosition?: "left" | "right";
  value?: string | number;
  onChange?: (value: string) => void;
  helperText?: string;
  error?: string;
}

export const UnitInput = React.forwardRef<HTMLInputElement, UnitInputProps>(
  (
    {
      unit,
      unitPosition = "right",
      value,
      onChange,
      helperText,
      error,
      className,
      id,
      ...props
    },
    ref
  ) => {
    const generatedId = React.useId();
    const inputId = id || generatedId;
    const unitId = `${inputId}-unit`;
    const helperId = `${inputId}-helper`;
    const errorId = `${inputId}-error`;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange?.(e.target.value);
    };

    return (
      <div className="w-full space-y-1">
        <div className="relative flex items-center">
          {unitPosition === "left" && (
            <span
              id={unitId}
              className="inline-flex h-9 items-center justify-center rounded-l-md border border-r-0 border-input bg-muted px-3 text-xs font-semibold text-muted-foreground select-none"
            >
              {unit}
            </span>
          )}

          <Input
            id={inputId}
            ref={ref}
            value={value ?? ""}
            onChange={handleChange}
            className={cn(
              unitPosition === "left" && "rounded-l-none",
              unitPosition === "right" && "rounded-r-none",
              error && "border-destructive focus-visible:ring-destructive",
              className
            )}
            aria-describedby={cn(unitId, error ? errorId : helperText ? helperId : undefined)}
            aria-invalid={Boolean(error)}
            {...props}
          />

          {unitPosition === "right" && (
            <span
              id={unitId}
              className="inline-flex h-9 items-center justify-center rounded-r-md border border-l-0 border-input bg-muted px-3 text-xs font-semibold text-muted-foreground select-none"
            >
              {unit}
            </span>
          )}
        </div>

        {error ? (
          <p id={errorId} className="text-xs text-destructive font-medium animate-in fade-in-0">
            {error}
          </p>
        ) : helperText ? (
          <p id={helperId} className="text-xs text-muted-foreground">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

UnitInput.displayName = "UnitInput";
