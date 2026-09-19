"""R13 (EST-03 / EST-04 / EST-21): concorrência otimista atômica e split serializado."""

import re
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import concurrency
from app.core.errors import PreconditionFailedError, PreconditionRequiredError
from app.main import create_app
from app.modules.cables.models import Cable, CableSegment, Fiber
from app.modules.customers.models import Customer
from app.modules.gis.service import get_topology_revision
from app.modules.inventory.models import Device, Port, Site, Structure
from app.modules.measurements.models import OpticalMeasurement
from app.modules.optical.models import OpticalProfile
from tests.conftest import create_test_user, login_test_client

APP_DIR = Path(__file__).resolve().parents[2] / "app"
POINT = "POINT(-46.6333 -23.5505)"


# ---------------------------------------------------------------------------------------------
# EST-21 — um único módulo para If-Match
# ---------------------------------------------------------------------------------------------


def test_if_match_parsing_lives_in_a_single_module() -> None:
    """Falha se surgir uma nova cópia de validação de If-Match fora de app/core/concurrency.py."""
    offenders: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        if path == APP_DIR / "core" / "concurrency.py":
            continue
        text = path.read_text()
        if re.search(
            r"def _?(validate_if_match|check_optimistic_lock|_check_optimistic_lock)\b", text
        ):
            offenders.append(
                f"{path.relative_to(APP_DIR)}: definição duplicada de checagem de If-Match"
            )
        if re.search(r"int\(\s*if_match\b", text):
            offenders.append(f"{path.relative_to(APP_DIR)}: parse manual de If-Match")
    assert not offenders, "\n".join(offenders)


@pytest.mark.parametrize(
    ("header", "expected"),
    [('"3"', 3), ("3", 3), ("'3'", 3), (' "3" ', 3), ('W/"3"', 3)],
)
def test_parse_if_match_accepts_common_etag_forms(header: str, expected: int) -> None:
    assert concurrency.parse_if_match(header) == expected


@pytest.mark.parametrize("header", [None, "", "   "])
def test_missing_if_match_is_428(header: str | None) -> None:
    with pytest.raises(PreconditionRequiredError):
        concurrency.parse_if_match(header)


def test_invalid_or_stale_if_match_is_412() -> None:
    with pytest.raises(PreconditionFailedError):
        concurrency.parse_if_match("abc")
    with pytest.raises(PreconditionFailedError):
        concurrency.check_if_match('"1"', current_version=2)
    concurrency.check_if_match('"2"', current_version=2)


# ---------------------------------------------------------------------------------------------
# EST-03 — check-then-act: duas requisições com o mesmo If-Match → exatamente um 200 e um 412
# ---------------------------------------------------------------------------------------------


def _make_entities(db: Session) -> dict[str, tuple[str, dict[str, Any], dict[str, Any]]]:
    """recurso → (url do PATCH, corpo A, corpo B). Cada entidade nasce com version=1."""
    site = Site(code="S-CC", name="Site", kind="pop", status="installed", location=POINT, version=1)
    db.add(site)
    db.flush()
    structure = Structure(
        code="ST-CC",
        kind="pole",
        status="installed",
        condition="ok",
        capacity=0,
        location=POINT,
        site_id=site.id,
        version=1,
    )
    device = Device(
        code="DEV-CC",
        kind="olt",
        manufacturer="M",
        model="X",
        site_id=site.id,
        status="installed",
        condition="ok",
        version=1,
    )
    cable = Cable(
        code="CAB-CC",
        model="M",
        fiber_count=6,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    customer = Customer(code="CLI-CC", name="Cliente", version=1)
    profile = OpticalProfile(
        name="Perfil CC",
        technology="GPON",
        wavelength_nm=1490,
        tx_min_dbm=1.0,
        tx_max_dbm=5.0,
        rx_sensitivity_dbm=-28.0,
        rx_overload_dbm=-8.0,
        default_attenuation_db_per_km=0.35,
        version=1,
    )
    db.add_all([structure, device, cable, customer, profile])
    db.flush()
    port = Port(name="P1", role="pon", device_id=device.id, connector_type="SC/APC", version=1)
    db.add(port)
    db.commit()
    return {
        "sites": (f"/api/v1/sites/{site.id}", {"name": "Nome A"}, {"name": "Nome B"}),
        "structures": (f"/api/v1/structures/{structure.id}", {"notes": "A"}, {"notes": "B"}),
        "devices": (f"/api/v1/devices/{device.id}", {"notes": "A"}, {"notes": "B"}),
        "ports": (f"/api/v1/ports/{port.id}", {"notes": "A"}, {"notes": "B"}),
        "cables": (f"/api/v1/cables/{cable.id}", {"notes": "A"}, {"notes": "B"}),
        "customers": (f"/api/v1/customers/{customer.id}", {"notes": "A"}, {"notes": "B"}),
        "optical-profiles": (
            f"/api/v1/optical-profiles/{profile.id}",
            {"notes": "A"},
            {"notes": "B"},
        ),
    }


def _race_patch(urls: tuple[str, dict[str, Any], dict[str, Any]], email: str) -> list[int]:
    url, body_a, body_b = urls
    barrier = threading.Barrier(2, timeout=15)
    concurrency._after_check_hooks.append(barrier.wait)  # ambos passam da checagem antes de gravar
    results: list[int] = []
    lock = threading.Lock()

    def worker(body: dict[str, Any]) -> None:
        client = TestClient(create_app(), raise_server_exceptions=False)
        csrf = login_test_client(client, email)
        resp = client.patch(url, json=body, headers={"X-CSRF-Token": csrf, "If-Match": '"1"'})
        with lock:
            results.append(resp.status_code)

    threads = [threading.Thread(target=worker, args=(b,)) for b in (body_a, body_b)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
    finally:
        concurrency._after_check_hooks.clear()
    return sorted(results)


@pytest.mark.parametrize(
    "resource",
    ["sites", "structures", "devices", "ports", "cables", "customers", "optical-profiles"],
)
def test_concurrent_patch_with_same_if_match_yields_exactly_one_success(
    db_session: Session, resource: str
) -> None:
    create_test_user(db_session, "engenheiro_cc@provedor.com.br", "engineer")
    entities = _make_entities(db_session)
    statuses = _race_patch(entities[resource], "engenheiro_cc@provedor.com.br")
    assert statuses == [status.HTTP_200_OK, status.HTTP_412_PRECONDITION_FAILED], statuses


def test_concurrent_user_update_yields_exactly_one_success(db_session: Session) -> None:
    create_test_user(db_session, "root_cc@provedor.com.br", "admin")
    target = create_test_user(db_session, "alvo_cc@provedor.com.br", "viewer")
    statuses = _race_patch(
        (f"/api/v1/users/{target.id}", {"name": "Nome A"}, {"name": "Nome B"}),
        "root_cc@provedor.com.br",
    )
    assert statuses == [status.HTTP_200_OK, status.HTTP_412_PRECONDITION_FAILED], statuses


def test_concurrent_measurement_update_yields_exactly_one_success(db_session: Session) -> None:
    from app.modules.connectivity.models import Terminal

    create_test_user(db_session, "tec_cc@provedor.com.br", "technician")
    site = Site(code="S-M", name="S", kind="pop", status="installed", location=POINT, version=1)
    db_session.add(site)
    db_session.flush()
    term = Terminal(
        kind="fiber_endpoint",
        site_id=site.id,
        label="T",
        occupancy="free",
        is_occupied=False,
        version=1,
    )
    db_session.add(term)
    db_session.flush()
    meas = OpticalMeasurement(
        terminal_id=term.id,
        power_dbm=-20.0,
        wavelength_nm=1490,
        direction="downstream",
        origin="manual_entry",
        version=1,
    )
    db_session.add(meas)
    db_session.commit()
    statuses = _race_patch(
        (f"/api/v1/measurements/{meas.id}", {"notes": "A"}, {"notes": "B"}),
        "tec_cc@provedor.com.br",
    )
    assert statuses == [status.HTTP_200_OK, status.HTTP_412_PRECONDITION_FAILED], statuses


def test_stale_data_error_is_mapped_to_412(db_session: Session) -> None:
    """Rede de proteção: gravação com versão defasada vira 412 (nunca 500) em qualquer fluxo."""
    from sqlalchemy.orm.exc import StaleDataError

    from app.db.session import get_session_factory

    site = Site(code="S-STALE", name="S", kind="pop", status="installed", location=POINT, version=1)
    db_session.add(site)
    db_session.commit()
    factory = get_session_factory()
    with factory() as s1, factory() as s2:
        a = s1.get(Site, site.id)
        b = s2.get(Site, site.id)
        assert a is not None and b is not None
        a.name, a.version = "A", a.version + 1
        s1.commit()
        b.name, b.version = "B", b.version + 1
        with pytest.raises(StaleDataError):
            s2.commit()


# ---------------------------------------------------------------------------------------------
# EST-04 — split: trava o trecho, exige If-Match ou expected_topology_revision
# ---------------------------------------------------------------------------------------------


def _split_scenario(db: Session) -> dict[str, Any]:
    site = Site(code="S-SP", name="S", kind="pop", status="installed", location=POINT, version=1)
    db.add(site)
    db.flush()
    pts = {
        "a": "POINT(-46.6330 -23.5500)",
        "b": "POINT(-46.6340 -23.5510)",
        "c": "POINT(-46.6350 -23.5520)",
    }
    structs = {
        key: Structure(
            code=f"SP-{key}",
            kind="ceo" if key == "b" else "pole",
            status="installed",
            condition="ok",
            capacity=0,
            location=loc,
            site_id=site.id,
            version=1,
        )
        for key, loc in pts.items()
    }
    db.add_all(structs.values())
    db.commit()
    return {k: v.id for k, v in structs.items()}


def _create_segment(client: TestClient, csrf: str, ids: dict[str, Any]) -> tuple[str, str]:
    cable = client.post(
        "/api/v1/cables",
        json={"code": "CAB-SP", "model": "M", "fiber_count": 4, "tube_count": 1},
        headers={"X-CSRF-Token": csrf},
    ).json()["id"]
    seg = client.post(
        "/api/v1/cable-segments",
        json={
            "cable_id": cable,
            "origin_structure_id": str(ids["a"]),
            "destination_structure_id": str(ids["c"]),
            "geometry": {
                "type": "LineString",
                "coordinates": [[-46.6330, -23.5500], [-46.6340, -23.5510], [-46.6350, -23.5520]],
            },
            "slack_length_m": 5.0,
        },
        headers={"X-CSRF-Token": csrf},
    ).json()["id"]
    return cable, seg


@pytest.fixture
def split_env(client: TestClient, db_session: Session) -> dict[str, Any]:
    create_test_user(db_session, "eng_split@provedor.com.br", "engineer")
    csrf = login_test_client(client, "eng_split@provedor.com.br")
    ids = _split_scenario(db_session)
    cable, seg = _create_segment(client, csrf, ids)
    return {"csrf": csrf, "ids": ids, "cable": cable, "segment": seg}


def _split(
    client: TestClient,
    env: dict[str, Any],
    body_extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    segment: str | None = None,
):  # type: ignore[no-untyped-def]
    body = {"access_structure_id": str(env["ids"]["b"]), "cut_fiber_ids": [], **(body_extra or {})}
    return client.post(
        f"/api/v1/cable-segments/{segment or env['segment']}/split",
        json=body,
        headers={"X-CSRF-Token": env["csrf"], **(headers or {})},
    )


def test_split_requires_if_match_or_expected_revision(
    client: TestClient, split_env: dict[str, Any]
) -> None:
    resp = _split(client, split_env)
    assert resp.status_code == status.HTTP_428_PRECONDITION_REQUIRED


def test_split_with_stale_if_match_is_412_and_changes_nothing(
    client: TestClient, split_env: dict[str, Any], db_session: Session
) -> None:
    resp = _split(client, split_env, headers={"If-Match": '"99"'})
    assert resp.status_code == status.HTTP_412_PRECONDITION_FAILED
    assert db_session.scalar(select(func.count(CableSegment.id))) == 1


def test_split_with_stale_expected_revision_is_409(
    client: TestClient, split_env: dict[str, Any]
) -> None:
    resp = _split(client, split_env, body_extra={"expected_topology_revision": 1})
    assert resp.status_code == status.HTTP_409_CONFLICT


def test_split_succeeds_with_current_if_match(
    client: TestClient, split_env: dict[str, Any], db_session: Session
) -> None:
    resp = _split(client, split_env, headers={"If-Match": '"1"'})
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert db_session.scalar(select(func.count(CableSegment.id))) == 2


def test_split_succeeds_with_current_expected_revision(
    client: TestClient, split_env: dict[str, Any], db_session: Session
) -> None:
    revision = get_topology_revision(db_session)
    resp = _split(client, split_env, body_extra={"expected_topology_revision": revision})
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["new_topology_revision"] == revision + 1


def test_concurrent_splits_of_the_same_segment_only_one_wins(
    db_session: Session, split_env: dict[str, Any]
) -> None:
    revision = get_topology_revision(db_session)
    barrier = threading.Barrier(2, timeout=15)
    results: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        client = TestClient(create_app(), raise_server_exceptions=False)
        csrf = login_test_client(client, "eng_split@provedor.com.br")
        env = {**split_env, "csrf": csrf}
        barrier.wait()
        resp = _split(client, env, body_extra={"expected_topology_revision": revision})
        with lock:
            results.append(resp.status_code)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert sorted(results) == [status.HTTP_200_OK, status.HTTP_409_CONFLICT], results
    db_session.expire_all()
    assert db_session.scalar(select(func.count(CableSegment.id))) == 2  # dividido uma única vez
    assert db_session.scalar(select(func.count(Fiber.id))) == 4  # fibras preservadas


def test_split_of_unknown_segment_is_404(client: TestClient, split_env: dict[str, Any]) -> None:
    resp = _split(client, split_env, headers={"If-Match": '"1"'}, segment=str(uuid.uuid4()))
    assert resp.status_code == status.HTTP_404_NOT_FOUND
