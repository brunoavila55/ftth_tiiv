"""R06 (EST-11): tetos de entrada retornam 422 (sem custo de criação) e rate limit retorna 429."""

import time
import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.rate_limit import reset_rate_limits
from tests.conftest import create_test_user, login_test_client

RID = str(uuid.uuid4())


@pytest.fixture
def engineer(client: TestClient, db_session: Session) -> str:
    create_test_user(db_session, "eng_limits@provedor.com.br", "engineer")
    return login_test_client(client, "eng_limits@provedor.com.br")


def _post(client: TestClient, csrf: str, url: str, body: dict[str, object]) -> int:
    return client.post(url, json=body, headers={"X-CSRF-Token": csrf}).status_code


def test_cable_fiber_and_tube_ceiling(client: TestClient, engineer: str) -> None:
    base = {"code": "CAB-LIMIT", "model": "M"}
    for body in (
        {**base, "fiber_count": 1_000_000},
        {**base, "fiber_count": 1729},
        {**base, "fiber_count": 12, "tube_count": 145},
        {**base, "fiber_count": 12, "notes": "x" * 5001},
        {**base, "fiber_count": 12, "color_standard": "x" * 51},
    ):
        assert _post(client, engineer, "/api/v1/cables", body) == 422, body


def test_cable_creation_with_reasonable_fiber_count_still_works(
    client: TestClient, engineer: str
) -> None:
    body = {"code": "CAB-OK-1", "model": "CFOA", "fiber_count": 144, "tube_count": 12}
    assert _post(client, engineer, "/api/v1/cables", body) == status.HTTP_201_CREATED


def test_list_ceilings(client: TestClient, engineer: str) -> None:
    big = [str(uuid.uuid4()) for _ in range(501)]
    assert (
        _post(
            client,
            engineer,
            "/api/v1/topology/impact",
            {
                "cable_segment_ids": big,
                "expected_topology_revision": 1,
            },
        )
        == 422
    )
    assert (
        _post(
            client,
            engineer,
            f"/api/v1/cable-segments/{RID}/split",
            {
                "access_structure_id": RID,
                "cut_fiber_ids": [str(uuid.uuid4()) for _ in range(1729)],
            },
        )
        == 422
    )
    assert (
        _post(
            client,
            engineer,
            "/api/v1/exports",
            {
                "format": "geojson",
                "layers": ["sites"] * 21,
            },
        )
        == 422
    )
    assert (
        _post(
            client,
            engineer,
            "/api/v1/connections/batch",
            {
                "structure_id": RID,
                "expected_topology_revision": 1,
                "operations": [{"action": "create"}] * 501,
            },
        )
        == 422
    )


def test_text_ceilings(client: TestClient, engineer: str) -> None:
    site = {"code": "S-1", "name": "Site", "location": {"type": "Point", "coordinates": [-46, -23]}}
    assert _post(client, engineer, "/api/v1/sites", {**site, "notes": "x" * 5001}) == 422
    assert _post(client, engineer, "/api/v1/sites", {**site, "address": "x" * 256}) == 422
    resp = client.patch(
        f"/api/v1/customers/{RID}",
        json={"phone": "1" * 31},
        headers={"X-CSRF-Token": engineer, "If-Match": "1"},
    )
    assert resp.status_code == 422
    assert client.get(f"/api/v1/search?q={'a' * 101}").status_code == 422


def test_customer_update_fields_are_aligned_with_columns(client: TestClient, engineer: str) -> None:
    for field, limit in (("phone", 30), ("email", 100), ("address", 255)):
        resp = client.patch(
            f"/api/v1/customers/{RID}",
            json={field: "x" * (limit + 1)},
            headers={"X-CSRF-Token": engineer, "If-Match": "1"},
        )
        assert resp.status_code == 422, field


def test_upload_limit_enforced_before_reading_whole_body(
    client: TestClient, engineer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_IMPORT_SIZE_BYTES", "1024")
    from app.core.config import get_settings

    get_settings.cache_clear()
    resp = client.post(
        "/api/v1/imports/preview",
        files={"file": ("a.geojson", b"{" + b" " * 5000 + b"}", "application/geo+json")},
        headers={"X-CSRF-Token": engineer},
    )
    assert resp.status_code == status.HTTP_413_CONTENT_TOO_LARGE


# ------------------------------------------------------------------------------------------
# Rate limit reutilizável (429 + Retry-After)
# ------------------------------------------------------------------------------------------


def test_rate_limit_returns_429_with_retry_after(
    client: TestClient, engineer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_SEARCH_PER_MINUTE", "3")
    from app.core.config import get_settings

    get_settings.cache_clear()
    reset_rate_limits()
    codes = [client.get("/api/v1/search?q=abc").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]
    blocked = client.get("/api/v1/search?q=abc")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.headers["content-type"].startswith("application/problem+json")


def test_rate_limit_is_per_user_and_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.rate_limit import InMemoryRateLimiter

    now = [1000.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    assert all(limiter.hit("k", "alice", limit=2, window_seconds=60)[0] for _ in range(2))
    allowed, retry_after = limiter.hit("k", "alice", limit=2, window_seconds=60)
    assert not allowed and 1 <= retry_after <= 60
    assert limiter.hit("k", "bob", limit=2, window_seconds=60)[0]  # outro sujeito
    now[0] += 61
    assert limiter.hit("k", "alice", limit=2, window_seconds=60)[0]  # janela expirou


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("POST", "/api/v1/topology/trace"),
        ("POST", "/api/v1/topology/impact"),
        ("POST", "/api/v1/optical/budgets"),
        ("POST", "/api/v1/optical/simulations"),
        ("GET", "/api/v1/search?q=abc"),
        ("POST", "/api/v1/attachments"),
        ("POST", "/api/v1/imports/preview"),
        ("POST", "/api/v1/exports"),
    ],
)
def test_expensive_routes_declare_a_rate_limit(method: str, url: str) -> None:
    from app.main import create_app
    from tests.route_utils import iter_api_routes

    path = url.split("?")[0]
    for route in iter_api_routes(create_app()):
        if route.path == path and method in route.methods:
            names = {getattr(d.call, "rate_limit_name", None) for d in _flatten(route.dependant)}
            assert names - {None}, f"{method} {path} sem rate_limit"
            return
    pytest.fail(f"rota {method} {path} não encontrada")


def _flatten(dependant):  # type: ignore[no-untyped-def]
    for sub in dependant.dependencies:
        yield sub
        yield from _flatten(sub)


def test_time_module_is_importable() -> None:
    assert time.monotonic() > 0
