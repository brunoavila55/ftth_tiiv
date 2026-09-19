"""R25 (EST-12): identificadores malformados retornam 422 (antes: HTTP 500 em ~14 rotas)."""

import re
import uuid
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from tests.conftest import create_test_user, login_test_client
from tests.route_utils import iter_api_routes

BAD_IDS = ["not-a-uuid", "123", "0000", "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz", "' OR 1=1 --"]
ID_NAME = re.compile(r"(^id$|_ids?$)")


def _is_uuid_typed(spec: dict[str, Any]) -> bool:
    if spec.get("format") == "uuid":
        return True
    alternatives = spec.get("anyOf", []) + spec.get("oneOf", [])
    if alternatives:
        return all(_is_uuid_typed(a) or a.get("type") == "null" for a in alternatives)
    if spec.get("type") == "array":
        return _is_uuid_typed(spec.get("items", {}))
    return spec.get("type") not in ("string",)  # não-string (int, bool...) não é o problema


def test_every_id_parameter_and_body_field_is_declared_as_uuid() -> None:
    schema = create_app().openapi()
    problems: list[str] = []
    for path, item in schema["paths"].items():
        for method, op in item.items():
            if not isinstance(op, dict):
                continue
            for prm in op.get("parameters", []):
                if ID_NAME.search(prm["name"]) and not _is_uuid_typed(prm["schema"]):
                    problems.append(f"{method.upper()} {path} ({prm['in']}) {prm['name']}")
    comps = schema["components"]["schemas"]
    roots: set[str] = set()
    for item in schema["paths"].values():
        for op in item.values():
            if isinstance(op, dict):
                for content in (op.get("requestBody") or {}).get("content", {}).values():
                    ref = content["schema"].get("$ref")
                    if ref:
                        roots.add(ref.split("/")[-1])
    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        seen.add(name)

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if "$ref" in node:
                    visit(node["$ref"].split("/")[-1])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(comps[name])

    for root in roots:
        visit(root)
    for name in sorted(seen):
        for prop, spec in comps[name].get("properties", {}).items():
            if ID_NAME.search(prop) and not _is_uuid_typed(spec):
                problems.append(f"schema {name}.{prop}")
    assert not problems, "Identificadores sem format uuid:\n" + "\n".join(problems)


@pytest.fixture
def admin_client(client: TestClient, db_session: Session) -> TestClient:
    create_test_user(db_session, "uuid_admin@provedor.com.br", "admin")
    login_test_client(client, "uuid_admin@provedor.com.br")
    return client


def test_malformed_path_ids_never_return_500(admin_client: TestClient) -> None:
    """Varre TODAS as rotas com parâmetro de caminho `*_id` e envia identificadores malformados."""
    csrf = admin_client.cookies["ftth_csrf_token"]
    offenders: list[str] = []
    checked = 0
    for route in iter_api_routes(create_app()):
        id_params = [p.name for p in route.dependant.path_params if ID_NAME.search(p.name)]
        if not id_params:
            continue
        for method in sorted(route.methods):
            for bad in BAD_IDS[:2]:
                url = route.path
                for name in id_params:
                    url = url.replace("{" + name + "}", bad)
                other = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), url)
                kwargs: dict[str, Any] = {"headers": {"X-CSRF-Token": csrf, "If-Match": '"1"'}}
                if method in ("POST", "PATCH", "PUT"):
                    kwargs["json"] = {}
                resp = admin_client.request(method, other, **kwargs)
                checked += 1
                if resp.status_code >= 500 or resp.status_code == status.HTTP_404_NOT_FOUND:
                    offenders.append(f"{method} {route.path} [{bad}] -> {resp.status_code}")
    assert checked > 60
    assert not offenders, "Rotas que não rejeitam o ID malformado com 422:\n" + "\n".join(offenders)


@pytest.mark.parametrize("bad", BAD_IDS)
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/customers/{}",
        "/api/v1/service-links/{}",
        "/api/v1/connections/{}",
        "/api/v1/structures/{}/connectivity",
        "/api/v1/structures/{}/cto-occupancy",
        "/api/v1/structures/{}",
        "/api/v1/sites/{}",
        "/api/v1/devices/{}",
        "/api/v1/ports/{}",
        "/api/v1/cables/{}",
        "/api/v1/cable-segments/{}",
        "/api/v1/measurements/{}",
        "/api/v1/optical-profiles/{}",
        "/api/v1/users/{}",
        "/api/v1/attachments/{}",
        "/api/v1/imports/{}",
        "/api/v1/exports/{}",
        "/api/v1/jobs/{}",
    ],
)
def test_get_with_malformed_id_is_422(admin_client: TestClient, path: str, bad: str) -> None:
    resp = admin_client.get(path.format(bad))
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (path, bad, resp.status_code)
    assert resp.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    ("url", "body"),
    [
        ("/api/v1/topology/trace", {"start_terminal_id": "x"}),
        ("/api/v1/topology/impact", {"cable_segment_ids": ["x"], "expected_topology_revision": 1}),
        ("/api/v1/service-links", {"customer_id": "x", "onu_device_id": "y", "port_id": "z"}),
        (
            "/api/v1/connections",
            {"terminal_a_id": "x", "terminal_b_id": "y", "connection_type": "fusion_splice"},
        ),
        (
            "/api/v1/cable-segments",
            {
                "cable_id": "x",
                "origin_structure_id": "y",
                "destination_structure_id": "z",
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            },
        ),
        ("/api/v1/measurements", {"terminal_id": "x", "power_dbm": -20, "wavelength_nm": 1490}),
        ("/api/v1/ports", {"name": "P", "role": "pon", "device_id": "x"}),
        ("/api/v1/optical/budgets", {"start_terminal_id": "x", "profile_id": "y"}),
    ],
)
def test_malformed_ids_in_request_bodies_are_422(
    admin_client: TestClient, url: str, body: dict[str, Any]
) -> None:
    csrf = admin_client.cookies["ftth_csrf_token"]
    resp = admin_client.post(url, json=body, headers={"X-CSRF-Token": csrf})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, resp.text
    fields = {e["field"] for e in resp.json().get("errors", [])}
    assert any(f.endswith("_id") or f.endswith("_ids") or "_ids." in f for f in fields), fields


def test_malformed_ids_in_query_filters_are_422(admin_client: TestClient) -> None:
    for url in (
        "/api/v1/service-links?customer_id=abc",
        "/api/v1/service-links?port_id=abc",
        "/api/v1/ports?device_id=abc",
        "/api/v1/attachments?entity_id=abc",
        "/api/v1/audit-events?actor_id=abc",
        "/api/v1/measurements?terminal_id=abc",
    ):
        assert admin_client.get(url).status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, url


def test_valid_uuids_in_any_case_are_still_accepted(admin_client: TestClient) -> None:
    upper = str(uuid.uuid4()).upper()
    # bem formado mas inexistente: 404 de negócio (não 422)
    assert admin_client.get(f"/api/v1/customers/{upper}").status_code == status.HTTP_404_NOT_FOUND
    assert (
        admin_client.get(f"/api/v1/sites/{uuid.uuid4()}").status_code == status.HTTP_404_NOT_FOUND
    )
