"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  Ban,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createImportPreview, commitImport } from "../api";
import { useJobPolling } from "../hooks/use-job-polling";
import type {
  CollisionStrategy,
  ImportPreviewItem,
  ImportPreviewResponse,
} from "../types";

type WizardStep = "upload" | "preview" | "strategy" | "job";

export function ImportWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialJobId = searchParams.get("job_id");

  const [step, setStep] = React.useState<WizardStep>(initialJobId ? "job" : "upload");
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<ImportPreviewResponse | null>(null);
  const [collisionStrategy, setCollisionStrategy] = React.useState<CollisionStrategy>("error");
  const [jobId, setJobId] = React.useState<string | null>(initialJobId);

  const [uploading, setUploading] = React.useState(false);
  const [committing, setCommitting] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  // Chave de idempotência estável por tentativa lógica (não muda em re-cliques)
  const idempotencyKeyRef = React.useRef<string>(
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `ftth-import-${Date.now()}`
  );

  const { job, canceling, cancel } = useJobPolling(jobId);

  // Atualiza URL ao receber jobId para permitir retomada pós-refresh
  React.useEffect(() => {
    if (jobId && !searchParams.get("job_id")) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("job_id", jobId);
      router.replace(`?${params.toString()}`);
    }
  }, [jobId, searchParams, router]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setErrorMessage(null);
    }
  };

  const handleGeneratePreview = async () => {
    if (!file) {
      setErrorMessage("Selecione um arquivo válido para prosseguir.");
      return;
    }

    try {
      setUploading(true);
      setErrorMessage(null);
      const res = await createImportPreview(file);
      setPreview(res);
      setStep("preview");
    } catch (err: unknown) {
      setErrorMessage((err as Error).message || "Falha ao processar arquivo no servidor.");
    } finally {
      setUploading(false);
    }
  };

  const handleCommit = async () => {
    if (!preview) return;

    try {
      setCommitting(true);
      setErrorMessage(null);
      const res = await commitImport(
        preview.import_id,
        collisionStrategy,
        idempotencyKeyRef.current
      );
      setJobId(res.job_id);
      setStep("job");
    } catch (err: unknown) {
      setErrorMessage((err as Error).message || "Falha ao confirmar importação.");
    } finally {
      setCommitting(false);
    }
  };

  const handleReset = () => {
    setStep("upload");
    setFile(null);
    setPreview(null);
    setJobId(null);
    setErrorMessage(null);
    idempotencyKeyRef.current =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `ftth-import-${Date.now()}`;
    router.replace(window.location.pathname);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Indicador de passos */}
      <div className="flex items-center justify-between border-b pb-4 text-sm font-medium">
        <div className="flex items-center gap-2">
          <span
            className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
              step === "upload"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            1
          </span>
          <span className={step === "upload" ? "font-semibold text-foreground" : "text-muted-foreground"}>
            Upload do Arquivo
          </span>
        </div>

        <div className="h-0.5 w-12 bg-border hidden sm:block" />

        <div className="flex items-center gap-2">
          <span
            className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
              step === "preview"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            2
          </span>
          <span className={step === "preview" ? "font-semibold text-foreground" : "text-muted-foreground"}>
            Prévia & Diagnóstico
          </span>
        </div>

        <div className="h-0.5 w-12 bg-border hidden sm:block" />

        <div className="flex items-center gap-2">
          <span
            className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
              step === "strategy"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            3
          </span>
          <span className={step === "strategy" ? "font-semibold text-foreground" : "text-muted-foreground"}>
            Estratégia & Validação
          </span>
        </div>

        <div className="h-0.5 w-12 bg-border hidden sm:block" />

        <div className="flex items-center gap-2">
          <span
            className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
              step === "job"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            4
          </span>
          <span className={step === "job" ? "font-semibold text-foreground" : "text-muted-foreground"}>
            Processamento & Job
          </span>
        </div>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-start gap-3"
        >
          <AlertTriangle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Atenção na Operação</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Passo 1: Upload */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>Selecionar Arquivo para Importação</CardTitle>
            <CardDescription>
              Formatos aceitos: <strong>GeoJSON (.geojson, .json)</strong>, <strong>KML / KMZ (.kml, .kmz)</strong> ou <strong>CSV (.csv)</strong>.
              O arquivo será analisado em memória sem modificar a topologia operacional da rede.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-border rounded-xl p-10 hover:border-primary/50 transition-colors bg-muted/20">
              <Upload className="h-10 w-10 text-muted-foreground mb-4" />
              <label
                htmlFor="import-file-input"
                className="cursor-pointer text-sm font-semibold text-primary hover:underline"
              >
                Clique para selecionar o arquivo
              </label>
              <input
                id="import-file-input"
                type="file"
                className="sr-only"
                accept=".geojson,.json,.kml,.kmz,.csv"
                onChange={handleFileChange}
              />
              <p className="text-xs text-muted-foreground mt-2">
                Limite máximo: 50 MB por arquivo. Proteção nativa contra zip bombs e injeção de fórmulas.
              </p>

              {file && (
                <div className="mt-4 flex items-center gap-2 rounded-lg bg-background border px-4 py-2 text-sm">
                  <FileText className="h-4 w-4 text-primary" />
                  <span className="font-medium text-foreground">{file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <Button
                disabled={!file || uploading}
                onClick={handleGeneratePreview}
                className="gap-2"
              >
                {uploading ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Processando Prévia...
                  </>
                ) : (
                  <>
                    Gerar Prévia
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Passo 2: Prévia & Diagnóstico */}
      {step === "preview" && preview && (
        <div className="space-y-6">
          {/* Banner permanente de isolamento */}
          <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-primary flex-shrink-0" />
            <p className="text-sm text-foreground">
              <strong>Modo de Pré-visualização Ativo:</strong> A rede operacional e o banco de dados não sofreram nenhuma alteração. Nenhuma conexão óptica foi criada automaticamente.
            </p>
          </div>

          {/* Cards de Métricas */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground font-medium uppercase">Total Registros</p>
                <p className="text-2xl font-bold mt-1">{preview.total_records}</p>
                <p className="text-xs text-muted-foreground mt-1">Formato {preview.format.toUpperCase()}</p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground font-medium uppercase">Registros Válidos</p>
                <p className="text-2xl font-bold mt-1 text-emerald-600">{preview.valid_records}</p>
                <p className="text-xs text-emerald-600/80 mt-1">Prontos para inserção</p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground font-medium uppercase">Colisões de Código</p>
                <p className="text-2xl font-bold mt-1 text-amber-600">{preview.collision_records}</p>
                <p className="text-xs text-amber-600/80 mt-1">Já existem no inventário</p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground font-medium uppercase">Erros de Validação</p>
                <p className="text-2xl font-bold mt-1 text-rose-600">{preview.error_records}</p>
                <p className="text-xs text-rose-600/80 mt-1">Impedem transação</p>
              </CardContent>
            </Card>
          </div>

          {/* Tabela de Amostra e Diagnóstico */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Diagnóstico Detalhado por Linha / Feature</CardTitle>
              <CardDescription>
                Exibindo amostra de elementos extraídos com seu respectivo status de validação.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="border rounded-md overflow-hidden">
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground border-b">
                    <tr>
                      <th className="px-4 py-2.5">Linha</th>
                      <th className="px-4 py-2.5">Tipo</th>
                      <th className="px-4 py-2.5">Código Extraído</th>
                      <th className="px-4 py-2.5">Status</th>
                      <th className="px-4 py-2.5">Diagnóstico / Mensagem</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {preview.sample_preview.map((item: ImportPreviewItem, idx: number) => (
                      <tr key={idx} className="hover:bg-muted/30">
                        <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                          {item.line_number}
                        </td>
                        <td className="px-4 py-2.5 font-medium">{item.entity_type}</td>
                        <td className="px-4 py-2.5 font-mono text-xs">{item.entity_code || "—"}</td>
                        <td className="px-4 py-2.5">
                          {item.validation_status === "valid" && (
                            <Badge variant="outline" className="text-emerald-600 border-emerald-300 bg-emerald-50">
                              <CheckCircle2 className="h-3 w-3 mr-1" /> Válido
                            </Badge>
                          )}
                          {item.validation_status === "collision" && (
                            <Badge variant="outline" className="text-amber-600 border-amber-300 bg-amber-50">
                              <AlertTriangle className="h-3 w-3 mr-1" /> Colisão
                            </Badge>
                          )}
                          {item.validation_status === "error" && (
                            <Badge variant="outline" className="text-rose-600 border-rose-300 bg-rose-50">
                              <XCircle className="h-3 w-3 mr-1" /> Erro
                            </Badge>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground">
                          {item.message || "OK para commit"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep("upload")} className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Trocar Arquivo
            </Button>

            <Button onClick={() => setStep("strategy")} className="gap-2">
              Avançar para Estratégia
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Passo 3: Estratégia de Colisão & Confirmação */}
      {step === "strategy" && preview && (
        <Card>
          <CardHeader>
            <CardTitle>Configuração de Tratamento de Colisões</CardTitle>
            <CardDescription>
              Defina o comportamento do sistema caso algum código de entidade já exista no banco de dados.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <label className="flex items-start gap-3 p-4 border rounded-lg cursor-pointer hover:bg-muted/20 transition-colors">
                <input
                  type="radio"
                  name="collision_strategy"
                  value="error"
                  checked={collisionStrategy === "error"}
                  onChange={() => setCollisionStrategy("error")}
                  className="mt-1"
                />
                <div>
                  <p className="font-semibold text-sm">Abortar Transação se Houver Colisão (Recomendado)</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Garante consistência total *All-or-Nothing*. Se houver qualquer código duplicado, toda a operação é revertida sem alterar o banco de dados.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-3 p-4 border rounded-lg cursor-pointer hover:bg-muted/20 transition-colors">
                <input
                  type="radio"
                  name="collision_strategy"
                  value="skip"
                  checked={collisionStrategy === "skip"}
                  onChange={() => setCollisionStrategy("skip")}
                  className="mt-1"
                />
                <div>
                  <p className="font-semibold text-sm">Ignorar Duplicatas (Manter Dados Existentes)</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Insere novos registros e ignora silenciosamente aqueles cujos códigos já existem no inventário.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-3 p-4 border rounded-lg cursor-pointer hover:bg-muted/20 transition-colors">
                <input
                  type="radio"
                  name="collision_strategy"
                  value="replace"
                  checked={collisionStrategy === "replace"}
                  onChange={() => setCollisionStrategy("replace")}
                  className="mt-1"
                />
                <div>
                  <p className="font-semibold text-sm">Substituir / Atualizar Registros Existentes</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Atualiza os atributos técnicos e geometrias dos elementos colidentes mantendo seus IDs internos.
                  </p>
                </div>
              </label>
            </div>

            <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-xs text-amber-800">
              <p className="font-semibold">Aviso de Idempotência</p>
              <p className="mt-1">
                A submissão enviará um cabeçalho único <code>Idempotency-Key</code>. Múltiplos cliques acidentais ou instabilidades de rede não duplicarão entidades na rede.
              </p>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep("preview")} className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                Voltar à Prévia
              </Button>

              <Button
                onClick={handleCommit}
                disabled={committing || (preview.error_records > 0 && collisionStrategy === "error")}
                className="gap-2"
              >
                {committing ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Enviando Lote...
                  </>
                ) : (
                  <>
                    Confirmar e Importar Lote
                    <CheckCircle2 className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Passo 4: Processamento & Job */}
      {step === "job" && (
        <Card>
          <CardHeader>
            <CardTitle>Processamento Assíncrono do Job</CardTitle>
            <CardDescription>
              O backend FTTH Manager está executando a transação via worker seguro em segundo plano.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col items-center justify-center p-8 text-center space-y-4">
              {job?.status === "queued" && (
                <>
                  <Clock className="h-12 w-12 text-amber-500 animate-pulse" />
                  <div>
                    <h3 className="text-base font-semibold">Job na Fila de Execução</h3>
                    <p className="text-xs text-muted-foreground mt-1">Aguardando worker disponível no banco PostgreSQL...</p>
                  </div>
                </>
              )}

              {job?.status === "running" && (
                <>
                  <RefreshCw className="h-12 w-12 text-primary animate-spin" />
                  <div>
                    <h3 className="text-base font-semibold">Importando Entidades...</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Progresso: {job.progress_percentage}% concluído
                    </p>
                  </div>
                  {/* Barra de Progresso */}
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
                    <h3 className="text-base font-semibold text-emerald-600">Importação Concluída com Sucesso!</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Todas as entidades foram persistidas atomicamente e a revisão de rede foi atualizada.
                    </p>
                  </div>
                </>
              )}

              {job?.status === "failed" && (
                <>
                  <XCircle className="h-12 w-12 text-rose-600" />
                  <div>
                    <h3 className="text-base font-semibold text-rose-600">Falha no Processamento da Importação</h3>
                    <p className="text-xs text-muted-foreground mt-1 max-w-md">
                      {job.error_message || "A transação falhou e todas as alterações foram revertidas (All-or-Nothing)."}
                    </p>
                  </div>
                </>
              )}

              {job?.status === "cancelled" && (
                <>
                  <Ban className="h-12 w-12 text-muted-foreground" />
                  <div>
                    <h3 className="text-base font-semibold">Importação Cancelada</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      A execução foi interrompida pelo operador e nenhuma alteração foi mantida.
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Ações */}
            <div className="flex justify-between border-t pt-4">
              {job && (job.status === "queued" || job.status === "running") && (
                <Button
                  variant="destructive"
                  onClick={cancel}
                  disabled={canceling}
                  className="gap-2"
                >
                  <Ban className="h-4 w-4" />
                  {canceling ? "Cancelando..." : "Cancelar Execução"}
                </Button>
              )}

              {job && (job.status === "succeeded" || job.status === "failed" || job.status === "cancelled") && (
                <Button onClick={handleReset} variant="outline" className="gap-2">
                  <RefreshCw className="h-4 w-4" />
                  Nova Importação
                </Button>
              )}

              {job?.status === "succeeded" && (
                <Button onClick={() => router.push("/map")} className="gap-2">
                  Ver no Mapa Operacional
                  <ArrowRight className="h-4 w-4" />
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
