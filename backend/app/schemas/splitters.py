from datetime import datetime

from pydantic import BaseModel, Field


class SplitterPortLoss(BaseModel):
    port_number: int = Field(..., ge=1, description="Número da porta de saída (1 a N)")
    loss_1310_db: float = Field(..., ge=0.0, description="Perda de inserção em 1310 nm (dB)")
    loss_1490_db: float = Field(..., ge=0.0, description="Perda de inserção em 1490 nm (dB)")
    loss_1550_db: float | None = Field(
        default=None, ge=0.0, description="Perda de inserção em 1550 nm (dB)"
    )


class SplitterCreate(BaseModel):
    code: str = Field(
        ..., min_length=2, max_length=50, description="Código único do splitter (ex: SPL-CTO04-1x8)"
    )
    structure_id: str | None = Field(
        default=None,
        description="Estrutura onde o splitter está instalado (exclusivo com device_id)",
    )
    device_id: str | None = Field(
        default=None,
        description="Dispositivo onde o splitter está alojado (exclusivo com structure_id)",
    )
    ratio: str = Field(
        default="1:8", description="Razão nominal de divisão (ex: 1:8, 1:16, 1:2 desbalanceado)"
    )
    output_ports_count: int = Field(
        ..., ge=2, le=64, description="Quantidade N de portas de saída (arquitetura estrita 1:N)"
    )
    ports: list[SplitterPortLoss] = Field(
        default_factory=list,
        description="Perdas reais medidas ou de datasheet cadastradas para cada saída em dB",
    )
    notes: str | None = None


class SplitterUpdate(BaseModel):
    notes: str | None = None
    ports: list[SplitterPortLoss] | None = None


class SplitterPortRead(BaseModel):
    port_number: int
    is_input: bool
    terminal_id: str = Field(
        ..., description="UUID do terminal óptico associado a esta porta do splitter"
    )
    loss_1310_db: float | None = None
    loss_1490_db: float | None = None
    loss_1550_db: float | None = None


class SplitterRead(BaseModel):
    id: str
    code: str
    structure_id: str | None = None
    device_id: str | None = None
    ratio: str
    output_ports_count: int
    input_terminal_id: str
    ports: list[SplitterPortRead]
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime
