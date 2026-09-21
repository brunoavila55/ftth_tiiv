import * as React from "react";
import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <SearchX className="h-7 w-7" aria-hidden="true" />
        </div>
        <p className="mt-5 font-mono text-sm font-semibold text-primary">HTTP 404</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">
          Página não encontrada
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          O endereço informado não corresponde a uma página disponível no FTTH Manager.
        </p>
        <Button asChild className="mt-6 gap-2">
          <Link href="/dashboard">
            <ArrowLeft className="h-4 w-4" />
            Voltar ao painel
          </Link>
        </Button>
      </div>
    </main>
  );
}
