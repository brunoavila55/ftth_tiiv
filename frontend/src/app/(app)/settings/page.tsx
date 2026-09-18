import * as React from "react";
import type { Metadata } from "next";
import { SettingsView } from "@/features/settings/components/settings-view";

export const metadata: Metadata = {
  title: "Configurações da Aplicação | FTTH Manager",
  description: "Parâmetros operacionais da organização, padrões de código de cores e configurações do sistema",
};

export default function SettingsPage() {
  return (
    <div className="container mx-auto py-4 sm:py-6 px-4 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight">
          Configurações e Parâmetros da Aplicação
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Identidade operacional, fuso horário oficial de Brasília, catálogos de normas técnicas e governança.
        </p>
      </div>

      <React.Suspense
        fallback={
          <div className="p-8 text-center text-xs text-muted-foreground">
            Carregando configurações…
          </div>
        }
      >
        <SettingsView />
      </React.Suspense>
    </div>
  );
}
