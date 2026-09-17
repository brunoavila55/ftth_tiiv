from enum import StrEnum

from pydantic import BaseModel, Field


class AdministrativeStatus(StrEnum):
    PLANNED = "planned"
    INSTALLED = "installed"
    RETIRED = "retired"


class PhysicalCondition(StrEnum):
    OK = "ok"
    DAMAGED = "damaged"
    UNKNOWN = "unknown"


class OccupancyStatus(StrEnum):
    FREE = "free"
    RESERVED = "reserved"
    CONNECTED = "connected"


class UserRole(StrEnum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    TECHNICIAN = "technician"
    VIEWER = "viewer"


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Número da página (1-indexado)")
    page_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Quantidade de itens por página (padrão 50, máximo 200)",
    )


class PaginatedResponse[T](BaseModel):
    items: list[T] = Field(..., description="Lista de itens da página atual")
    total: int = Field(..., ge=0, description="Total global de registros correspondentes")
    page: int = Field(..., ge=1, description="Página retornada")
    page_size: int = Field(..., ge=1, le=200, description="Tamanho de página aplicado")
