import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportWizard } from "@/features/imports_exports/components/import-wizard";
import { ExportWizard } from "@/features/imports_exports/components/export-wizard";
import * as importsExportsApi from "@/features/imports_exports/api";
import type {
  ImportPreviewResponse,
  ImportCommitResponse,
  JobRead,
  ExportResponse,
} from "@/features/imports_exports/types";

// Mock do next/navigation
const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
}));

// Mock do auth context
vi.mock("@/features/auth/auth-context", () => ({
  useAuth: () => ({
    user: {
      id: "admin-1",
      email: "admin@ftth.local",
      name: "Administrador",
      role: "admin",
      permissions: ["imports:write", "imports:read", "exports:write", "exports:read"],
    },
    logout: vi.fn(),
  }),
}));

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

const mockPreviewData: ImportPreviewResponse = {
  import_id: "550e8400-e29b-41d4-a716-446655440000",
  file_hash: "abcdef1234567890",
  format: "geojson",
  total_records: 12,
  valid_records: 10,
  error_records: 1,
  collision_records: 1,
  sample_preview: [
    {
      line_number: 1,
      entity_type: "structure",
      entity_code: "POSTE-001",
      validation_status: "valid",
      message: "OK para commit",
    },
    {
      line_number: 2,
      entity_type: "structure",
      entity_code: "POSTE-002",
      validation_status: "collision",
      message: "Código 'POSTE-002' já existe no banco de dados",
    },
    {
      line_number: 3,
      entity_type: "cable",
      entity_code: "CABO-INV",
      validation_status: "error",
      message: "Coordenadas inválidas para LineString",
    },
  ],
};

const mockRunningJob: JobRead = {
  id: "job-1111-2222",
  type: "import_geojson",
  status: "running",
  progress_percentage: 45,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockSucceededJob: JobRead = {
  id: "job-1111-2222",
  type: "import_geojson",
  status: "succeeded",
  progress_percentage: 100,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  finished_at: new Date().toISOString(),
};

describe("F16 — Assistente de Importação (ImportWizard)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams();
  });

  it("renderiza o passo inicial de upload e solicita arquivo", () => {
    renderWithQuery(<ImportWizard />);

    expect(screen.getByText("Upload do Arquivo")).toBeDefined();
    expect(screen.getByText("Selecionar Arquivo para Importação")).toBeDefined();
    expect(screen.getByText("Clique para selecionar o arquivo")).toBeDefined();
  });

  it("envia arquivo, gera prévia e exibe métricas e banner sem mutação de rede", async () => {
    vi.spyOn(importsExportsApi, "createImportPreview").mockResolvedValue(mockPreviewData);

    renderWithQuery(<ImportWizard />);

    // Simula seleção de arquivo
    const file = new File(['{"type": "FeatureCollection", "features": []}'], "rede.geojson", {
      type: "application/geo+json",
    });
    const input = document.getElementById("import-file-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByText("rede.geojson")).toBeDefined();

    // Clica em Gerar Prévia
    const generateBtn = screen.getByRole("button", { name: /Gerar Prévia/i });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(importsExportsApi.createImportPreview).toHaveBeenCalledWith(file);
    });

    // Valida banner permanente de isolamento
    await waitFor(() => {
      expect(screen.getByText(/Modo de Pré-visualização Ativo/i)).toBeDefined();
      expect(screen.getByText(/A rede operacional e o banco de dados não sofreram nenhuma alteração/i)).toBeDefined();
    });

    // Valida contadores
    expect(screen.getByText("12")).toBeDefined(); // Total
    expect(screen.getByText("10")).toBeDefined(); // Válidos
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2); // Colisões / Erros / Linha 1

    // Valida linhas da tabela
    expect(screen.getByText("POSTE-001")).toBeDefined();
    expect(screen.getByText("POSTE-002")).toBeDefined();
    expect(screen.getByText("CABO-INV")).toBeDefined();
  });

  it("avança para estratégia de colisão e dispara commit idempotente", async () => {
    vi.spyOn(importsExportsApi, "createImportPreview").mockResolvedValue(mockPreviewData);
    const mockCommitResponse: ImportCommitResponse = {
      job_id: "job-1111-2222",
      message: "Job de importação agendado",
      status: "queued",
    };
    vi.spyOn(importsExportsApi, "commitImport").mockResolvedValue(mockCommitResponse);
    vi.spyOn(importsExportsApi, "getJob").mockResolvedValue(mockRunningJob);

    renderWithQuery(<ImportWizard />);

    const file = new File(["dummy"], "teste.geojson", { type: "application/geo+json" });
    const input = document.getElementById("import-file-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    fireEvent.click(screen.getByRole("button", { name: /Gerar Prévia/i }));

    await waitFor(() => {
      expect(screen.getByText(/Avançar para Estratégia/i)).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: /Avançar para Estratégia/i }));

    expect(screen.getByText("Configuração de Tratamento de Colisões")).toBeDefined();
    expect(screen.getByText(/Abortar Transação se Houver Colisão/i)).toBeDefined();
    expect(screen.getByText(/Ignorar Duplicatas/i)).toBeDefined();

    // Seleciona estratégia "skip" para permitir commit mesmo com erros
    const skipRadio = screen.getByLabelText(/Ignorar Duplicatas/i);
    fireEvent.click(skipRadio);

    // Clica no botão de commit
    const commitBtn = screen.getByRole("button", { name: /Confirmar e Importar Lote/i });
    fireEvent.click(commitBtn);

    await waitFor(() => {
      expect(importsExportsApi.commitImport).toHaveBeenCalledTimes(1);
      const call = vi.mocked(importsExportsApi.commitImport).mock.calls[0];
      expect(call[0]).toBe(mockPreviewData.import_id);
      expect(call[1]).toBe("skip");
      expect(call[2]).toBeDefined(); // idempotency-key presente
    });
  });

  it("retoma job automaticamente quando job_id estiver na URL", async () => {
    mockSearchParams = new URLSearchParams("job_id=job-1111-2222");
    vi.spyOn(importsExportsApi, "getJob").mockResolvedValue(mockSucceededJob);

    renderWithQuery(<ImportWizard />);

    await waitFor(() => {
      expect(importsExportsApi.getJob).toHaveBeenCalledWith("job-1111-2222", expect.anything());
      expect(screen.getByText("Importação Concluída com Sucesso!")).toBeDefined();
      expect(screen.getByText("Ver no Mapa Operacional")).toBeDefined();
    });
  });

  it("permite cancelar job em execução", async () => {
    mockSearchParams = new URLSearchParams("job_id=job-1111-2222");
    vi.spyOn(importsExportsApi, "getJob").mockResolvedValue(mockRunningJob);
    vi.spyOn(importsExportsApi, "cancelJob").mockResolvedValue({
      ...mockRunningJob,
      status: "cancelled",
    });

    renderWithQuery(<ImportWizard />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Cancelar Execução/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: /Cancelar Execução/i }));

    await waitFor(() => {
      expect(importsExportsApi.cancelJob).toHaveBeenCalledWith("job-1111-2222");
    });
  });
});

describe("F16 — Assistente de Exportação (ExportWizard)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams();
  });

  it("renderiza opções de formato e camadas padrão", () => {
    renderWithQuery(<ExportWizard />);

    expect(screen.getByText("Exportação de Dados da Rede")).toBeDefined();
    expect(screen.getByText("GeoJSON")).toBeDefined();
    expect(screen.getByText("KML (Google Earth)")).toBeDefined();
    expect(screen.getByText("Planilha CSV")).toBeDefined();
    expect(screen.getByText("Sites e POPs")).toBeDefined();
    expect(screen.getByText("Cabos e Segmentos de Rota")).toBeDefined();
  });

  it("exibe aviso LGPD quando a camada de clientes é selecionada", () => {
    renderWithQuery(<ExportWizard />);

    const customerCheckbox = screen.getByLabelText(/Clientes e Assinantes/i);
    expect(screen.queryByText(/Proteção de Dados Pessoais \(LGPD\)/i)).toBeNull();

    fireEvent.click(customerCheckbox);

    expect(screen.getByText(/Proteção de Dados Pessoais \(LGPD\)/i)).toBeDefined();
    expect(screen.getByText(/A exportação da camada de clientes contém dados sensíveis/i)).toBeDefined();
  });

  it("solicita exportação e inicia polling do job", async () => {
    const mockExportResponse: ExportResponse = {
      job_id: "export-job-999",
      message: "Exportação solicitada",
    };
    vi.spyOn(importsExportsApi, "requestExport").mockResolvedValue(mockExportResponse);
    vi.spyOn(importsExportsApi, "getJob").mockResolvedValue({
      id: "export-job-999",
      type: "export_geojson",
      status: "running",
      progress_percentage: 50,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    renderWithQuery(<ExportWizard />);

    const submitBtn = screen.getByRole("button", { name: /Iniciar Exportação Assíncrona/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(importsExportsApi.requestExport).toHaveBeenCalledWith({
        format: "geojson",
        layers: ["sites", "structures", "cables"],
      });
      expect(screen.getByText("Acompanhamento da Exportação")).toBeDefined();
      expect(screen.getByText(/Progresso: 50%/i)).toBeDefined();
    });
  });

  it("oferece botão de download quando a exportação conclui", async () => {
    mockSearchParams = new URLSearchParams("export_id=export-job-999");
    vi.spyOn(importsExportsApi, "getJob").mockResolvedValue({
      id: "export-job-999",
      type: "export_geojson",
      status: "succeeded",
      progress_percentage: 100,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    vi.spyOn(importsExportsApi, "downloadExportBlob").mockResolvedValue();

    renderWithQuery(<ExportWizard />);

    await waitFor(() => {
      expect(screen.getByText("Arquivo Pronto para Download!")).toBeDefined();
      expect(screen.getByRole("button", { name: /Baixar Arquivo Gerado/i })).toBeDefined();
    });

    const downloadBtn = screen.getByRole("button", { name: /Baixar Arquivo Gerado/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(importsExportsApi.downloadExportBlob).toHaveBeenCalledWith("export-job-999");
    });
  });

  it("trata download expirado (HTTP 410) exibindo opção de nova solicitação", async () => {
    mockSearchParams = new URLSearchParams("export_id=export-job-999");
    vi.spyOn(importsExportsApi, "getJob").mockResolvedValue({
      id: "export-job-999",
      type: "export_geojson",
      status: "succeeded",
      progress_percentage: 100,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    vi.spyOn(importsExportsApi, "downloadExportBlob").mockRejectedValue(
      new Error("O arquivo exportado expirou ou foi removido do servidor.")
    );

    renderWithQuery(<ExportWizard />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Baixar Arquivo Gerado/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: /Baixar Arquivo Gerado/i }));

    await waitFor(() => {
      expect(screen.getByText(/O arquivo exportado expirou/i)).toBeDefined();
      expect(screen.getByRole("button", { name: /Solicitar Nova Exportação/i })).toBeDefined();
    });
  });
});
