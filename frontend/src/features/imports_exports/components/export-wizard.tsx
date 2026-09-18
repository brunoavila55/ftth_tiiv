"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Download,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Ban,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { requestExport, downloadExportBlob } from "../api";
import { useJobPolling } from "../hooks/use-job-polling";
import { useAuth } from "@/features/auth/auth-context";
import type { ExportFormat, ImportFormat } from "../types";

export function ExportWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialExportId = searchParams.get("export_id");

  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [format, setFormat] = React.useState<ExportFormat>("geojson");
  const [selectedLayers, setSelectedLayers] = React.useState<string[]>([
    "sites",
    "structures",
    "cables",
  ]);
  const [exportId, setExportId] = React.useState<string | null>(initialExportId);
  const [requesting, setRequesting] = React.useState(false);
  const [downloading, setDownloading] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [expiredDownload, setExpiredDownload] = React.useState(false);

  const { job, canceling, cancel } = useJobPolling(exportId);

  // Atualiza URL para retomar job após refresh
  React.useEffect(() => {
    if (exportId && !searchParams.get("export_id")) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("export_id", exportId);
      router.replace(`?${params.toString()}`);
    }
  }, [exportId, searchParams, router]);

  const toggleLayer = (layer: string) => {
    if (selectedLayers.includes(layer)) {
      setSelectedLayers(selectedLayers.filter((l) => l !== layer));
    } else {
      setSelectedLayers([...selectedLayers, layer]);
    }
  };

  const handleRequestExport = async () => {
    if (selectedLayers.length === 0) {
      setErrorMessage("Selecione pelo menos uma camada para exportação.");
      return;
    }

    try {
      setRequesting(true);
      setErrorMessage(null);
      setExpiredDownload(false);
      const res = await requestExport({
        format: format as ImportFormat,
        layers: selectedLayers,
      });
      setExportId(res.job_id);
    } catch (err: unknown) {
      setErrorMessage((err as Error).message || "Falha ao registrar solicitação de exportação.");
    } finally {
      setRequesting(false);
    }
  };

  const handleDownload = async () => {
    if (!exportId) return;

    try {
      setDownloading(true);
      setErrorMessage(null);
      await downloadExportBlob(exportId);
    } catch (err: unknown) {
      const msg = (err as Error).message;
      if (msg.includes("expirou") || msg.includes("410")) {
        setExpiredDownload(true);
      }
      setErrorMessage(msg);
    } finally {
      setDownloading(false);
    }
  };

  const handleReset = () => {
    setExportId(null);
    setErrorMessage(null);
    setExpiredDownload(false);
    router.replace(window.location.pathname);
  };

  const hasCustomerLayer = selectedLayers.includes("customers");

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {errorMessage && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-start gap-3"
        >
          <AlertTriangle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Erro na Operação de Exportação</p>
            <p className="mt-1">{errorMessage}</p>
            {expiredDownload && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleReset}
                className="mt-3 gap-1 bg-background text-foreground"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Solicitar Nova Exportação
              </Button>
            )}
          </div>
        </div>
      )}

      {!exportId ? (
        <Card>
          <CardHeader>
            <CardTitle>Exportação de Dados da Rede</CardTitle>
            <CardDescription>
              Gere arquivos GeoJSON, KML ou planilhas CSV com tratamento seguro contra injeção de fórmulas e respeito à LGPD.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Escolha do formato */}
            <div>
              <label className="text-sm font-semibold text-foreground block mb-3">
                1. Selecione o Formato de Saída
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <label
                  className={`flex flex-col p-4 border rounded-lg cursor-pointer transition-colors ${
                    format === "geojson" ? "border-primary bg-primary/5" : "hover:bg-muted/20"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-sm">GeoJSON</span>
                    <input
                      type="radio"
                      name="format"
                      value="geojson"
                      checked={format === "geojson"}
                      onChange={() => setFormat("geojson")}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Padrão aberto RFC 7946 para SIG/GIS com geometria vetorial e atributos completos.
                  </p>
                </label>

                <label
                  className={`flex flex-col p-4 border rounded-lg cursor-pointer transition-colors ${
                    format === "kml" ? "border-primary bg-primary/5" : "hover:bg-muted/20"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-sm">KML (Google Earth)</span>
                    <input
                      type="radio"
                      name="format"
                      value="kml"
                      checked={format === "kml"}
                      onChange={() => setFormat("kml")}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Visualização em 3D e camadas com pastas estruturadas no Google Earth.
                  </p>
                </label>

                <label
                  className={`flex flex-col p-4 border rounded-lg cursor-pointer transition-colors ${
                    format === "csv" ? "border-primary bg-primary/5" : "hover:bg-muted/20"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-sm">Planilha CSV</span>
                    <input
                      type="radio"
                      name="format"
                      value="csv"
                      checked={format === "csv"}
                      onChange={() => setFormat("csv")}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Dados tabulares com neutralização estrita de fórmulas maliciosas de planilhas.
                  </p>
                </label>
              </div>
            </div>

            {/* Escolha das camadas */}
            <div>
              <label className="text-sm font-semibold text-foreground block mb-3">
                2. Selecione as Camadas a Exportar
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-muted/20">
                  <input
                    type="checkbox"
                    checked={selectedLayers.includes("sites")}
                    onChange={() => toggleLayer("sites")}
                    className="rounded"
                  />
                  <div>
                    <p className="text-sm font-medium">Sites e POPs</p>
                    <p className="text-xs text-muted-foreground">Pontos de presença, centrais e armários</p>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-muted/20">
                  <input
                    type="checkbox"
                    checked={selectedLayers.includes("structures")}
                    onChange={() => toggleLayer("structures")}
                    className="rounded"
                  />
                  <div>
                    <p className="text-sm font-medium">Estruturas (Postes, Caixas CEO/CTO)</p>
                    <p className="text-xs text-muted-foreground">Pontos de emenda e atendimento</p>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-muted/20">
                  <input
                    type="checkbox"
                    checked={selectedLayers.includes("cables")}
                    onChange={() => toggleLayer("cables")}
                    className="rounded"
                  />
                  <div>
                    <p className="text-sm font-medium">Cabos e Segmentos de Rota</p>
                    <p className="text-xs text-muted-foreground">Traçados vetoriais e extensões ópticas</p>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-muted/20">
                  <input
                    type="checkbox"
                    checked={hasCustomerLayer}
                    onChange={() => toggleLayer("customers")}
                    className="rounded"
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium">Clientes e Assinantes</p>
                      <Badge variant="outline" className="text-xs text-amber-700 border-amber-300">
                        LGPD / Admin
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">Dados cadastrais de clientes vinculados</p>
                  </div>
                </label>
              </div>
            </div>

            {/* Alerta LGPD */}
            {hasCustomerLayer && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-xs text-amber-800 flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 flex-shrink-0 mt-0.5 text-amber-600" />
                <div>
                  <p className="font-semibold">Proteção de Dados Pessoais (LGPD)</p>
                  <p className="mt-0.5">
                    A exportação da camada de clientes contém dados sensíveis (nomes, telefones e endereços). Esta ação é restrita ao perfil de administrador e é registrada permanentemente na trilha de auditoria do sistema.
                  </p>
                  {!isAdmin && (
                    <p className="mt-1 font-semibold text-destructive">
                      Atenção: Seu usuário não possui papel de administrador. A exportação da camada de clientes será rejeitada pelo servidor.
                    </p>
                  )}
                </div>
              </div>
            )}

            <div className="flex justify-end pt-4 border-t">
              <Button
                onClick={handleRequestExport}
                disabled={requesting || selectedLayers.length === 0}
                className="gap-2"
              >
                {requesting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Registrando Solicitação...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    Iniciar Exportação Assíncrona
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Acompanhamento da Exportação</CardTitle>
            <CardDescription>
              O backend processa a exportação sem sobrecarregar a memória do navegador.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col items-center justify-center p-8 text-center space-y-4">
              {job?.status === "queued" && (
                <>
                  <Clock className="h-12 w-12 text-amber-500 animate-pulse" />
                  <div>
                    <h3 className="text-base font-semibold">Job na Fila de Exportação</h3>
                    <p className="text-xs text-muted-foreground mt-1">Aguardando worker disponível...</p>
                  </div>
                </>
              )}

              {job?.status === "running" && (
                <>
                  <RefreshCw className="h-12 w-12 text-primary animate-spin" />
                  <div>
                    <h3 className="text-base font-semibold">Exportando Entidades...</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Progresso: {job.progress_percentage}%
                    </p>
                  </div>
                  <div className="w-full max-w-md bg-muted rounded-full h-2.5 overflow-hidden">
                    <div
                      className="bg-primary h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${job.progress_percentage}%` }}
                    />
                  </div>
                </>
              )}

              {job?.status === "succeeded" && (
                <>
                  <CheckCircle2 className="h-12 w-12 text-emerald-600" />
                  <div>
                    <h3 className="text-base font-semibold text-emerald-600">Arquivo Pronto para Download!</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      O arquivo foi gerado no servidor e expira em 24 horas.
                    </p>
                  </div>
                  <Button
                    onClick={handleDownload}
                    disabled={downloading}
                    className="gap-2 mt-4"
                  >
                    {downloading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        Baixando Arquivo...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4" />
                        Baixar Arquivo Gerado
                      </>
                    )}
                  </Button>
                </>
              )}

              {job?.status === "failed" && (
                <>
                  <XCircle className="h-12 w-12 text-rose-600" />
                  <div>
                    <h3 className="text-base font-semibold text-rose-600">Falha ao Gerar Exportação</h3>
                    <p className="text-xs text-muted-foreground mt-1 max-w-md">
                      {job.error_message || "Ocorreu um erro no processamento do arquivo no servidor."}
                    </p>
                  </div>
                </>
              )}

              {job?.status === "cancelled" && (
                <>
                  <Ban className="h-12 w-12 text-muted-foreground" />
                  <div>
                    <h3 className="text-base font-semibold">Exportação Cancelada</h3>
                    <p className="text-xs text-muted-foreground mt-1">A solicitação foi interrompida.</p>
                  </div>
                </>
              )}
            </div>

            <div className="flex justify-between border-t pt-4">
              {job && (job.status === "queued" || job.status === "running") && (
                <Button
                  variant="destructive"
                  onClick={cancel}
                  disabled={canceling}
                  className="gap-2"
                >
                  <Ban className="h-4 w-4" />
                  {canceling ? "Cancelando..." : "Cancelar Exportação"}
                </Button>
              )}

              <Button onClick={handleReset} variant="outline" className="gap-2 ml-auto">
                <RefreshCw className="h-4 w-4" />
                Nova Exportação
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
