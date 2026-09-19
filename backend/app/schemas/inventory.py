from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import AdministrativeStatus, PhysicalCondition, UuidOrEmptyStr, UuidStr
from app.schemas.geojson import PointGeometry


class SiteKind(StrEnum):
    POP = "pop"
    CABINET = "cabinet"
    TECHNICAL_FACILITY = "technical_facility"


class StructureKind(StrEnum):
    POLE = "pole"
    CEO = "ceo"
    CTO = "cto"
    MANHOLE = "manhole"
    PEDESTAL = "pedestal"


class DeviceKind(StrEnum):
    OLT = "olt"
    DIO = "dio"
    ONU = "onu"
    SWITCH = "switch"


class PortRole(StrEnum):
    PON = "pon"
    UPLINK = "uplink"
    CLIENT_ACCESS = "client_access"
    PASS_THROUGH = "pass_through"
    INTERNAL = "internal"


# --- SITE ---
class SiteCreate(BaseModel):
    code: str = Field(
        ..., min_length=2, max_length=50, description="Código único do site (ex: POP-CENTRO)"
    )
    name: str = Field(
        ..., min_length=2, max_length=100, description="Nome legível do local técnico"
    )
    kind: SiteKind = Field(default=SiteKind.POP)
    location: PointGeometry = Field(..., description="Ponto geográfico do site")
    status: AdministrativeStatus = Field(default=AdministrativeStatus.INSTALLED)
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    kind: SiteKind | None = None
    location: PointGeometry | None = None
    status: AdministrativeStatus | None = None
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)


class SiteRead(BaseModel):
    id: str
    code: str
    name: str
    kind: SiteKind
    location: PointGeometry
    status: AdministrativeStatus
    address: str | None = None
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


# --- STRUCTURE ---
class StructureCreate(BaseModel):
    code: str = Field(
        ..., min_length=2, max_length=50, description="Código único da estrutura (ex: CTO-04)"
    )
    kind: StructureKind = Field(
        ..., description="Tipo de estrutura (pole, ceo, cto, manhole, pedestal)"
    )
    location: PointGeometry = Field(..., description="Ponto geográfico da estrutura")
    site_id: UuidStr | None = Field(
        default=None, description="UUID do site associado, se alocado internamente"
    )
    capacity: int = Field(default=0, ge=0, description="Capacidade física cadastrada", le=100000)
    status: AdministrativeStatus = Field(default=AdministrativeStatus.INSTALLED)
    condition: PhysicalCondition = Field(default=PhysicalCondition.OK)
    notes: str | None = Field(default=None, max_length=5000)


class StructureUpdate(BaseModel):
    location: PointGeometry | None = None
    site_id: UuidOrEmptyStr | None = None
    capacity: int | None = Field(default=None, ge=0, le=100000)
    status: AdministrativeStatus | None = None
    condition: PhysicalCondition | None = None
    notes: str | None = Field(default=None, max_length=5000)


class StructureRead(BaseModel):
    id: str
    code: str
    kind: StructureKind
    location: PointGeometry
    site_id: str | None = None
    capacity: int
    status: AdministrativeStatus
    condition: PhysicalCondition
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class StructureOccupancyResponse(BaseModel):
    structure_id: str
    code: str
    kind: StructureKind
    total_ports: int = Field(..., ge=0, description="Total de portas físicas de atendimento")
    connected_ports: int = Field(..., ge=0, description="Portas com conexões ativas")
    reserved_ports: int = Field(..., ge=0, description="Portas atualmente reservadas")
    free_ports: int = Field(..., ge=0, description="Portas livres para novas conexões")
    damaged_ports: int = Field(default=0, ge=0, description="Portas danificadas ou inoperantes")


# --- DEVICE ---
class DeviceCreate(BaseModel):
    code: str = Field(
        ..., min_length=2, max_length=50, description="Código único do dispositivo (ex: OLT-01)"
    )
    kind: DeviceKind = Field(..., description="Tipo do dispositivo (olt, dio, onu, switch)")
    manufacturer: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    site_id: UuidStr | None = Field(
        default=None, description="Alocação em site (exclusivo com structure_id)"
    )
    structure_id: UuidStr | None = Field(
        default=None, description="Alocação em structure (exclusivo com site_id)"
    )
    status: AdministrativeStatus = Field(default=AdministrativeStatus.INSTALLED)
    condition: PhysicalCondition = Field(default=PhysicalCondition.OK)
    notes: str | None = Field(default=None, max_length=5000)


class DeviceUpdate(BaseModel):
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    site_id: UuidOrEmptyStr | None = None
    structure_id: UuidOrEmptyStr | None = None
    status: AdministrativeStatus | None = None
    condition: PhysicalCondition | None = None
    notes: str | None = Field(default=None, max_length=5000)


class DeviceRead(BaseModel):
    id: str
    code: str
    kind: DeviceKind
    manufacturer: str
    model: str
    serial_number: str | None = None
    site_id: str | None = None
    structure_id: str | None = None
    status: AdministrativeStatus
    condition: PhysicalCondition
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


# --- PORT ---
class PortCreate(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=50, description="Identificador da porta (ex: PON-1, Porta 01)"
    )
    role: PortRole = Field(..., description="Função da porta")
    device_id: UuidStr | None = Field(
        default=None, description="Dispositivo proprietário (exclusivo com structure_id)"
    )
    structure_id: UuidStr | None = Field(
        default=None, description="Estrutura proprietária (exclusivo com device_id)"
    )
    has_internal_pass_through: bool = Field(
        default=False,
        description="Indica se a porta passiva possui travessia frente/trás (ex: DIO ou CTO)",
    )
    connector_type: str = Field(
        default="SC/APC", description="Padrão de conector óptico", max_length=50
    )
    notes: str | None = Field(default=None, max_length=5000)


class PortUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=50)
    role: PortRole | None = None
    connector_type: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


class PortRead(BaseModel):
    id: str
    name: str
    role: PortRole
    device_id: str | None = None
    structure_id: str | None = None
    has_internal_pass_through: bool
    connector_type: str
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime
