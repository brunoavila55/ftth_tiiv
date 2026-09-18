"use client";

import * as React from "react";

/**
 * Hook para interceptar recarregamento ou fechamento de aba do navegador
 * quando existirem alterações pendentes não salvas em um formulário.
 */
export function useUnsavedChanges(isDirty: boolean, message?: string) {
  const defaultMessage =
    message || "Existem alterações não salvas no formulário. Se você sair agora, os dados serão perdidos.";

  React.useEffect(() => {
    if (!isDirty) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = defaultMessage;
      return defaultMessage;
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isDirty, defaultMessage]);
}
