"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getStructure } from "@/features/inventory/api";
import { FusionEditor } from "@/features/connectivity/components/fusion-editor";
import { Button } from "@/components/ui/button";
import { LoadingState, ErrorState } from "@/components/ui/state-displays";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function StructureFusionEditorPage() {
  const params = useParams<{ id: string }>();
  const structureId = params.id;

  const {
    data: structure,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["structures", structureId],
    queryFn: () => getStructure(structureId),
    enabled: Boolean(structureId),
  });

  if (isLoading) {
    return <LoadingState message="Carregando estrutura para o editor de fusões..." />;
  }

  if (isError || !structure) {
    return (
      <ErrorState
        title="Estrutura não encontrada"
        error={error}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Botão de Retorno */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" asChild className="gap-1.5 text-xs">
          <Link href={`/structures/${structureId}`}>
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Voltar para Detalhes da Estrutura</span>
          </Link>
        </Button>
      </div>

      <FusionEditor
        structureId={structureId}
        structureCode={structure.code}
        structureKind={structure.kind}
      />
    </div>
  );
}
