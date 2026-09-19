"use client";

import * as React from "react";
import { Camera, FileUp, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { type Attachment } from "../types";
import { listAttachments } from "../api";
import { AttachmentCard } from "./attachment-card";
import { AttachmentUploadDialog } from "./attachment-upload-dialog";
import { PermissionGate } from "@/components/auth/permission-gate";

interface AttachmentsGalleryProps {
  entityType?: string;
  entityId?: string;
  canUpload?: boolean;
  canDelete?: boolean;
  title?: string;
  description?: string;
}

export function AttachmentsGallery({
  entityType,
  entityId,
  canUpload = true,
  canDelete = true,
  title = "Fotos e Anexos Técnicos",
  description = "Documentação fotográfica de campo, diagramas e termos em formato seguro",
}: AttachmentsGalleryProps) {
  const [attachments, setAttachments] = React.useState<Attachment[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = React.useState(false);

  const fetchAttachments = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await listAttachments(entityType, entityId);
      setAttachments(resp.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Falha ao carregar anexos";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [entityType, entityId]);

  React.useEffect(() => {
    fetchAttachments();
  }, [fetchAttachments]);

  const handleCreated = (newAttachment: Attachment) => {
    setAttachments((prev) => [newAttachment, ...prev]);
  };

  const handleDeleted = (deletedId: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== deletedId));
  };

  return (
    <div className="space-y-4">
      {/* Cabeçalho com ações */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b pb-3">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAttachments}
            disabled={loading}
            className="h-8 text-xs"
            title="Atualizar lista"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
            Atualizar
          </Button>

          {canUpload && entityId && entityType && (
            <PermissionGate permission="attachments:write">
              <Button
                size="sm"
                onClick={() => setUploadOpen(true)}
                className="h-8 text-xs"
              >
                <Camera className="h-3.5 w-3.5 mr-1.5" />
                Adicionar Anexo / Foto
              </Button>
            </PermissionGate>
          )}
        </div>
      </div>

      {/* Conteúdo da Galeria */}
      {loading ? (
        <div className="flex flex-col items-center justify-center p-12 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
          <p className="text-sm">Carregando anexos seguros...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive font-medium mb-2">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchAttachments}>
            Tentar novamente
          </Button>
        </div>
      ) : attachments.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center bg-muted/10">
          <FileUp className="h-10 w-10 text-muted-foreground/60 mb-2" />
          <h4 className="text-sm font-medium">Nenhum anexo ou foto cadastrada</h4>
          <p className="text-xs text-muted-foreground max-w-sm mt-1">
            Capture fotos de caixas, postes, fusões ou anexe documentos PDF autorizados.
          </p>
          {canUpload && entityId && entityType && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setUploadOpen(true)}
              className="mt-4"
            >
              <Camera className="h-3.5 w-3.5 mr-1.5" />
              Tirar Foto / Enviar Arquivo
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {attachments.map((att) => (
            <AttachmentCard
              key={att.id}
              attachment={att}
              onDeleted={handleDeleted}
              canDelete={canDelete}
            />
          ))}
        </div>
      )}

      {/* Diálogo de Upload */}
      {entityId && entityType && (
        <AttachmentUploadDialog
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          entityId={entityId}
          entityType={entityType}
          onSuccess={handleCreated}
        />
      )}
    </div>
  );
}
