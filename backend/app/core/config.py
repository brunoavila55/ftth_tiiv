import ipaddress
from enum import StrEnum
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_LENGTH = 32
# Fragmentos que denunciam valores de exemplo/padrão publicados no repositório ou em documentação
_INSECURE_MARKERS = (
    "dev-insecure",
    "change-me",
    "changeme",
    "replace-in-production",
    "change-in-production",
    "example",
    "ftth_password",
)


def _is_weak_secret(value: str) -> bool:
    candidate = value.strip()
    return (
        len(candidate) < MIN_SECRET_LENGTH
        or len(set(candidate)) < 8  # ex.: "aaaa…" ou "abababab…"
        or any(marker in candidate.lower() for marker in _INSECURE_MARKERS)
    )


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Erros de validação não devem ecoar segredos (input_value) em logs de inicialização
        hide_input_in_errors=True,
    )

    APP_NAME: str = "FTTH Manager"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    LOG_LEVEL: str = "INFO"

    # Segurança. Em produção, SECRET_KEY/CSRF_SECRET/METRICS_SECRET_TOKEN não podem ser os padrões
    # de desenvolvimento nem valores fracos (ver `reject_insecure_production_config`).
    # SECRET_KEY e CSRF_SECRET ainda não são consumidas: serão usadas na R09 (token CSRF assinado
    # e sessões); permanecem declaradas para que a validação de produção já as proteja.
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-replace-in-production-minimum-32-chars-long",
        min_length=32,
    )
    COOKIE_SECURE: bool = False
    CSRF_SECRET: str = "dev-insecure-csrf-secret-replace-in-production"

    # Proxies reversos confiáveis (IPs ou CIDRs, formato JSON list). Só de pares nesta lista o backend
    # aceita X-Forwarded-For/-Proto. Vazio = não confia em nenhum (usa o IP do socket). Em produção
    # atrás do Caddy, informe a rede do compose (ex.: ["172.16.0.0/12"]).
    TRUSTED_PROXIES: list[str] = []

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Banco de dados
    DATABASE_URL: str = "postgresql+psycopg://ftth_user:ftth_password@127.0.0.1:5432/ftth_manager"
    # O pool é POR PROCESSO: com WEB_CONCURRENCY=2 workers a API abre no máximo 2 × (5+5) = 20
    # conexões (o PostgreSQL padrão aceita 100, dividindo com worker de jobs, migrate e leitura).
    DB_POOL_SIZE: int = Field(default=5, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0)
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    # Timeouts no servidor: nenhuma query da API prende uma conexão por mais de 30 s; o worker de
    # jobs (importações grandes) usa um teto separado e maior.
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=30_000, ge=100)
    DB_WORKER_STATEMENT_TIMEOUT_MS: int = Field(default=600_000, ge=100)
    DB_CONNECT_TIMEOUT_SECONDS: int = Field(default=10, ge=1)
    # Readiness: conexão dedicada e curta (não usa o pool da aplicação)
    HEALTH_DB_TIMEOUT_SECONDS: int = Field(default=2, ge=1)

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Armazenamento
    STORAGE_PATH: str = "./storage"
    MAX_UPLOAD_SIZE_BYTES: int = 10_485_760  # 10 MB (anexos)
    # Jobs assíncronos: lease do worker (renovada por heartbeat a cada lease/3 enquanto o job roda)
    JOB_LEASE_SECONDS: float = Field(default=60.0, gt=0)
    EXPORT_TTL_DAYS: int = Field(default=7, ge=1)  # arquivos de exportação vencem após N dias
    # Reconciliador de anexos: arquivos mais novos que isso NÃO são removidos (upload em andamento)
    ATTACHMENT_ORPHAN_GRACE_MINUTES: int = Field(default=15, ge=1)
    MAX_IMAGE_PIXELS: int = 25_000_000  # 25 Mpx: acima disso a imagem é rejeitada sem decodificar
    MAX_IMPORT_SIZE_BYTES: int = 20_971_520  # 20 MB (arquivos de importação GeoJSON/KML/CSV)

    # Rate limit por usuário autenticado (janela de 1 minuto; limitador em memória por processo —
    # com N réplicas/workers o teto efetivo é N × valor; ver docs/runbooks)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_COMPUTE_PER_MINUTE: int = 30  # trace, impact, budgets, simulations
    RATE_LIMIT_SEARCH_PER_MINUTE: int = 60
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20  # anexos e prévias de importação
    RATE_LIMIT_EXPORT_PER_MINUTE: int = 10

    # GIS e Mapa
    MAP_MAX_FEATURES: int = 500
    ROUTE_ENDPOINT_TOLERANCE_M: float = 5.0

    # Backup: chave de assinatura do manifesto (HMAC; obrigatória em produção) e chave opcional de
    # criptografia do pacote (AES-256-GCM; 32 bytes em hex/base64). Guarde-as FORA do servidor de backup.
    BACKUP_SIGNING_KEY: str = ""
    BACKUP_ENCRYPTION_KEY: str = ""

    # Desempenho e Observabilidade (B16)
    METRICS_ENABLED: bool = True  # False → /metrics responde 404
    # Diretório compartilhado (API × workers × worker de jobs) para agregar métricas entre processos;
    # vazio = modo processo único (métricas só em memória).
    METRICS_DIR: str = ""
    METRICS_SNAPSHOT_TTL_SECONDS: int = Field(default=60, ge=10)
    METRICS_PUBLISH_INTERVAL_SECONDS: float = Field(default=10.0, gt=0)
    METRICS_SECRET_TOKEN: str = "dev-metrics-token-change-in-production"
    # Teto de saltos do rastreio óptico: ainda não aplicado; será usado na R14
    MAX_TRACE_HOPS: int = 300

    # Worker de jobs assíncronos: heartbeat consultado pelo HEALTHCHECK do compose
    WORKER_HEARTBEAT_FILE: str = "/tmp/ftth-worker.heartbeat"
    WORKER_HEARTBEAT_MAX_AGE_SECONDS: int = 300

    @field_validator("TRUSTED_PROXIES")
    @classmethod
    def validate_trusted_proxies(cls, value: list[str]) -> list[str]:
        for entry in value:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError as err:
                raise ValueError(f"TRUSTED_PROXIES contém entrada inválida: {entry!r}") from err
        return value

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def parse_environment(cls, v: str | Environment) -> Environment:
        if isinstance(v, str):
            return Environment(v.lower())
        return v

    @model_validator(mode="after")
    def reject_insecure_production_config(self) -> "Settings":
        """Produção recusa segredos padrão/fracos e a senha de banco de exemplo (SEC-05)."""
        if self.ENVIRONMENT != Environment.PRODUCTION:
            return self

        problems: list[str] = []
        for name in ("SECRET_KEY", "CSRF_SECRET", "METRICS_SECRET_TOKEN", "BACKUP_SIGNING_KEY"):
            if _is_weak_secret(getattr(self, name)):
                problems.append(
                    f"{name} é um valor padrão/fraco (use `openssl rand -hex 32`, "
                    f"mínimo {MIN_SECRET_LENGTH} caracteres)"
                )
        if self.BACKUP_ENCRYPTION_KEY:
            from app.core.backup_crypto import BackupCryptoError, parse_key

            try:
                parse_key(self.BACKUP_ENCRYPTION_KEY)
            except BackupCryptoError as err:
                problems.append(str(err))
        db_password = urlsplit(self.DATABASE_URL).password
        if not db_password or any(m in db_password.lower() for m in _INSECURE_MARKERS):
            problems.append("DATABASE_URL usa senha ausente ou de exemplo")
        if problems:
            raise ValueError(
                "Configuração insegura para ENVIRONMENT=production: " + "; ".join(problems)
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == Environment.TEST


@lru_cache
def get_settings() -> Settings:
    return Settings()
