import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { OpticalBudgetView } from "@/features/optical/components/optical-budget-view";
import * as opticalApi from "@/features/optical/api";
import type { BudgetCalculationResponse } from "@/features/optical/types";

// Mock das chamadas de API
vi.mock("@/features/optical/api", () => ({
  calculateOpticalBudget: vi.fn(),
  listOpticalProfiles: vi.fn(),
  listCustomers: vi.fn(),
  listServiceLinks: vi.fn(),
}));

describe("F13 — Orçamento Óptico e Balanço de Potência (Frontend)", () => {
  const mockAcceptanceResponse: BudgetCalculationResponse = {
    status: "complete",
    direction: "downstream",
    wavelength_nm: 1490,
    topology_revision: 42,
    assumptions: ["TX nominal adotado como limite de referência."],
    missing_fields: [],
    steps: [
      {
        step_number: 1,
        element_type: "mated_pair",
        element_name: "Acoplador DIO",
        parameter_source: "standard",
        unit: "dB",
        individual_value: 0.3,
        loss_db: 0.3,
        accumulated_loss_db: 0.3,
      },
      {
        step_number: 2,
        element_type: "fiber",
        element_name: "Trecho Alimentador (3.5 km)",
        parameter_source: "catalog",
        unit: "m",
        individual_value: 3500.0,
        loss_db: 0.875,
        accumulated_loss_db: 1.175,
      },
      {
        step_number: 3,
        element_type: "splitter",
        element_name: "Splitter Primário 1:8",
        parameter_source: "catalog",
        unit: "dB",
        individual_value: 10.5,
        loss_db: 10.5,
        accumulated_loss_db: 11.675,
      },
      {
        step_number: 4,
        element_type: "fiber",
        element_name: "Trecho Distribuição (3.5 km)",
        parameter_source: "catalog",
        unit: "m",
        individual_value: 3500.0,
        loss_db: 0.875,
        accumulated_loss_db: 12.55,
      },
      {
        step_number: 5,
        element_type: "splitter",
        element_name: "Splitter Secundário 1:8",
        parameter_source: "catalog",
        unit: "dB",
        individual_value: 10.5,
        loss_db: 10.5,
        accumulated_loss_db: 23.05,
      },
      {
        step_number: 6,
        element_type: "fusion",
        element_name: "Fusão 4x",
        parameter_source: "measured",
        unit: "dB",
        individual_value: 0.4,
        loss_db: 0.4,
        accumulated_loss_db: 23.45,
      },
      {
        step_number: 7,
        element_type: "mated_pair",
        element_name: "Acoplador Porta CTO",
        parameter_source: "standard",
        unit: "dB",
        individual_value: 0.3,
        loss_db: 0.3,
        accumulated_loss_db: 23.75,
      },
    ],
    total_loss_db: 23.75,
    tx_dbm: 3.0,
    predicted_rx_dbm: -20.75,
    rx_min_dbm: -22.25,
    rx_max_dbm: -18.75,
    engineering_margin_db: 3.0,
    remaining_margin_db: 3.25,
    overload_headroom_db: 12.75,
    assessment: "pass",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(opticalApi.listOpticalProfiles).mockResolvedValue({
      items: [
        {
          id: "prof-gpon-b",
          name: "GPON Classe B+",
          technology: "GPON",
          wavelength_nm: 1490,
          tx_min_dbm: 1.5,
          tx_max_dbm: 5.0,
          rx_sensitivity_dbm: -27.0,
          rx_overload_dbm: -8.0,
          default_attenuation_db_per_km: 0.25,
          version: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
    });
    vi.mocked(opticalApi.listCustomers).mockResolvedValue({
      items: [
        {
          id: "cust-1",
          code: "CLI-001",
          name: "Carlos Eduardo Silva",
          phone: "11999998888",
          email: "carlos@teste.com",
          version: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    vi.mocked(opticalApi.listServiceLinks).mockResolvedValue({
      items: [
        {
          id: "link-1",
          customer_id: "cust-1",
          onu_device_id: "onu-1",
          port_id: "port-1",
          status: "active",
          activated_at: new Date().toISOString(),
          version: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });
  });

  it("renderiza o aceite numérico sintético B10 / F13 com precisão e formatação pt-BR", async () => {
    vi.mocked(opticalApi.calculateOpticalBudget).mockResolvedValueOnce(mockAcceptanceResponse);

    render(<OpticalBudgetView initialServiceLinkId="link-1" />);

    // Aguarda conclusão do cálculo
    await waitFor(() => {
      expect(screen.getByText("Aprovado")).toBeDefined();
    });

    // 1. TX: +3,00 dBm (preserva sinal +)
    expect(screen.getByText("+3,00 dBm")).toBeDefined();

    // 2. Perda Total: 23,75 dB (aparece no card de métrica e no último passo da tabela)
    expect(screen.getAllByText("23,75 dB").length).toBeGreaterThanOrEqual(1);

    // 3. RX Previsto: -20,75 dBm (preserva sinal -)
    expect(screen.getByText("-20,75 dBm")).toBeDefined();

    // 4. Margem de Engenharia: 3,00 dB
    expect(screen.getAllByText("3,00 dB").length).toBeGreaterThanOrEqual(1);

    // 5. Margem Restante / Líquida: +3,25 dB
    expect(screen.getByText("+3,25 dB")).toBeDefined();

    // 6. Revisão da topologia v42
    expect(screen.getByText("v42")).toBeDefined();

    // 7. Breakdown passo a passo contém os 7 elementos
    expect(screen.getByText("Memória de Cálculo e Atenuação Passo a Passo")).toBeDefined();
    expect(screen.getByText("Acoplador DIO")).toBeDefined();
    expect(screen.getByText("Splitter Primário 1:8")).toBeDefined();
    expect(screen.getByText("Splitter Secundário 1:8")).toBeDefined();
  });

  it("permite alternar entre downstream e upstream mudando o comprimento de onda", async () => {
    vi.mocked(opticalApi.calculateOpticalBudget).mockResolvedValueOnce(mockAcceptanceResponse);

    render(<OpticalBudgetView />);

    // Muda para modo terminal direto para testar interação
    const terminalBtn = screen.getByText("Terminal Direto");
    fireEvent.click(terminalBtn);

    const inputUuid = screen.getByPlaceholderText(/a1b2c3d4/);
    fireEvent.change(inputUuid, { target: { value: "a1b2c3d4-e5f6-7890-abcd-ef1234567890" } });

    // Alterna para Upstream
    const upstreamBtn = screen.getByText(/Upstream/);
    fireEvent.click(upstreamBtn);

    const calcBtn = screen.getByRole("button", { name: /Calcular Orçamento/i });
    fireEvent.click(calcBtn);

    await waitFor(() => {
      expect(opticalApi.calculateOpticalBudget).toHaveBeenCalledWith(
        expect.objectContaining({
          direction: "upstream",
          start_terminal_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        })
      );
    });
  });

  it("exibe status 'Abaixo da Sensibilidade' quando a atenuação é crítica", async () => {
    const belowSensResponse: BudgetCalculationResponse = {
      ...mockAcceptanceResponse,
      predicted_rx_dbm: -29.0,
      total_loss_db: 32.0,
      remaining_margin_db: -5.0,
      assessment: "below_sensitivity",
    };
    vi.mocked(opticalApi.calculateOpticalBudget).mockResolvedValueOnce(belowSensResponse);

    render(<OpticalBudgetView initialServiceLinkId="link-1" />);

    await waitFor(() => {
      expect(screen.getByText("Abaixo da Sensibilidade")).toBeDefined();
      expect(screen.getByText("-29,00 dBm")).toBeDefined();
      expect(screen.getByText("-5,00 dB")).toBeDefined();
    });
  });

  it("exibe status 'Sobrecarga' quando o sinal excede a saturação do receptor", async () => {
    const overloadResponse: BudgetCalculationResponse = {
      ...mockAcceptanceResponse,
      predicted_rx_dbm: -5.0,
      total_loss_db: 8.0,
      assessment: "overload",
    };
    vi.mocked(opticalApi.calculateOpticalBudget).mockResolvedValueOnce(overloadResponse);

    render(<OpticalBudgetView initialServiceLinkId="link-1" />);

    await waitFor(() => {
      expect(screen.getByText("Sobrecarga / Saturação")).toBeDefined();
      expect(screen.getByText("-5,00 dBm")).toBeDefined();
    });
  });

  it("não transforma null em 0 quando há dados insuficientes ou circuito rompido", async () => {
    const insufficientResponse: BudgetCalculationResponse = {
      status: "insufficient_data",
      direction: "downstream",
      topology_revision: 10,
      assumptions: [],
      missing_fields: ["Atenuação da fibra do trecho CEO->CTO não informada"],
      steps: [],
      total_loss_db: null,
      tx_dbm: 3.0,
      predicted_rx_dbm: null,
      engineering_margin_db: 3.0,
      remaining_margin_db: null,
      overload_headroom_db: null,
      assessment: "unknown",
    };
    vi.mocked(opticalApi.calculateOpticalBudget).mockResolvedValueOnce(insufficientResponse);

    render(<OpticalBudgetView initialServiceLinkId="link-1" />);

    await waitFor(() => {
      expect(screen.getByText("Dados Insuficientes")).toBeDefined();
    });

    // Null não vira 0: deve conter "—" em Perda Total e RX Previsto
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);

    // O campo faltante deve ser exibido com alerta
    expect(
      screen.getByText(/Atenuação da fibra do trecho CEO->CTO não informada/)
    ).toBeDefined();
  });
});
