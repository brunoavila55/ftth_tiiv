"""R05 (SEC-05 / EST-17): acesso ao /metrics — token efetivo, comparação constante, kill-switch."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import get_settings

TOKEN = "c81e4a7f20d95b36e1a07c4f9d2b58e3a6f10c74"


@pytest.fixture
def metrics_token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("METRICS_SECRET_TOKEN", TOKEN)
    get_settings.cache_clear()
    return TOKEN


def test_configured_token_is_the_effective_token(client: TestClient, metrics_token: str) -> None:
    ok = client.get("/api/v1/metrics", headers={"X-Metrics-Token": metrics_token})
    assert ok.status_code == status.HTTP_200_OK
    # o default público deixa de valer quando o token é configurado
    default = client.get(
        "/api/v1/metrics", headers={"X-Metrics-Token": "dev-metrics-token-change-in-production"}
    )
    assert default.status_code == status.HTTP_401_UNAUTHORIZED


def test_wrong_token_of_same_length_is_rejected(client: TestClient, metrics_token: str) -> None:
    almost = metrics_token[:-1] + ("0" if metrics_token[-1] != "0" else "1")
    resp = client.get("/api/v1/metrics", headers={"X-Metrics-Token": almost})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_non_ascii_token_does_not_crash(client: TestClient, metrics_token: str) -> None:
    resp = client.get("/api/v1/metrics", headers={"X-Metrics-Token": "tökén-inválido".encode()})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_metrics_disabled_is_not_served(
    client: TestClient, metrics_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    get_settings.cache_clear()
    resp = client.get("/api/v1/metrics", headers={"X-Metrics-Token": metrics_token})
    assert resp.status_code == status.HTTP_404_NOT_FOUND
