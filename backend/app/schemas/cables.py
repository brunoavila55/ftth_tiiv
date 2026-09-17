from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import AdministrativeStatus, OccupancyStatus
from app.schemas.geojson import LineStringGeometry


class LengthSource(StrEnum):
    MEASURED = "measured"
    CALCULATED = "calculated"


class CableCreate(BaseModel):
    code: str = Field(
        ..., min_length=2, max_length=50, description="Código único do cabo (ex: CAB-TRONCAL-01)"
    )
    model: str = Field(
        ..., min_length=1, max_length=100, description="Modelo do cabo (ex: CFOA-SM-AS80-S-12F)"
    )
    fiber_count: int = Field(..., ge=1, description="Quantidade total de fibras ópticas no cabo")
    tube_count: int = Field(default=1, ge=1, description="Quantidade de tubos loose")
    color_standard: str = Field(
        default="NBR", description="Padrão de código de cores (NBR, TIA-598, etc.)"
    )
    status: AdministrativeStatus = Field(default=AdministrativeStatus.INSTALLED)
    notes: str | None = None


class CableUpdate(BaseModel):
    status: AdministrativeStatus | None = None
    notes: str | None = None


class CableRead(BaseModel):
    id: str
    code: str
    model: str
    fiber_count: int
    tube_count: int
    color_standard: str
    status: AdministrativeStatus
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class CableSegmentCreate(BaseModel):
    cable_id: str = Field(..., description="UUID do cabo ao qual o trecho pertence")
    origin_structure_id: str = Field(
        ..., description="UUID da estrutura inicial de acesso (poste, CEO, CTO)"
    )
    destination_structure_id: str = Field(..., description="UUID da estrutura final de acesso")
    geometry: LineStringGeometry = Field(..., description="Linha geográfica do trecho do cabo")
    measured_length_m: float | None = Field(
        default=None,
        ge=0.0,
        description="Comprimento medido no campo em metros (se informado, tem precedência sobre o cálculo geográfico)",
    )
    slack_length_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Reserva técnica de cabo em metros (somada apenas quando measured_length_m não for informado)",
    )


class CableSegmentUpdate(BaseModel):
    geometry: LineStringGeometry | None = None
    measured_length_m: float | None = Field(default=None, ge=0.0)
    slack_length_m: float | None = Field(default=None, ge=0.0)


class CableSegmentRead(BaseModel):
    id: str
    cable_id: str
    origin_structure_id: str
    destination_structure_id: str
    geometry: LineStringGeometry
    map_length_m: float = Field(
        ..., description="Comprimento geodésico calculado em metros via PostGIS"
    )
    measured_length_m: float | None = Field(
        default=None, description="Comprimento físico medido em metros quando informado"
    )
    slack_length_m: float = Field(..., description="Reserva técnica em metros")
    effective_length_m: float = Field(
        ..., description="Comprimento óptico efetivo adotado para cálculo de atenuação"
    )
    length_source: LengthSource = Field(
        ..., description="Origem do valor efetivo: 'measured' ou 'calculated'"
    )
    version: int
    created_at: datetime
    updated_at: datetime


class TubeRead(BaseModel):
    id: str
    cable_id: str
    number: int = Field(..., description="Número do tubo loose")
    color_name: str = Field(..., description="Cor do tubo loose")
    is_logical_group: bool = Field(
        default=False, description="Indica agrupamento lógico para cabo sem tubos físicos"
    )


class FiberRead(BaseModel):
    id: str
    cable_id: str
    global_number: int = Field(..., description="Número ordinal da fibra dentro do cabo (1 a N)")
    tube_number: int = Field(..., description="Número do tubo loose")
    tube_position: int = Field(..., description="Posição da fibra dentro do tubo")
    color_name: str = Field(..., description="Nome da cor segundo o padrão do cabo")


class FiberSegmentRead(BaseModel):
    id: str
    cable_segment_id: str
    fiber_id: str
    fiber_number: int
    terminal_a_id: str = Field(..., description="Terminal óptico da extremidade A")
    terminal_b_id: str = Field(..., description="Terminal óptico da extremidade B")
    occupancy: OccupancyStatus = Field(
        ..., description="Estado atual de ocupação: free, reserved, connected"
    )


class SegmentSplitRequest(BaseModel):
    access_structure_id: str = Field(
        ...,
        description="UUID da estrutura física onde o cabo é aberto/dividido (ex: CEO ou CTO)",
    )
    split_coordinates: tuple[float, float] | None = Field(
        default=None,
        description="Coordenadas geodésicas opcionais do ponto de divisão (se omitido, usa as da estrutura de acesso)",
    )
    cut_fiber_ids: list[str] = Field(
        default_factory=list,
        description="Lista de UUIDs das fibras cortadas nesta caixa. Fibras não listadas permanecem passantes (continuidade interna)",
    )
    segment_1_slack_m: float = Field(
        default=0.0, ge=0.0, description="Reserva técnica alocada para o primeiro trecho em metros"
    )
    segment_2_slack_m: float = Field(
        default=0.0, ge=0.0, description="Reserva técnica alocada para o segundo trecho em metros"
    )


class SegmentSplitPreviewResponse(BaseModel):
    original_segment_id: str
    access_structure_id: str
    total_fibers_count: int
    cut_fibers_count: int
    pass_through_fibers_count: int
    segment_1_map_length_m: float
    segment_2_map_length_m: float
    warnings: list[str] = Field(default_factory=list)


class SegmentSplitResponse(BaseModel):
    success: bool
    original_segment_id: str
    segment_1: CableSegmentRead
    segment_2: CableSegmentRead
    pass_through_continuities_count: int
    cut_terminals_count: int
    new_topology_revision: int
