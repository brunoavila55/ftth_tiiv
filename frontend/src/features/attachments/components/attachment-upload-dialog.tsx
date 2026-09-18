"use client";

import * as React from "react";
import { Camera, FileUp, Loader2, X, AlertCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ALLOWED_MIME_TYPES,
  MAX_UPLOAD_SIZE_BYTES,
  formatFileSize,
  uploadAttachment,
  validateAttachmentFile,
} from "../api";
import { type Attachment } from "../types";

interface AttachmentUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entityType: string;
  entityId: string;
  onSuccess: (attachment: Attachment) => void;
}

export function AttachmentUploadDialog({
  open,
  onOpenChange,
  entityType,
  entityId,
  onSuccess,
}: AttachmentUploadDialogProps) {
  const [file, setFile] = React.useState<File | null>(null);
  const [caption, setCaption] = React.useState("");
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Limpeza de Object URL para evitar vazamento de memória
  React.useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    // Validação estrita client-side
    const validation = validateAttachmentFile(selectedFile);
    if (!validation.valid) {
      setError(validation.error || "Arquivo inválido");
      setFile(null);
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        setPreviewUrl(null);
      }
      return;
    }

    setFile(selectedFile);

    // Gerar preview apenas se for imagem suportada
    if (selectedFile.type.startsWith("image/")) {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      const newUrl = URL.createObjectURL(selectedFile);
      setPreviewUrl(newUrl);
    } else {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        setPreviewUrl(null);
      }
    }
  };

  const handleClearFile = () => {
    setFile(null);
    setError(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Selecione um arquivo ou foto para enviar.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const created = await uploadAttachment({
        entity_id: entityId,
        entity_type: entityType,
        caption: caption.trim() || undefined,
        file,
      });

      handleClearFile();
      setCaption("");
      onSuccess(created);
      onOpenChange(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Falha no upload do anexo";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = (nextOpen: boolean) => {
    if (!loading) {
      if (!nextOpen) {
        handleClearFile();
        setCaption("");
      }
      onOpenChange(nextOpen);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileUp className="h-5 w-5 text-primary" />
            Adicionar Anexo ou Foto de Campo
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md bg-destructive/15 p-3 text-sm text-destructive border border-destructive/20"
            >
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="attachment-file">Arquivo ou Captura Mobile</Label>
            <input
              id="attachment-file"
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_MIME_TYPES.join(",")}
              capture="environment"
              onChange={handleFileChange}
              className="hidden"
              disabled={loading}
            />

            {!file ? (
              <div
                onClick={() => fileInputRef.current?.click()}
                className="flex flex-col items-center justify-center border-2 border-dashed border-muted-foreground/30 rounded-lg p-6 cursor-pointer hover:border-primary/50 hover:bg-muted/30 transition-colors"
              >
                <div className="flex gap-2 mb-2 text-muted-foreground">
                  <Camera className="h-8 w-8 text-primary" />
                  <FileUp className="h-8 w-8" />
                </div>
                <p className="text-sm font-medium">Toque para tirar foto ou selecionar arquivo</p>
                <p className="text-xs text-muted-foreground mt-1 text-center">
                  Formatos aceitos: JPEG, PNG, WebP e PDF (máx. {formatFileSize(MAX_UPLOAD_SIZE_BYTES)})
                </p>
              </div>
            ) : (
              <div className="border rounded-lg p-3 bg-muted/20 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="truncate text-sm font-medium max-w-[320px]">{file.name}</div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleClearFile}
                    disabled={loading}
                    className="h-7 w-7 p-0"
                    title="Remover arquivo"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  {file.type || "Desconhecido"} • {formatFileSize(file.size)}
                </p>

                {previewUrl && (
                  <div className="relative mt-2 max-h-48 overflow-hidden rounded border bg-black/5 flex justify-center items-center">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={previewUrl}
                      alt="Pré-visualização do anexo"
                      className="max-h-48 object-contain"
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="attachment-caption">Legenda ou Anotação (Opcional)</Label>
            <Input
              id="attachment-caption"
              placeholder="Ex: Foto frontal do DIO, conector de entrada"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              disabled={loading}
              maxLength={255}
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleClose(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={!file || loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enviando...
                </>
              ) : (
                "Enviar Anexo"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
