import pytest

from app.core.config import Environment, Settings


def test_settings_default_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = Settings(
        SECRET_KEY="a" * 32,
    )
    assert settings.APP_NAME == "FTTH Manager"
    assert settings.ENVIRONMENT == Environment.DEVELOPMENT
    assert settings.is_production is False
    assert settings.is_test is False
    assert settings.API_V1_PREFIX == "/api/v1"


def test_settings_environment_modes() -> None:
    test_settings = Settings(
        ENVIRONMENT=Environment.TEST,
        SECRET_KEY="b" * 32,
    )
    assert test_settings.is_test is True
    assert test_settings.is_production is False

    prod_settings = Settings(
        ENVIRONMENT=Environment.PRODUCTION,
        SECRET_KEY="c" * 32,
    )
    assert prod_settings.is_production is True
    assert prod_settings.is_test is False
