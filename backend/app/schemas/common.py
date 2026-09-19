from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

_UUID_REGEX = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

UUID_PATTERN = f"^{_UUID_REGEX}$"

# Identificador UUID em texto: o FastAPI/Pydantic recusa valores malformados com 422 (antes o
# `uuid.UUID(valor)` dos serviços estourava 500). Continua `str`, então os serviços não mudam; o
# OpenAPI declara `format: uuid` (o cliente tipado segue `string`).
UuidStr = Annotated[
    str,
    Field(
        pattern=UUID_PATTERN,
        min_length=36,
        max_length=36,
        json_schema_extra={"format": "uuid"},
    ),
]

# Campo de atualização em que "" significa "remover o vínculo" (ex.: desassociar o site)
UuidOrEmptyStr = Annotated[
    str,
    Field(pattern=f"^({_UUID_REGEX})?$", max_length=36, json_schema_extra={"format": "uuid"}),
]


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
