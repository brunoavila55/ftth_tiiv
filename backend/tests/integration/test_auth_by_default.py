"""R03 (EST-02 / SEC-01): autenticação por padrão em TODAS as rotas.

Varredura comportamental: percorre os paths/métodos de `app.openapi()`, envia a requisição SEM
cookie/Authorization e exige 401 — exceto a allowlist explícita abaixo. Uma rota nova que nasça
sem autenticação faz este teste falhar.
"""

import re
import uuid

from fastapi import status
from fastapi.testclient import TestClient

from app.main import create_app

HTTP_METHODS = ("get", "post", "put", "patch", "delete")

# Rotas públicas por design (método, regex do path completo). Toda entrada tem justificativa.
PUBLIC_ROUTES: list[tuple[str, str]] = [
    # health checks (orquestrador/balanceador; sem dados de negócio)
    ("GET", r"/health/(live|ready)"),
    ("GET", r"/api/v1/health/(live|ready)"),
    # fluxo de login: precisa ser anônimo (CSRF inicial, credenciais, logout idempotente)
    ("GET", r"/api/v1/auth/csrf"),
    ("POST", r"/api/v1/auth/login"),
    ("POST", r"/api/v1/auth/logout"),
    # /metrics aceita X-Metrics-Token (Prometheus) ou sessão admin; anônimo sem token → 401 pelo
    # próprio verify_metrics_access (segredo endurecido na R05).
    ("GET", r"/api/v1/metrics"),
]


def _is_public(method: str, path: str) -> bool:
    return any(m == method and re.fullmatch(rx, path) for m, rx in PUBLIC_ROUTES)


def _all_operations() -> list[tuple[str, str]]:
    schema = create_app().openapi()
    return [
        (method.upper(), path)
        for path, item in sorted(schema["paths"].items())
        for method in HTTP_METHODS
        if method in item
    ]


OPERATIONS = _all_operations()


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


def test_inventory_is_not_empty() -> None:
    assert len(OPERATIONS) >= 100


def test_every_route_requires_authentication(client: TestClient) -> None:
    """Um único teste (uma limpeza de banco) percorre todas as operações e agrega as falhas."""
    offenders: list[str] = []
    for method, path in OPERATIONS:
        kwargs: dict[str, object] = {}
        if method in ("POST", "PUT", "PATCH"):
            kwargs["json"] = {}
        response = client.request(method, _concrete(path), **kwargs)  # type: ignore[arg-type]

        if _is_public(method, path):
            # /metrics é "público" só para quem apresenta X-Metrics-Token; anônimo puro → 401
            if path.endswith("/metrics") and response.status_code != status.HTTP_401_UNAUTHORIZED:
                offenders.append(f"{method} {path} -> {response.status_code} (esperado 401)")
            continue

        if response.status_code != status.HTTP_401_UNAUTHORIZED:
            offenders.append(f"{method} {path} -> {response.status_code} (esperado 401)")

    assert not offenders, "Rotas acessíveis sem autenticação:\n" + "\n".join(offenders)


def test_allowlist_entries_match_real_routes() -> None:
    """A allowlist não pode ficar com entradas mortas (rota removida/renomeada)."""
    for method, regex in PUBLIC_ROUTES:
        assert any(m == method and re.fullmatch(regex, p) for m, p in OPERATIONS), (method, regex)
