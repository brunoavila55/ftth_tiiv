from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "FTTH Manager"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Segurança
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-replace-in-production-minimum-32-chars-long",
        min_length=32,
    )
    COOKIE_SECURE: bool = False
    CSRF_SECRET: str = "dev-insecure-csrf-secret-replace-in-production"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Banco de dados
    DATABASE_URL: str = "postgresql+psycopg://ftth_user:ftth_password@127.0.0.1:5432/ftth_manager"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Armazenamento
    STORAGE_PATH: str = "./storage"
    MAX_UPLOAD_SIZE_BYTES: int = 10_485_760  # 10 MB

    # GIS e Mapa
    MAP_MAX_FEATURES: int = 500
    ROUTE_ENDPOINT_TOLERANCE_M: float = 5.0

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def parse_environment(cls, v: str | Environment) -> Environment:
        if isinstance(v, str):
            return Environment(v.lower())
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == Environment.TEST


@lru_cache
def get_settings() -> Settings:
    return Settings()
