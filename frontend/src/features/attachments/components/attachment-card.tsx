"use client";

import * as React from "react";
import { Download, FileText, Image as ImageIcon, Loader2, Trash2, Eye } from "lucide-react";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { type Attachment } from "../types";
import { deleteAttachment, downloadAttachmentBlob, formatFileSize } from "../api";
import { PermissionGate } from "@/components/auth/permission-gate";

interface AttachmentCardProps {
  attachment: Attachment;
  onDeleted: (id: string) => void;
  canDelete?: boolean;
}

export function AttachmentCard({
  attachment,
  onDeleted,
  canDelete = true,
}: AttachmentCardProps) {
  const [downloading, setDownloading] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = React.useState(false);
  const [previewModalOpen, setPreviewModalOpen] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const isImage = attachment.mime_type.startsWith("image/");
  const isPdf = attachment.mime_type === "application/pdf";

  const formattedDate = React.useMemo(() => {
    try {
      return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(attachment.created_at));
    } catch {
      return attachment.created_at;
    }
  }, [attachment.created_at]);

  const handleDownload = async () => {
    setDownloading(true);
    setErrorMessage(null);
    try {
      await downloadAttachmentBlob(attachment.id, attachment.file_name);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Falha ao baixar anexo";
      setErrorMessage(msg);
    } finally {
      setDownloading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    setDeleting(true);
    setErrorMessage(null);
    try {
      await deleteAttachment(attachment.id, attachment.version);
      onDeleted(attachment.id);
      setConfirmDeleteOpen(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Falha ao excluir anexo";
      setErrorMessage(msg);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Card className="overflow-hidden flex flex-col justify-between border shadow-sm hover:shadow-md transition-shadow">
        <CardContent className="p-3 space-y-2">
          {/* Área de Visualização / Miniatura */}
          <div className="relative aspect-video w-full rounded-md bg-muted/40 flex items-center justify-center overflow-hidden border">
            {isImage ? (
              // Miniatura com visualizador seguro
              <div className="relative w-full h-full group">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={attachment.thumbnail_url || attachment.download_url}
                  alt={attachment.caption || attachment.file_name}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                <button
                  type="button"
                  onClick={() => setPreviewModalOpen(true)}
                  className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity cursor-pointer"
                  title="Ampliar visualização"
                >
                  <Eye className="h-6 w-6" />
                </button>
              </div>
            ) : isPdf ? (
              <div className="flex flex-col items-center justify-center text-muted-foreground p-4">
                <FileText className="h-10 w-10 text-primary mb-1" />
                <span className="text-xs font-semibold uppercase tracking-wider text-primary">PDF</span>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center text-muted-foreground p-4">
                <ImageIcon className="h-10 w-10 mb-1" />
                <span className="text-xs">Arquivo</span>
              </div>
            )}
          </div>

          {/* Metadados */}
          <div className="space-y-1">
            <h4 className="text-sm font-semibold truncate" title={attachment.file_name}>
              {attachment.file_name}
            </h4>
            {attachment.caption && (
              <p className="text-xs text-muted-foreground line-clamp-2" title={attachment.caption}>
                {attachment.caption}
              </p>
            )}
            <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
              <span>{formatFileSize(attachment.file_size_bytes)}</span>
              <span>{formattedDate}</span>
            </div>
          </div>

          {errorMessage && (
            <p className="text-xs text-destructive mt-1">{errorMessage}</p>
          )}
        </CardContent>

        <CardFooter className="p-2 pt-0 flex gap-1 border-t bg-muted/10 justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            disabled={downloading || deleting}
            className="h-8 px-2 text-xs"
            title="Download autorizado"
          >
            {downloading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
            ) : (
              <Download className="h-3.5 w-3.5 mr-1" />
            )}
            Baixar
          </Button>

          {canDelete && (
            <PermissionGate permission="attachments:write">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmDeleteOpen(true)}
                disabled={downloading || deleting}
                className="h-8 px-2 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                title="Excluir anexo"
              >
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                Excluir
              </Button>
            </PermissionGate>
          )}
        </CardFooter>
      </Card>

      {/* Diálogo de Confirmação de Exclusão */}
      <ConfirmDialog
        open={confirmDeleteOpen}
        onOpenChange={setConfirmDeleteOpen}
        title="Excluir anexo permanentemente?"
        description={
          <span>
            Esta ação removerá o arquivo físico <strong>{attachment.file_name}</strong> e todos os
            seus metadados. Um registro auditado será gerado. Esta operação não pode ser desfeita.
          </span>
        }
        confirmLabel="Sim, excluir anexo"
        cancelLabel="Cancelar"
        variant="destructive"
        isLoading={deleting}
        onConfirm={handleDeleteConfirm}
      />

      {/* Modal Seguro de Visualização Ampliada */}
      {isImage && (
        <Dialog open={previewModalOpen} onOpenChange={setPreviewModalOpen}>
          <DialogContent className="max-w-3xl max-h-[90vh] p-4 flex flex-col">
            <DialogHeader>
              <DialogTitle className="truncate">{attachment.caption || attachment.file_name}</DialogTitle>
            </DialogHeader>
            <div className="flex-1 overflow-auto flex items-center justify-center bg-black/5 rounded p-2 min-h-[300px]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={attachment.download_url}
                alt={attachment.caption || attachment.file_name}
                className="max-h-[70vh] max-w-full object-contain rounded"
              />
            </div>
            <div className="text-xs text-muted-foreground flex justify-between pt-2">
              <span>{attachment.file_name} • {formatFileSize(attachment.file_size_bytes)}</span>
              <span>{formattedDate}</span>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
