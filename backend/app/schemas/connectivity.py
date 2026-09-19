from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import UuidStr


class TerminalKind(StrEnum):
    FIBER_ENDPOINT = "fiber_endpoint"
    PORT_FRONT = "port_front"
    PORT_BACK = "port_back"
    SPLITTER_INPUT = "splitter_input"
    SPLITTER_OUTPUT = "splitter_output"


class ConnectionType(StrEnum):
    FUSION_SPLICE = "fusion_splice"
    PATCH_CORD = "patch_cord"
    INTERNAL_CONTINUITY = "internal_continuity"


class BatchOperationType(StrEnum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RESERVE = "reserve"
    RELEASE = "release"


class TerminalRead(BaseModel):
    id: str
    kind: TerminalKind
    entity_id: str = Field(
        ..., description="UUID do objeto proprietário (fibra, porta ou splitter)"
    )
    entity_type: str = Field(..., description="Nome da entidade proprietária")
    label: str = Field(..., description="Rótulo identificador do terminal")
    is_occupied: bool = Field(
        ..., description="Indica se o terminal já possui uma conexão externa ativa"
    )


class ConnectionCreate(BaseModel):
    terminal_a_id: UuidStr = Field(..., description="UUID do primeiro terminal distinto")
    terminal_b_id: UuidStr = Field(..., description="UUID do segundo terminal distinto")
    connection_type: ConnectionType = Field(..., description="Tipo físico da conexão")
    loss_db: float = Field(
        default=0.1,
        ge=0.0,
        description="Perda de inserção documentada da conexão em dB (ex: fusão 0.10 dB, acoplador 0.30 dB)",
    )
    structure_id: UuidStr | None = Field(
        default=None,
        description="Estrutura (CEO, CTO, POP) onde a conexão física está localizada",
    )
    notes: str | None = Field(default=None, max_length=5000)


class ConnectionRead(BaseModel):
    id: str
    terminal_a_id: str
    terminal_b_id: str
    connection_type: ConnectionType
    loss_db: float
    structure_id: str | None = None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class BatchOperationItem(BaseModel):
    action: BatchOperationType = Field(
        ..., description="Ação atômica: connect, disconnect, reserve, release"
    )
    terminal_a_id: UuidStr = Field(..., description="UUID do terminal primário da operação")
    terminal_b_id: UuidStr | None = Field(
        default=None,
        description="UUID do terminal secundário (obrigatório quando action=connect)",
    )
    connection_type: ConnectionType | None = Field(
        default=None, description="Tipo de conexão para action=connect"
    )
    loss_db: float | None = Field(
        default=None, ge=0.0, description="Perda em dB para action=connect"
    )
    reservation_reason: str | None = Field(
        default=None, description="Motivo ou cliente para reserva/bloqueio", max_length=500
    )


class ConnectionBatchRequest(BaseModel):
    expected_topology_revision: int = Field(
        ...,
        description="Revisão topológica esperada no cliente; falha com 409 se a revisão atual divergir",
        le=2147483647,
    )
    structure_id: UuidStr = Field(
        ...,
        description="UUID do local/estrutura onde o lote de fusões/conexões está sendo executado",
    )
    operations: list[BatchOperationItem] = Field(
        ...,
        min_length=1,
        description="Lista ordenada de operações atômicas a serem aplicadas em lote",
        max_length=500,
    )


class ConnectionBatchResponse(BaseModel):
    success: bool
    applied_operations_count: int
    new_topology_revision: int = Field(
        ..., description="Nova revisão topológica monotônica incrementada após a transação"
    )


class TerminalReservationRead(BaseModel):
    id: str
    terminal_id: str
    reason: str
    reserved_by_id: str | None = None
    expires_at: datetime | None = None
    is_active: bool
    version: int
    created_at: datetime


class InternalEdgeRead(BaseModel):
    id: str
    terminal_a_id: str
    terminal_b_id: str
    edge_type: str
    entity_type: str
    entity_id: str
    loss_db: float
    is_bidirectional: bool


class StructureConnectivityResponse(BaseModel):
    structure_id: str
    topology_revision: int
    terminals: list[TerminalRead]
    connections: list[ConnectionRead]
    reservations: list[TerminalReservationRead]
    internal_edges: list[InternalEdgeRead]
