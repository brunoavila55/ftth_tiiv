import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MeasurementsView } from "@/features/measurements/components/measurements-view";
import { SimulationsView } from "@/features/simulations/components/simulations-view";
import * as measurementsApi from "@/features/measurements/api";
import * as simulationsApi from "@/features/simulations/api";
import type { MeasurementComparisonResponse, MeasurementRead } from "@/features/measurements/types";
import type { OpticalSimulationResponse } from "@/features/simulations/types";

// Mock das APIs
vi.mock("@/features/measurements/api", () => ({
  listMeasurements: vi.fn(),
  createMeasurement: vi.fn(),
  getMeasurement: vi.fn(),
  updateMeasurement: vi.fn(),
  deleteMeasurement: vi.fn(),
  compareMeasurement: vi.fn(),
}));

vi.mock("@/features/simulations/api", () => ({
  simulateOpticalBudget: vi.fn(),
  simulateCableImpact: vi.fn(),
}));

describe("F14 — Medições e Simulações de Engenharia (Frontend)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockMeasurements: MeasurementRead[] = [
    {
      id: "meas-aceite-001",
      terminal_id: "term-cto-001",
      service_link_id: "sl-client-001",
      power_dbm: -25.4,
      wavelength_nm: 1490,
      direction: "downstream",
      origin: "manual_entry",
      instrument_model: "EXFO PPM-350D",
      measured_at: "2026-09-18T03:30:00.000Z",
      user_id: "user-eng-001",
      predicted_power_dbm: -19.3,
      excess_loss_db: 6.1, // Aceite exato: -19.3 - (-25.4) = +6.1 dB
      topology_revision: 42,
      notes: "Medição de aceite na entrada da ONU",
      version: 1,
      created_at: "2026-09-18T03:30:00.000Z",
      updated_at: "2026-09-18T03:30:00.000Z",
    },
    {
      id: "meas-incompatible-002",
      terminal_id: "term-cto-002",
      service_link_id: "sl-client-002",
      power_dbm: -22.0,
      wavelength_nm: 1550, // Comprimento de onda diferente da rota GPON
      direction: "downstream",
      origin: "field_power_meter",
      instrument_model: "Yokogawa AQ2180",
      measured_at: "2026-09-18T03:35:00.000Z",
      user_id: "user-eng-001",
      predicted_power_dbm: null,
      excess_loss_db: null,
      topology_revision: 42,
      notes: "Medição em 1550nm não compatível com GPON",
      version: 1,
      created_at: "2026-09-18T03:35:00.000Z",
      updated_at: "2026-09-18T03:35:00.000Z",
    },
  ];

  it("renderiza a listagem de medições com critério numérico exato (+6,10 dB de perda excedente)", async () => {
    vi.mocked(measurementsApi.listMeasurements).mockResolvedValueOnce({
      items: mockMeasurements,
      total: 2,
    });

    render(<MeasurementsView />);

    expect(screen.getByText("Medições & Potência Óptica")).toBeDefined();

    await waitFor(() => {
      // Potência medida do caso de aceite
      expect(screen.getByText("-25,40 dBm")).toBeDefined();
      // Potência prevista do caso de aceite
      expect(screen.getByText("-19,30 dBm")).toBeDefined();
      // Perda excedente exata (+6,10 dB)
      expect(screen.getByText("+6,10 dB")).toBeDefined();
    });

    // Medição incompatível não gera perda falsa e renderiza "—"
    const dashElements = screen.getAllByText("—");
    expect(dashElements.length).toBeGreaterThanOrEqual(1);
  });

  it("abre modal de comparação detalhada exibindo cálculo explicativo e aviso preventivo de falha", async () => {
    vi.mocked(measurementsApi.listMeasurements).mockResolvedValueOnce({
      items: mockMeasurements,
      total: 2,
    });

    const mockCompResponse: MeasurementComparisonResponse = {
      measurement_id: "meas-aceite-001",
      measured_power_dbm: -25.4,
      predicted_power_dbm: -19.3,
      excess_loss_db: 6.1,
      wavelength_nm: 1490,
      direction: "downstream",
      tolerance_db: 2.0,
      is_within_tolerance: false,
      is_compatible: true,
      incompatibility_reason: null,
      topology_revision: 42,
    };
    vi.mocked(measurementsApi.compareMeasurement).mockResolvedValueOnce(mockCompResponse);

    render(<MeasurementsView />);

    await waitFor(() => {
      expect(screen.getByText("-25,40 dBm")).toBeDefined();
    });

    // Clicar no botão de comparação (ícone Eye)
    const viewButtons = screen.getAllByTitle("Comparar com Orçamento");
    fireEvent.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("Conferência de Potência Óptica")).toBeDefined();
      expect(screen.getByText("Atenuação Excedente")).toBeDefined();
      // Verifica presença da diretriz que alerta que desvio isolado não localiza a falha
      expect(
        screen.getByText(/não localiza a falha nem comprova a causa física/i)
      ).toBeDefined();
    });
  });

  it("renderiza o banner permanente em SimulationsView e executa simulação de overrides antes/depois", async () => {
    const mockSimResponse: OpticalSimulationResponse = {
      baseline: {
        status: "complete",
        direction: "downstream",
        wavelength_nm: 1490,
        topology_revision: 10,
        assumptions: ["Circuito original."],
        missing_fields: [],
        steps: [
          {
            step_number: 1,
            element_type: "fusion",
            element_name: "Fusão CTO",
            parameter_source: "standard",
            unit: "dB",
            individual_value: 0.1,
            loss_db: 0.1,
            accumulated_loss_db: 0.1,
          },
        ],
        total_loss_db: 18.65,
        tx_dbm: 3.0,
        predicted_rx_dbm: -15.65,
        rx_min_dbm: -17.0,
        rx_max_dbm: -14.0,
        engineering_margin_db: 3.0,
        remaining_margin_db: 9.35,
        overload_headroom_db: 7.65,
        assessment: "pass",
      },
      simulated: {
        status: "complete",
        direction: "downstream",
        wavelength_nm: 1490,
        topology_revision: 10,
        assumptions: ["Simulação hipotética com 1 override aplicado."],
        missing_fields: [],
        steps: [
          {
            step_number: 1,
            element_type: "fusion",
            element_name: "Fusão CTO [Simulado: 3.50 dB]",
            parameter_source: "measured",
            unit: "dB",
            individual_value: 3.5,
            loss_db: 3.5,
            accumulated_loss_db: 3.5,
          },
        ],
        total_loss_db: 22.05,
        tx_dbm: 3.0,
        predicted_rx_dbm: -19.05,
        rx_min_dbm: -20.4,
        rx_max_dbm: -17.4,
        engineering_margin_db: 3.0,
        remaining_margin_db: 5.95,
        overload_headroom_db: 11.05,
        assessment: "pass",
      },
      delta_loss_db: 3.4,
      delta_predicted_rx_dbm: -3.4,
    };

    vi.mocked(simulationsApi.simulateOpticalBudget).mockResolvedValueOnce(mockSimResponse);

    render(<SimulationsView />);

    // 1. Banner permanente obrigatório
    expect(screen.getByText("Simulação — rede operacional não alterada")).toBeDefined();

    // 2. Preencher formulário de simulação
    const slInput = screen.getByLabelText(/Atendimento \(Service Link ID\)/i);
    fireEvent.change(slInput, { target: { value: "sl-test-123" } });

    const elemIdInput = screen.getByPlaceholderText(/UUID do elemento/i);
    fireEvent.change(elemIdInput, { target: { value: "fus-test-456" } });

    // 3. Submeter simulação
    const submitBtn = screen.getByText("Calcular Simulação");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Cenário Original (Baseline Operacional)")).toBeDefined();
      expect(screen.getByText("Cenário Simulado (Com Overrides)")).toBeDefined();
      // Valores Antes vs Depois
      expect(screen.getByText("-15,65 dBm")).toBeDefined();
      expect(screen.getByText("-19,05 dBm")).toBeDefined();
      expect(screen.getByText("(-3.40 dBm)")).toBeDefined();
      expect(screen.getByText("(+3.40 dB)")).toBeDefined();
    });

    // 4. Encerrar cenário restaura a vista limpa
    const endBtn = screen.getByText(/Encerrar Cenário/i);
    fireEvent.click(endBtn);

    await waitFor(() => {
      expect(screen.queryByText("Cenário Original (Baseline Operacional)")).toBeNull();
    });
  });

  it("não exibe botão de aplicar cenário para garantir que a rede operacional nunca sofra mutações", () => {
    render(<SimulationsView />);

    // Garantir que nenhum botão de "Aplicar cenário" ou "Salvar na rede" exista
    expect(screen.queryByText(/aplicar cenário/i)).toBeNull();
    expect(screen.queryByText(/salvar na rede/i)).toBeNull();
  });
});
