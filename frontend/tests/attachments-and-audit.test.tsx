import * as React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  formatFileSize,
  validateAttachmentFile,
  downloadAttachmentBlob,
} from "@/features/attachments/api";
import { AttachmentsGallery } from "@/features/attachments/components/attachments-gallery";
import { AuditTimeline } from "@/features/audit/components/audit-timeline";
import { type Attachment } from "@/features/attachments/types";
import { type AuditEvent } from "@/features/audit/types";

// Mock do client fetch para download
global.fetch = vi.fn();
URL.createObjectURL = vi.fn(() => "blob:mock-url");
URL.revokeObjectURL = vi.fn();

// Mock do módulo de anexos e auditoria
vi.mock("@/features/attachments/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/attachments/api")>();
  return {
    ...actual,
    listAttachments: vi.fn(),
    deleteAttachment: vi.fn(),
    uploadAttachment: vi.fn(),
  };
});

vi.mock("@/features/audit/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/audit/api")>();
  return {
    ...actual,
    listAuditEvents: vi.fn(),
  };
});

describe("F15 — Fotos, Documentos e Histórico de Auditoria", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Validação de Tipos e Segurança de Arquivos", () => {
    it("aceita arquivos válidos (JPEG, PNG, WebP e PDF)", () => {
      const pngFile = new File(["dummy png content"], "foto_poste.png", { type: "image/png" });
      const jpegFile = new File(["dummy jpg content"], "caixa_ceo.jpg", { type: "image/jpeg" });
      const webpFile = new File(["dummy webp content"], "rack_pop.webp", { type: "image/webp" });
      const pdfFile = new File(["dummy pdf content"], "termo_cliente.pdf", { type: "application/pdf" });

      expect(validateAttachmentFile(pngFile).valid).toBe(true);
      expect(validateAttachmentFile(jpegFile).valid).toBe(true);
      expect(validateAttachmentFile(webpFile).valid).toBe(true);
      expect(validateAttachmentFile(pdfFile).valid).toBe(true);
    });

    it("recusa estritamente arquivos com SVG ativo ou páginas HTML por segurança", () => {
      const svgFile = new File(["<svg><script>alert(1)</script></svg>"], "vector.svg", {
        type: "image/svg+xml",
      });
      const htmlFile = new File(["<html><body>malicious</body></html>"], "doc.html", {
        type: "text/html",
      });
      const maskedSvg = new File(["<svg></svg>"], "hack.svg.png", {
        type: "image/svg+xml",
      });

      const resSvg = validateAttachmentFile(svgFile);
      expect(resSvg.valid).toBe(false);
      expect(resSvg.error).toContain("SVG, scripts ou páginas HTML são proibidos");

      const resHtml = validateAttachmentFile(htmlFile);
      expect(resHtml.valid).toBe(false);

      const resMasked = validateAttachmentFile(maskedSvg);
      expect(resMasked.valid).toBe(false);
    });

    it("recusa arquivos que excedem o limite de 20 MB", () => {
      // Cria arquivo fictício com 21 MB
      const bigFile = new File(["x"], "arquivo_pesado.pdf", { type: "application/pdf" });
      Object.defineProperty(bigFile, "size", { value: 21 * 1024 * 1024 });

      const res = validateAttachmentFile(bigFile);
      expect(res.valid).toBe(false);
      expect(res.error).toContain("limite máximo permitido");
    });

    it("formata tamanho de arquivo de forma legível", () => {
      expect(formatFileSize(500)).toBe("500 B");
      expect(formatFileSize(1536)).toBe("1.5 KB");
      expect(formatFileSize(2097152)).toBe("2.00 MB");
    });
  });

  describe("Download Seguro e Prevenção de Vazamento de Memória", () => {
    it("revoga explicitamente a URL do Blob após disparo do download", async () => {
      const mockBlob = new Blob(["arquivo de teste"], { type: "application/pdf" });
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        blob: async () => mockBlob,
      });

      await downloadAttachmentBlob("00000000-0000-0000-0000-000000000001", "termo.pdf");

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/attachments/00000000-0000-0000-0000-000000000001/download",
        expect.objectContaining({ credentials: "include" })
      );
      expect(URL.createObjectURL).toHaveBeenCalledWith(mockBlob);
      // Garante que URL.revokeObjectURL foi acionado no cleanup
      expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
    });
  });

  describe("Componente AttachmentsGallery", () => {
    const mockAttachments: Attachment[] = [
      {
        id: "att-1",
        entity_id: "site-1",
        entity_type: "site",
        file_name: "foto_rack.png",
        mime_type: "image/png",
        file_size_bytes: 1048576,
        download_url: "/api/v1/attachments/att-1/download",
        thumbnail_url: "/api/v1/attachments/att-1/thumbnail",
        caption: "Rack A01 do POP",
        checksum_sha256: "abc123hash",
        user_id: "user-1",
        version: 1,
        created_at: "2026-09-18T10:00:00Z",
      },
      {
        id: "att-2",
        entity_id: "site-1",
        entity_type: "site",
        file_name: "manual_dio.pdf",
        mime_type: "application/pdf",
        file_size_bytes: 524288,
        download_url: "/api/v1/attachments/att-2/download",
        thumbnail_url: null,
        caption: "Manual do fabricante",
        checksum_sha256: "def456hash",
        user_id: "user-2",
        version: 1,
        created_at: "2026-09-18T10:30:00Z",
      },
    ];

    it("renderiza lista de anexos com miniaturas, badges e tamanhos formatados", async () => {
      const { listAttachments } = await import("@/features/attachments/api");
      (listAttachments as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: mockAttachments,
        total: 2,
        page: 1,
        page_size: 50,
      });

      render(
        <AttachmentsGallery
          entityType="site"
          entityId="site-1"
        />
      );

      await waitFor(() => {
        expect(screen.getByText("foto_rack.png")).toBeDefined();
        expect(screen.getByText("manual_dio.pdf")).toBeDefined();
      });

      expect(screen.getByText("Rack A01 do POP")).toBeDefined();
      expect(screen.getByText("1.00 MB")).toBeDefined();
      expect(screen.getByText("512.0 KB")).toBeDefined();
      expect(screen.getByText("PDF")).toBeDefined();
    });

    it("exibe modal de confirmação antes de remover um anexo", async () => {
      const { listAttachments } = await import("@/features/attachments/api");
      (listAttachments as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [mockAttachments[0]],
        total: 1,
        page: 1,
        page_size: 50,
      });

      render(
        <AttachmentsGallery
          entityType="site"
          entityId="site-1"
        />
      );

      await waitFor(() => {
        expect(screen.getByText("foto_rack.png")).toBeDefined();
      });

      const deleteBtn = screen.getByTitle("Excluir anexo");
      fireEvent.click(deleteBtn);

      expect(screen.getByText("Excluir anexo permanentemente?")).toBeDefined();
      expect(screen.getByText("Cancelar")).toBeDefined();
      expect(screen.getByText("Sim, excluir anexo")).toBeDefined();
    });
  });

  describe("Componente AuditTimeline", () => {
    const mockEvents: AuditEvent[] = [
      {
        id: "ev-1",
        actor_id: "u-1",
        actor_name: "Carlos Engenheiro",
        action: "CONNECTION_CREATED",
        entity_type: "connection",
        entity_id: "conn-10",
        changes: {
          connection_type: "fusion_splice",
          loss_db: 0.05,
        },
        reason: "Emenda troncal para ramal norte",
        request_id: "req-123",
        created_at: "2026-09-18T11:00:00Z",
      },
      {
        id: "ev-2",
        actor_id: "u-2",
        actor_name: "Mariana Técnica",
        action: "ATTACHMENT_UPLOAD",
        entity_type: "site",
        entity_id: "site-1",
        changes: {
          file_name: "rack.png",
        },
        reason: null,
        request_id: null,
        created_at: "2026-09-18T11:15:00Z",
      },
    ];

    it("renderiza trilha de auditoria append-only com atores, ações e motivos em formato somente-leitura", async () => {
      const { listAuditEvents } = await import("@/features/audit/api");
      (listAuditEvents as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: mockEvents,
        total: 2,
        page: 1,
        page_size: 50,
      });

      render(
        <AuditTimeline
          entityType="site"
          entityId="site-1"
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Carlos Engenheiro")).toBeDefined();
        expect(screen.getByText("Mariana Técnica")).toBeDefined();
      });

      expect(screen.getByText("CONNECTION_CREATED")).toBeDefined();
      expect(screen.getByText("ATTACHMENT_UPLOAD")).toBeDefined();
      expect(screen.getByText(/Emenda troncal para ramal norte/)).toBeDefined();

      // Garante que não existem botões de alteração ou mutação de auditoria
      expect(screen.queryByText("Editar")).toBeNull();
      expect(screen.queryByText("Excluir")).toBeNull();
    });

    it("permite expandir e recolher detalhes técnicos das alterações (Antes/Depois)", async () => {
      const { listAuditEvents } = await import("@/features/audit/api");
      (listAuditEvents as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [mockEvents[0]],
        total: 1,
        page: 1,
        page_size: 50,
      });

      render(
        <AuditTimeline
          entityType="connection"
          entityId="conn-10"
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Ver alterações (Antes/Depois)")).toBeDefined();
      });

      const expandBtn = screen.getByText("Ver alterações (Antes/Depois)");
      fireEvent.click(expandBtn);

      expect(screen.getByText("Ocultar detalhes técnicos")).toBeDefined();
      expect(screen.getByText(/"fusion_splice"/)).toBeDefined();
      expect(screen.getByText(/0.05/)).toBeDefined();
    });
  });
});
