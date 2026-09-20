from pydantic import BaseModel, Field, field_validator


class AppSettingsRead(BaseModel):
    app_name: str
    organization_name: str = "Operação FTTH"
    timezone: str = "America/Sao_Paulo"
    default_map_center: tuple[float, float] = Field(
        default=(-46.633308, -23.550520),
        description="Coordenadas [lon, lat] padrão para inicialização do mapa",
    )
    default_map_zoom: int = 14
    max_upload_size_bytes: int = 10_485_760
    trace_max_depth: int = 100
    excess_loss_tolerance_db: float = Field(
        default=2.0, description="Tolerância para alerta de perda óptica excedente em dB"
    )
    version: int = 1


class AppSettingsUpdate(BaseModel):
    organization_name: str | None = Field(default=None, max_length=150)
    timezone: str | None = Field(default=None, max_length=64)
    default_map_center: tuple[float, float] | None = None
    default_map_zoom: int | None = Field(default=None, ge=1, le=22)
    excess_loss_tolerance_db: float | None = Field(default=None, ge=0.1, le=10.0)

    @field_validator("default_map_center")
    @classmethod
    def validate_map_center(cls, value: tuple[float, float] | None) -> tuple[float, float] | None:
        if value is None:
            return None
        longitude, latitude = value
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("default_map_center deve conter [longitude, latitude] válidas")
        return value
