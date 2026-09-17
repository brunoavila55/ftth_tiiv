from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.topology import TraceDirection


class MeasurementOrigin(StrEnum):
    FIELD_POWER_METER = "field_power_meter"
    OTDR = "otdr"
    MANUAL_ENTRY = "manual_entry"


class MeasurementCreate(BaseModel):
    terminal_id: str = Field(
        ..., description="UUID do terminal óptico onde a medição foi realizada"
    )
    service_link_id: str | None = Field(
        default=None,
        description="UUID do atendimento associado, se a medição ocorreu na ponta de um cliente",
    )
    power_dbm: float = Field(..., description="Potência óptica medida em dBm (ex: -21.50 dBm)")
    wavelength_nm: int = Field(
        ..., ge=800, le=2000, description="Comprimento de onda calibrado no medidor (nm)"
    )
    direction: TraceDirection = Field(
        default=TraceDirection.DOWNSTREAM,
        description="Direção do sinal medido: downstream (chegando na ONU) ou upstream (chegando na OLT)",
    )
    instrument_model: str | None = Field(
        default=None, description="Fabricante e modelo do medidor óptico (Power Meter / OTDR)"
    )
    measured_at: datetime | None = Field(
        default=None, description="Data e hora da coleta em campo (UTC)"
    )
    notes: str | None = None


class MeasurementUpdate(BaseModel):
    notes: str | None = None


class MeasurementRead(BaseModel):
    id: str
    terminal_id: str
    service_link_id: str | None = None
    power_dbm: float
    wavelength_nm: int
    direction: TraceDirection
    instrument_model: str | None = None
    measured_at: datetime
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class MeasurementComparisonResponse(BaseModel):
    measurement_id: str
    measured_power_dbm: float = Field(
        ..., description="Potência real obtida pelo instrumento em dBm"
    )
    predicted_power_dbm: float = Field(
        ..., description="Potência teórica prevista pelo orçamento óptico em dBm"
    )
    excess_loss_db: float = Field(
        ...,
        description="Perda excedente (previsto - medido). Valor positivo indica atenuação além da documentada em dB",
    )
    wavelength_nm: int
    direction: TraceDirection
    tolerance_db: float = Field(default=2.0, description="Tolerância de desvio configurada em dB")
    is_within_tolerance: bool = Field(
        ...,
        description="Indica se a medição de campo está dentro da margem de aceitação da engenharia",
    )
