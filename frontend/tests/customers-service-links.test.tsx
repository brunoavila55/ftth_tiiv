import { describe, it, expect, vi, beforeEach } from "vitest";
import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CtoPortsGrid } from "@/features/customers/components/cto-ports-grid";
import { ServiceLinkDialog } from "@/features/customers/components/service-link-dialog";
import { CustomerDetailView } from "@/features/customers/components/customer-detail-view";
import { CustomersTable } from "@/features/customers/components/customers-table";
import * as customerApi from "@/features/customers/api";
import type { CtoPortOccupancy, CustomerRead, ServiceLinkRead } from "@/features/customers/types";
import type { DeviceRead } from "@/features/inventory/api";

vi.mock("@/features/auth/auth-context", () => import("./support/auth-context-mock"));

// Mock do next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    replace: vi.fn(),
  }),
  usePathname: () => "/customers",
}));

// Mock da API de Clientes e Atendimentos
vi.mock("@/features/customers/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/customers/api")>();
  return {
    ...actual,
    getCtoOccupancy: vi.fn(),
    listCustomers: vi.fn(),
    getCustomer: vi.fn(),
    createCustomer: vi.fn(),
    updateCustomer: vi.fn(),
    deleteCustomer: vi.fn(),
    listServiceLinks: vi.fn(),
    createServiceLink: vi.fn(),
    deactivateServiceLink: vi.fn(),
    listAvailableOnus: vi.fn(),
  };
});

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe("CTOs, Clientes e Atendimentos (F11)", () => {
  // Fixture sintética do critério de aceite F11:
  // CTO de 8 portas com 3 conectadas (2 com cliente + 1 sem cliente) e 1 reservada mostra 4 livres;
  // 1 porta danificada (condição separada de ocupação).
  const mockCtoOccupancy: CtoPortOccupancy = {
    structure_id: "cto-uuid-001",
    total_ports: 8,
    occupied_ports: 3,
    connected_without_customer: 1,
    reserved_ports: 1,
    free_ports: 4,
    ports: [
      {
        id: "port-1",
        name: "Porta 1",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "customer_connected",
        is_damaged: false,
        terminal_id: "term-p1",
        customer: {
          id: "cust-1",
          code: "CLI-10001",
          name: "Maria Silva",
          phone: "(11) 98888-1111",
          email: "maria@provedor.com.br",
        },
        onu: {
          id: "onu-1",
          code: "ONU-1001",
          serial_number: "FHTT12345678",
          model: "AN5506-01-A",
        },
        service_link: {
          id: "link-1",
          status: "active",
          activated_at: "2026-09-01T10:00:00Z",
          version: 1,
          notes: "Drop de 50m",
        },
      },
      {
        id: "port-2",
        name: "Porta 2",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "customer_connected",
        is_damaged: false,
        terminal_id: "term-p2",
        customer: {
          id: "cust-2",
          code: "CLI-10002",
          name: "João Santos",
          phone: "(11) 97777-2222",
        },
        onu: {
          id: "onu-2",
          code: "ONU-1002",
          serial_number: "FHTT87654321",
        },
        service_link: {
          id: "link-2",
          status: "active",
          activated_at: "2026-09-05T14:30:00Z",
          version: 1,
        },
      },
      {
        id: "port-3",
        name: "Porta 3",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "connected_no_customer",
        is_damaged: false,
        terminal_id: "term-p3",
        notes: "Drop instalado em espera",
      },
      {
        id: "port-4",
        name: "Porta 4",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "reserved",
        is_damaged: false,
        terminal_id: "term-p4",
        reservation: {
          id: "res-1",
          reason: "Reserva técnica corporativa",
          reserved_by: "Eng. Roberto",
          expires_at: "2026-12-31T23:59:59Z",
        },
      },
      {
        id: "port-5",
        name: "Porta 5",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "free",
        is_damaged: false,
        terminal_id: "term-p5",
      },
      {
        id: "port-6",
        name: "Porta 6",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "free",
        is_damaged: false,
        terminal_id: "term-p6",
      },
      {
        id: "port-7",
        name: "Porta 7",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "free",
        is_damaged: false,
        terminal_id: "term-p7",
      },
      {
        id: "port-8",
        name: "Porta 8",
        role: "customer_drop",
        connector_type: "SC/APC",
        status: "free",
        is_damaged: true, // Condição mecânica danificada porém status livre
        terminal_id: "term-p8",
        notes: "[Danificada] Trava mecânica quebrada",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(customerApi.getCtoOccupancy).mockResolvedValue(mockCtoOccupancy);
  });

  it("Aceite F11: CTO de 8 portas com 3 conectadas e 1 reservada mostra 4 livres", async () => {
    renderWithQueryClient(
      <CtoPortsGrid structureId="cto-uuid-001" structureCode="CTO-F11-01" />
    );

    // Aguarda carregamento
    await waitFor(() => {
      expect(screen.getByText("Porta 1")).toBeDefined();
    });

    // 1. Valida métricas do painel superior
    // Total de portas = 8
    expect(screen.getByText("Total de Portas")).toBeDefined();
    expect(screen.getByText("8")).toBeDefined();

    // Portas livres = 4
    expect(screen.getByText("Portas Livres")).toBeDefined();
    expect(screen.getByText("4")).toBeDefined();

    // Conectadas = 3 (com subindicação de 1 sem cliente)
    expect(screen.getByText("Conectadas")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("(1 s/ cliente)")).toBeDefined();

    // Reservadas = 1
    expect(screen.getByText("Reservadas")).toBeDefined();
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);

    // Danificadas = 1
    expect(screen.getByText("Danificadas")).toBeDefined();
  });

  it("garante que estado danificado é condição separada de ocupação", async () => {
    renderWithQueryClient(
      <CtoPortsGrid structureId="cto-uuid-001" structureCode="CTO-F11-01" />
    );

    await waitFor(() => {
      expect(screen.getByText("Porta 8")).toBeDefined();
    });

    // Porta 8 é livre para ocupação MAS tem condição mecânica danificada
    const damagedBadges = screen.getAllByText("Danificada");
    expect(damagedBadges.length).toBeGreaterThanOrEqual(1);
  });

  it("permite alternar entre visualização de Grade e Tabela Acessível", async () => {
    renderWithQueryClient(
      <CtoPortsGrid structureId="cto-uuid-001" structureCode="CTO-F11-01" />
    );

    await waitFor(() => {
      expect(screen.getByText("Porta 1")).toBeDefined();
    });

    // Alterna para Tabela Acessível
    const tableBtn = screen.getByTitle("Lista Acessível");
    fireEvent.click(tableBtn);

    // Tabela com atributos semânticos deve estar visível
    const table = screen.getByRole("table", { name: "Lista de Portas da CTO" });
    expect(table).toBeDefined();
    expect(screen.queryByText("Tipo de Conector")).toBeNull(); // No modal ainda não aberto
    expect(screen.getByText("Assinante / Detalhes")).toBeDefined();
  });

  it("clique na porta abre detalhes com identificação de cliente, ONU e drop", async () => {
    renderWithQueryClient(
      <CtoPortsGrid structureId="cto-uuid-001" structureCode="CTO-F11-01" />
    );

    await waitFor(() => {
      expect(screen.getByText("Porta 1")).toBeDefined();
    });

    // Clica na Porta 1 (conectada à Maria Silva)
    const port1Btn = screen.getByText("Porta 1");
    fireEvent.click(port1Btn);

    await waitFor(() => {
      expect(screen.getByText("Assinante Vinculado")).toBeDefined();
      expect(screen.getAllByText("Maria Silva").length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText("CLI-10001").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/ONU-1001/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Ficha do Cliente")).toBeDefined();
      expect(screen.getByText("Desativar Atendimento")).toBeDefined();
    });
  });

  it("mostra conectado sem cliente como situação válida com ação de vinculação", async () => {
    renderWithQueryClient(
      <CtoPortsGrid structureId="cto-uuid-001" structureCode="CTO-F11-01" />
    );

    await waitFor(() => {
      expect(screen.getByText("Porta 3")).toBeDefined();
    });

    // Clica na Porta 3 (conectada sem cliente)
    fireEvent.click(screen.getByText("Porta 3"));

    await waitFor(() => {
      expect(screen.getByText("Drop conectado sem cliente associado")).toBeDefined();
      expect(screen.getByText("Vincular Assinante a esta Porta")).toBeDefined();
    });
  });

  it("executa o fluxo de atendimento em ServiceLinkDialog com prevenção de concorrência", async () => {
    const mockCustomers: CustomerRead[] = [
      {
        id: "cust-10",
        code: "CLI-10010",
        name: "Carlos Ferreira",
        version: 1,
        created_at: "2026-09-10T00:00:00Z",
        updated_at: "2026-09-10T00:00:00Z",
      },
    ];

    const mockOnus: DeviceRead[] = [
      {
        id: "onu-10",
        code: "ONU-9901",
        kind: "onu",
        manufacturer: "FiberHome",
        model: "FiberHome 5506",
        serial_number: "FHTT99990000",
        status: "installed",
        condition: "ok",
        version: 1,
      },
    ];

    vi.mocked(customerApi.listCustomers).mockResolvedValue({
      items: mockCustomers,
      total: 1,
      page: 1,
      page_size: 50,
    });
    vi.mocked(customerApi.listAvailableOnus).mockResolvedValue({
      items: mockOnus,
      total: 1,
      page: 1,
      page_size: 100,
    });

    const onSuccessMock = vi.fn();

    renderWithQueryClient(
      <ServiceLinkDialog
        open={true}
        onOpenChange={vi.fn()}
        structureId="cto-uuid-001"
        structureCode="CTO-F11-01"
        availablePorts={mockCtoOccupancy.ports}
        onSuccess={onSuccessMock}
      />
    );

    // Passo 1: Selecionar Assinante
    await waitFor(() => {
      expect(screen.getByText("Carlos Ferreira")).toBeDefined();
    });
    fireEvent.click(screen.getByText("Carlos Ferreira"));

    // Avançar para Passo 2
    fireEvent.click(screen.getByText("Avançar"));

    // Passo 2: Selecionar Porta da CTO
    await waitFor(() => {
      expect(screen.getByText("Porta Óptica de Atendimento (CTO)")).toBeDefined();
    });
    // Porta 5 está livre
    fireEvent.click(screen.getByText("Porta 5"));

    // Avançar para Passo 3
    fireEvent.click(screen.getByText("Avançar"));

    // Passo 3: Selecionar ONU
    await waitFor(() => {
      expect(screen.getByText("ONU-9901")).toBeDefined();
    });
    fireEvent.click(screen.getByText("ONU-9901"));

    // Avançar para Passo 4
    fireEvent.click(screen.getByText("Avançar"));

    // Passo 4: Revisão
    await waitFor(() => {
      expect(screen.getByText("Resumo do Atendimento Óptico")).toBeDefined();
      expect(screen.getByText("Confirmar Ativação")).toBeDefined();
    });

    // Simula resposta da API
    const mockCreatedLink: ServiceLinkRead = {
      id: "link-created-1",
      customer_id: "cust-10",
      port_id: "port-5",
      onu_device_id: "onu-10",
      status: "active",
      activated_at: "2026-09-18T03:00:00Z",
      version: 1,
      created_at: "2026-09-18T03:00:00Z",
      updated_at: "2026-09-18T03:00:00Z",
    };
    vi.mocked(customerApi.createServiceLink).mockResolvedValue(mockCreatedLink);

    // Submete ativação
    fireEvent.click(screen.getByText("Confirmar Ativação"));

    await waitFor(() => {
      expect(customerApi.createServiceLink).toHaveBeenCalledWith({
        customer_id: "cust-10",
        port_id: "port-5",
        onu_device_id: "onu-10",
        notes: null,
      });
      expect(onSuccessMock).toHaveBeenCalledWith(mockCreatedLink);
    });
  });

  it("trata conflito de concorrência 409 ao tentar vincular porta já em uso", async () => {
    vi.mocked(customerApi.listCustomers).mockResolvedValue({
      items: [
        {
          id: "cust-10",
          code: "CLI-10010",
          name: "Carlos Ferreira",
          version: 1,
          created_at: "2026-09-10T00:00:00Z",
          updated_at: "2026-09-10T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    vi.mocked(customerApi.listAvailableOnus).mockResolvedValue({
      items: [
        {
          id: "onu-10",
          code: "ONU-9901",
          kind: "onu",
          manufacturer: "FiberHome",
          model: "FiberHome 5506",
          status: "installed",
          condition: "ok",
          version: 1,
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    // Simula erro 409 Conflict
    vi.mocked(customerApi.createServiceLink).mockRejectedValue(
      new Error("A porta 'Porta 5' já está associada a um atendimento ativo.")
    );

    renderWithQueryClient(
      <ServiceLinkDialog
        open={true}
        onOpenChange={vi.fn()}
        structureId="cto-uuid-001"
        structureCode="CTO-F11-01"
        availablePorts={mockCtoOccupancy.ports}
        onSuccess={vi.fn()}
      />
    );

    // Pula para o envio
    await waitFor(() => expect(screen.getByText("Carlos Ferreira")).toBeDefined());
    fireEvent.click(screen.getByText("Carlos Ferreira"));
    fireEvent.click(screen.getByText("Avançar"));

    await waitFor(() => expect(screen.getByText("Porta 5")).toBeDefined());
    fireEvent.click(screen.getByText("Porta 5"));
    fireEvent.click(screen.getByText("Avançar"));

    await waitFor(() => expect(screen.getByText("ONU-9901")).toBeDefined());
    fireEvent.click(screen.getByText("ONU-9901"));
    fireEvent.click(screen.getByText("Avançar"));

    await waitFor(() => expect(screen.getByText("Confirmar Ativação")).toBeDefined());
    fireEvent.click(screen.getByText("Confirmar Ativação"));

    // Exibe mensagem de erro RFC 7807 na interface
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
      expect(
        screen.getByText("A porta 'Porta 5' já está associada a um atendimento ativo.")
      ).toBeDefined();
    });
  });

  it("renderiza a ficha do cliente com atendimentos ativos e histórico preservado", async () => {
    const mockCustomerDetail: CustomerRead = {
      id: "cust-1",
      code: "CLI-10001",
      name: "Maria Silva",
      phone: "(11) 98888-1111",
      email: "maria@provedor.com.br",
      address: "Rua das Flores, 123, Bairro Alto",
      notes: "Cliente VIP desde 2024",
      version: 2,
      created_at: "2024-01-10T10:00:00Z",
      updated_at: "2026-09-01T10:00:00Z",
    };

    const mockCustomerLinks: ServiceLinkRead[] = [
      {
        id: "link-active",
        customer_id: "cust-1",
        port_id: "00000000-0000-0000-0000-000000000001",
        onu_device_id: "00000000-0000-0000-0000-000000000002",
        status: "active",
        activated_at: "2026-09-01T10:00:00Z",
        notes: "Instalação Fibra 600M",
        version: 1,
        created_at: "2026-09-01T10:00:00Z",
        updated_at: "2026-09-01T10:00:00Z",
      },
      {
        id: "link-history",
        customer_id: "cust-1",
        port_id: "00000000-0000-0000-0000-000000000099",
        onu_device_id: "00000000-0000-0000-0000-000000000088",
        status: "deactivated",
        activated_at: "2024-02-01T10:00:00Z",
        deactivated_at: "2025-12-15T15:00:00Z",
        notes: "Migração de endereço",
        version: 2,
        created_at: "2024-02-01T10:00:00Z",
        updated_at: "2025-12-15T15:00:00Z",
      },
    ];

    vi.mocked(customerApi.getCustomer).mockResolvedValue(mockCustomerDetail);
    vi.mocked(customerApi.listServiceLinks).mockResolvedValue({
      items: mockCustomerLinks,
      total: 2,
      page: 1,
      page_size: 100,
    });

    renderWithQueryClient(<CustomerDetailView customerId="cust-1" />);

    await waitFor(() => {
      expect(screen.getByText("Maria Silva")).toBeDefined();
      expect(screen.getByText("CLI-10001")).toBeDefined();
      expect(screen.getByText("(11) 98888-1111")).toBeDefined();
      expect(screen.getByText("Rua das Flores, 123, Bairro Alto")).toBeDefined();
    });

    // Atendimento ativo
    expect(screen.getByText("Circuito Ativo")).toBeDefined();
    expect(screen.getByText("Instalação Fibra 600M")).toBeDefined();

    // Histórico de atendimentos anteriores preservado
    expect(screen.getByText("Histórico de Atendimentos Anteriores")).toBeDefined();
    expect(screen.getByText("Migração de endereço")).toBeDefined();
  });
});
