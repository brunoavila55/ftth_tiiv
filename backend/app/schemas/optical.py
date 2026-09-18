from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.topology import TraceDirection


class BudgetAssessment(StrEnum):
    PASS = "pass"
    LOW_MARGIN = "low_margin"
    BELOW_SENSITIVITY = "below_sensitivity"
    OVERLOAD = "overload"
    UNKNOWN = "unknown"


class OpticalProfileCreate(BaseModel):
    name: str = Field(
        ..., min_length=2, max_length=100, description="Nome do perfil óptico (ex: GPON Classe B+)"
    )
    technology: str = Field(default="GPON", description="Tecnologia PON (GPON, XGS-PON, etc.)")
    wavelength_nm: int = Field(
        ..., ge=800, le=2000, description="Comprimento de onda em nanômetros (ex: 1490)"
    )
    tx_min_dbm: float = Field(..., description="Potência mínima de transmissão (dBm)")
    tx_max_dbm: float = Field(..., description="Potência máxima de transmissão (dBm)")
    rx_sensitivity_dbm: float = Field(..., description="Sensibilidade de recepção RX (dBm)")
    rx_overload_dbm: float = Field(..., description="Ponto de saturação/sobrecarga RX (dBm)")
    default_attenuation_db_per_km: float = Field(
        default=0.35,
        ge=0.0,
        description="Atenuação nominal da fibra em dB/km para este comprimento de onda",
    )
    notes: str | None = None


class OpticalProfileUpdate(BaseModel):
    name: str | None = None
    tx_min_dbm: float | None = None
    tx_max_dbm: float | None = None
    rx_sensitivity_dbm: float | None = None
    rx_overload_dbm: float | None = None
    default_attenuation_db_per_km: float | None = None
    notes: str | None = None


class OpticalProfileRead(BaseModel):
    id: str
    name: str
    technology: str
    wavelength_nm: int
    tx_min_dbm: float
    tx_max_dbm: float
    rx_sensitivity_dbm: float
    rx_overload_dbm: float
    default_attenuation_db_per_km: float
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class BudgetCalculationRequest(BaseModel):
    service_link_id: str | None = Field(
        default=None, description="UUID do atendimento de cliente a orçar"
    )
    start_terminal_id: str | None = Field(
        default=None, description="UUID do terminal óptico alternativo para orçar"
    )
    direction: TraceDirection = Field(
        default=TraceDirection.DOWNSTREAM,
        description="Direção do orçamento óptico: downstream (OLT->ONU) ou upstream (ONU->OLT)",
    )
    profile_id: str | None = Field(
        default=None,
        description="UUID do perfil óptico (se não fornecido, adota o perfil padrão do dispositivo)",
    )
    engineering_margin_db: float = Field(
        default=3.0,
        ge=0.0,
        description="Margem de segurança de engenharia em dB (não diminui a potência nominal)",
    )


class BudgetLossStep(BaseModel):
    step_number: int
    element_type: str
    element_name: str
    parameter_source: str = Field(
        ..., description="Origem da perda: datasheet, medido, calculado, default"
    )
    unit: str
    individual_value: float
    loss_db: float
    accumulated_loss_db: float


class BudgetCalculationResponse(BaseModel):
    status: str = Field(
        ..., description="'complete' se calculado integralmente ou 'insufficient_data'"
    )
    direction: TraceDirection
    wavelength_nm: int | None = Field(
        default=None, description="Comprimento de onda utilizado no cálculo"
    )
    topology_revision: int
    assumptions: list[str] = Field(
        default_factory=list, description="Hipóteses e convenções adotadas"
    )
    missing_fields: list[str] = Field(
        default_factory=list, description="Campos ausentes que impediram cálculo total"
    )
    steps: list[BudgetLossStep] = Field(
        default_factory=list, description="Memória de cálculo detalhada passo a passo"
    )
    total_loss_db: float | None = Field(default=None, description="Perda óptica total somada em dB")
    tx_dbm: float | None = Field(
        default=None, description="Potência de transmissão nominal de referência em dBm"
    )
    predicted_rx_dbm: float | None = Field(
        default=None, description="Potência óptica prevista na recepção em dBm"
    )
    rx_min_dbm: float | None = Field(
        default=None, description="Pior potência RX considerando TX mínimo e perda máxima"
    )
    rx_max_dbm: float | None = Field(
        default=None, description="Maior potência RX considerando TX máximo e perda mínima"
    )
    engineering_margin_db: float = Field(..., description="Margem de engenharia estipulada em dB")
    remaining_margin_db: float | None = Field(
        default=None, description="Margem líquida disponível em dB"
    )
    overload_headroom_db: float | None = Field(
        default=None, description="Distância até o limite de sobrecarga em dB"
    )
    assessment: BudgetAssessment = Field(
        ..., description="Veredito: pass, low_margin, below_sensitivity, overload, unknown"
    )


class SimulationOverrideItem(BaseModel):
    element_id: str = Field(
        ..., description="UUID do elemento óptico cujos parâmetros serão substituídos"
    )
    override_type: str = Field(
        ..., description="Tipo de substituição: loss_db, length_m, splitter_ratio"
    )
    new_value: float = Field(
        ..., description="Novo valor a ser aplicado temporariamente no cálculo"
    )


class OpticalSimulationRequest(BaseModel):
    service_link_id: str
    direction: TraceDirection = TraceDirection.DOWNSTREAM
    engineering_margin_db: float = 3.0
    overrides: list[SimulationOverrideItem] = Field(
        ..., min_length=1, description="Lista de substituições pontuais a simular no caminho óptico"
    )


class OpticalSimulationResponse(BaseModel):
    baseline: BudgetCalculationResponse
    simulated: BudgetCalculationResponse
    delta_loss_db: float = Field(
        ..., description="Diferença de atenuação entre simulação e baseline (dB)"
    )
    delta_predicted_rx_dbm: float = Field(
        ..., description="Variação na potência recebida prevista (dBm)"
    )
