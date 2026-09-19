from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import UuidStr


class ServiceLinkStatus(StrEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    SUSPENDED = "suspended"


class CustomerCreate(BaseModel):
    code: str = Field(
        ..., min_length=2, max_length=50, description="Código único do cliente (ex: CLI-10023)"
    )
    name: str = Field(
        ..., min_length=2, max_length=150, description="Nome do cliente ou razão social"
    )
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)


class CustomerRead(BaseModel):
    id: str
    code: str
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class ServiceLinkCreate(BaseModel):
    customer_id: UuidStr = Field(..., description="UUID do cliente atendido")
    onu_device_id: UuidStr = Field(..., description="UUID do equipamento ONU instalado no cliente")
    port_id: UuidStr = Field(..., description="UUID da porta da CTO que atende esta ativação")
    notes: str | None = Field(default=None, max_length=5000)


class ServiceLinkUpdate(BaseModel):
    status: ServiceLinkStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ServiceLinkRead(BaseModel):
    id: str
    customer_id: str
    onu_device_id: str
    port_id: str
    status: ServiceLinkStatus
    activated_at: datetime
    deactivated_at: datetime | None = None
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime
