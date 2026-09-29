from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import AdministrativeStatus, UuidStr


class RadioLinkCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    site_a_id: UuidStr
    site_b_id: UuidStr
    radio_a_id: UuidStr
    radio_b_id: UuidStr
    frequency_mhz: float = Field(..., gt=0, le=100000)
    channel_width_mhz: float = Field(..., gt=0, le=10000)
    status: AdministrativeStatus = AdministrativeStatus.PLANNED
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def distinct_endpoints(self) -> "RadioLinkCreate":
        if self.site_a_id == self.site_b_id or self.radio_a_id == self.radio_b_id:
            raise ValueError("Origem e destino do enlace devem ser diferentes.")
        return self


class RadioLinkUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    frequency_mhz: float | None = Field(default=None, gt=0, le=100000)
    channel_width_mhz: float | None = Field(default=None, gt=0, le=10000)
    status: AdministrativeStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)


class RadioLinkRead(BaseModel):
    id: str
    code: str
    name: str
    site_a_id: str
    site_b_id: str
    radio_a_id: str
    radio_b_id: str
    frequency_mhz: float
    channel_width_mhz: float
    status: AdministrativeStatus
    notes: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime
