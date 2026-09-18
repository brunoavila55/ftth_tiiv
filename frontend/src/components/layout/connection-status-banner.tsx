"use client";

import * as React from "react";
import { useNetworkStatus } from "@/lib/hooks/use-network-status";
import { WifiOff, Wifi, CheckCircle2 } from "lucide-react";

export function ConnectionStatusBanner() {
  const { isOnline, wasOffline } = useNetworkStatus();
  const [showRestored, setShowRestored] = React.useState<boolean>(false);

  React.useEffect(() => {
    if (isOnline && wasOffline) {
      setShowRestored(true);
      const timer = setTimeout(() => {
        setShowRestored(false);
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [isOnline, wasOffline]);

  if (!isOnline) {
    return (
      <div
        role="alert"
        aria-live="assertive"
        className="w-full bg-amber-500 text-amber-950 dark:bg-amber-600 dark:text-amber-50 px-3 py-2 text-xs font-medium border-b border-amber-600/30 flex items-center justify-between gap-2 shadow-sm transition-all"
        data-testid="connection-status-offline"
      >
        <div className="flex items-center gap-2 min-w-0">
          <WifiOff className="h-4 w-4 shrink-0 animate-pulse" aria-hidden="true" />
          <span className="truncate">
            <strong>Sem conexão de rede.</strong> Confirmações no servidor estão bloqueadas para evitar inconsistências. Rascunhos mantidos em memória.
          </span>
        </div>
        <span className="shrink-0 px-2 py-0.5 rounded bg-amber-600/30 text-[10px] font-bold uppercase tracking-wider hidden sm:inline-block">
          Modo Protegido
        </span>
      </div>
    );
  }

  if (showRestored) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="w-full bg-emerald-600 text-white px-3 py-2 text-xs font-medium border-b border-emerald-700 flex items-center justify-between gap-2 shadow-sm transition-all animate-in fade-in slide-in-from-top-1"
        data-testid="connection-status-restored"
      >
        <div className="flex items-center gap-2 min-w-0">
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="truncate">
            <strong>Conexão restabelecida!</strong> Operações de confirmação e salvamento no servidor foram liberadas.
          </span>
        </div>
        <Wifi className="h-4 w-4 shrink-0" aria-hidden="true" />
      </div>
    );
  }

  return null;
}
