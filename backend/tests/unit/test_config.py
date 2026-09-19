from pathlib import Path

import pydantic
import pytest
import yaml

from app.core.config import Environment, Settings

# Segredos fortes (aleatórios) e banco sem a senha de exemplo — aceitos em produção
STRONG_SECRETS = {
    "CSRF_SECRET": "3b7d19e5a04c86f2d1e7a9053c4b8e62f1d70a95c3e846b2",
    "METRICS_SECRET_TOKEN": "c81e4a7f20d95b36e1a07c4f9d2b58e3a6f10c74",
    "BACKUP_SIGNING_KEY": "7d3f0a19c6e48b25d1f97a3c5e08b642a1d97f3c0e5b8a24",
    "DATABASE_URL": "postgresql+psycopg://ftth_user:Zk3vQ9tLw2xB7nRp@db:5432/ftth_manager",
}


def test_settings_default_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = Settings()
    assert settings.APP_NAME == "FTTH Manager"
    assert settings.ENVIRONMENT == Environment.DEVELOPMENT
    assert settings.is_production is False
    assert settings.is_test is False
    assert settings.API_V1_PREFIX == "/api/v1"


def test_settings_environment_modes() -> None:
    test_settings = Settings(ENVIRONMENT=Environment.TEST)
    assert test_settings.is_test is True
    assert test_settings.is_production is False

    prod_settings = Settings(ENVIRONMENT=Environment.PRODUCTION, **STRONG_SECRETS)
    assert prod_settings.is_production is True
    assert prod_settings.is_test is False


# --- R05: produção recusa segredos padrão/fracos -------------------------------------------------


def test_production_accepts_strong_secrets() -> None:
    assert Settings(ENVIRONMENT=Environment.PRODUCTION, **STRONG_SECRETS).is_production


def test_production_rejects_all_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CSRF_SECRET",
        "METRICS_SECRET_TOKEN",
        "BACKUP_SIGNING_KEY",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(ENVIRONMENT=Environment.PRODUCTION)
    message = str(exc.value)
    for name in (
        "CSRF_SECRET",
        "METRICS_SECRET_TOKEN",
        "BACKUP_SIGNING_KEY",
        "DATABASE_URL",
    ):
        assert name in message


@pytest.mark.parametrize("field", ["CSRF_SECRET", "METRICS_SECRET_TOKEN", "BACKUP_SIGNING_KEY"])
@pytest.mark.parametrize(
    "weak",
    [
        "",
        "curto",
        "a" * 32,
        "dev-insecure-secret-key-replace-in-production-minimum-32-chars-long",
        "dev-insecure-csrf-secret-replace-in-production",
        "dev-metrics-token-change-in-production",
        "change-me-generate-with-openssl-rand-hex-32",
    ],
)
def test_production_rejects_weak_secret(field: str, weak: str) -> None:
    kwargs = {**STRONG_SECRETS, field: weak}
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(ENVIRONMENT=Environment.PRODUCTION, **kwargs)
    assert field in str(exc.value)


def test_production_rejects_default_database_password() -> None:
    kwargs = {
        **STRONG_SECRETS,
        "DATABASE_URL": "postgresql+psycopg://ftth_user:ftth_password@db:5432/ftth_manager",
    }
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(ENVIRONMENT=Environment.PRODUCTION, **kwargs)
    assert "DATABASE_URL" in str(exc.value)


@pytest.mark.parametrize("env", [Environment.DEVELOPMENT, Environment.TEST])
def test_defaults_still_allowed_outside_production(env: Environment) -> None:
    assert env == Settings(ENVIRONMENT=env).ENVIRONMENT


def test_compose_only_injects_variables_that_settings_reads() -> None:
    """Regressão do achado SEC-05: o compose injetava METRICS_TOKEN, mas a config lê outro nome."""
    compose = yaml.safe_load((Path(__file__).resolve().parents[3] / "compose.yaml").read_text())
    known = set(Settings.model_fields)
    # Variáveis do compose consumidas por outros processos (não pelo Settings do backend)
    not_settings = {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"}
    for service in ("migrate", "backend", "worker"):
        for name in compose["services"][service].get("environment", {}):
            assert name in known | not_settings, f"{service}: {name} não é lido por Settings"


def test_compose_secrets_have_no_public_defaults() -> None:
    text = (Path(__file__).resolve().parents[3] / "compose.yaml").read_text()
    for var in ("CSRF_SECRET", "METRICS_SECRET_TOKEN", "POSTGRES_PASSWORD"):
        assert f"${{{var}:-" not in text, f"{var} não pode ter default no compose"
        assert f"${{{var}:?" in text, f"{var} deve ser obrigatório no compose"
    assert "dev-insecure" not in text and "ftth_password" not in text


def test_production_rejects_invalid_backup_encryption_key() -> None:
    kwargs = {**STRONG_SECRETS, "BACKUP_ENCRYPTION_KEY": "curta"}
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(ENVIRONMENT=Environment.PRODUCTION, **kwargs)
    assert "BACKUP_ENCRYPTION_KEY" in str(exc.value)
    ok = {**STRONG_SECRETS, "BACKUP_ENCRYPTION_KEY": "ab" * 32}
    assert Settings(ENVIRONMENT=Environment.PRODUCTION, **ok).is_production


def test_s3_backend_requires_endpoint_and_credentials() -> None:
    """EST-14: STORAGE_BACKEND=s3 sem config não sobe (independe do ENVIRONMENT)."""
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(STORAGE_BACKEND="s3")
    message = str(exc.value)
    assert "S3_ENDPOINT_URL" in message
    assert "S3_ACCESS_KEY" in message
    assert "S3_SECRET_KEY" in message

    ok = Settings(
        STORAGE_BACKEND="s3",
        S3_ENDPOINT_URL="http://minio:9000",
        S3_ACCESS_KEY="minio",
        S3_SECRET_KEY="minio-secret",
    )
    assert ok.STORAGE_BACKEND == "s3"


def test_local_backend_ignores_missing_s3_config() -> None:
    assert Settings(STORAGE_BACKEND="local").STORAGE_BACKEND == "local"
