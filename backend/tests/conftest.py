import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Configurar ambiente de teste antes de importar a aplicação
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://ftth_user:ftth_password@127.0.0.1:5432/ftth_manager_test"
)

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
