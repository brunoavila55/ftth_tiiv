"""R22 (PERF-05 / PERF-08): importação em lote sem bloquear o loop e exportação em fluxo."""

import csv
import io
import json
import threading
import time
import tracemalloc
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import resolve_storage_path
from app.modules.exports import service as exports_service
from app.modules.imports import service as imports_service
from app.modules.imports.models import AsyncJob
from app.modules.inventory.models import Site, Structure
from app.modules.jobs import service as jobs_service
from app.modules.jobs.service import execute_import_commit, process_next_job
from tests import legacy_exports_service as legacy_exports
from tests.conftest import create_test_user, login_test_client
from tests.integration.test_dashboard_performance import StatementCounter

BATCH = 500


@pytest.fixture
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    return tmp_path


def point_features(n: int, prefix: str = "PT") -> list[dict[str, Any]]:
    return [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-46.0 - i * 1e-5, -23.0 - i * 1e-5]},
            "properties": {
                "code": f"{prefix}-{i:06d}",
                "name": f"Ponto {i}",
                "entity_type": "structure",
                "type": "pole",
            },
        }
        for i in range(n)
    ]


def geojson_bytes(features: list[dict[str, Any]]) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


def import_job_for(
    db: Session, storage: Path, features: list[dict[str, Any]], user_id: Any = None
) -> AsyncJob:
    rel = f"imports/{uuid.uuid4().hex}.geojson"
    (storage / "imports").mkdir(parents=True, exist_ok=True)
    (storage / rel).write_bytes(geojson_bytes(features))
    job = AsyncJob(
        type="import_commit",
        status="running",
        lease_owner="w",
        idempotency_key=f"k-{uuid.uuid4()}",
        payload={"file_storage_path": rel, "format": "geojson"},
        user_id=user_id,
    )
    db.add(job)
    db.commit()
    return job


# ---------------------------------------------------------------------------------------------
# PERF-05 — preview não bloqueia o event loop
# ---------------------------------------------------------------------------------------------


def test_import_preview_does_not_block_health_probe(
    client: TestClient, db_session: Session, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_test_user(db_session, "imp_scale@provedor.com.br", "admin")
    csrf = login_test_client(client, "imp_scale@provedor.com.br")
    real_parse = imports_service.parse_geojson

    def slow_parse(content: bytes):  # type: ignore[no-untyped-def]
        time.sleep(1.5)
        return real_parse(content)

    monkeypatch.setattr(imports_service, "parse_geojson", slow_parse)
    result: dict[str, int] = {}
    body = geojson_bytes(point_features(5))
    worker = threading.Thread(
        target=lambda: result.update(
            status=client.post(
                "/api/v1/imports/preview",
                files={"file": ("rede.geojson", io.BytesIO(body), "application/geo+json")},
                headers={"X-CSRF-Token": csrf},
            ).status_code
        )
    )
    worker.start()
    time.sleep(0.2)
    latencies = []
    for _ in range(3):
        t0 = time.perf_counter()
        assert client.get("/health/live").status_code == status.HTTP_200_OK
        latencies.append(time.perf_counter() - t0)
    worker.join()
    assert result["status"] == status.HTTP_200_OK
    # Bloqueado, a sonda esperaria ~1,3 s; o teto folgado absorve runners lentos sem perder o sinal
    assert max(latencies) < 0.5, latencies


def test_preview_rejects_files_with_too_many_features(
    client: TestClient, db_session: Session, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_IMPORT_FEATURES", "10")
    get_settings.cache_clear()
    create_test_user(db_session, "imp_cap@provedor.com.br", "admin")
    csrf = login_test_client(client, "imp_cap@provedor.com.br")
    resp = client.post(
        "/api/v1/imports/preview",
        files={
            "file": (
                "grande.geojson",
                io.BytesIO(geojson_bytes(point_features(11))),
                "application/geo+json",
            )
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "10" in resp.json()["detail"]


# ---------------------------------------------------------------------------------------------
# PERF-05 — commit em lotes: ≤ 2 statements por lote de 500, all-or-nothing preservado
# ---------------------------------------------------------------------------------------------


def test_import_of_50k_points_uses_at_most_two_statements_per_batch(
    db_session: Session, storage: Path
) -> None:
    n = 50_000
    job = import_job_for(db_session, storage, point_features(n))
    with StatementCounter() as counter:
        result = execute_import_commit(db_session, job)
    db_session.commit()

    batches = -(-n // BATCH)
    print(f"\n[R22] import de {n} pontos: {counter.count} statements ({batches} lotes)")
    assert result["created_structures"] == n
    assert counter.count <= 2 * batches + 15, (
        f"{counter.count} statements para {batches} lotes (teto {2 * batches + 15})"
    )
    assert db_session.scalar(select(func.count(Structure.id))) == n
    sample = db_session.scalar(select(Structure).where(Structure.code == "PT-000123"))
    assert sample is not None and sample.kind == "pole" and sample.status == "installed"


def test_import_is_all_or_nothing_when_a_later_batch_fails(
    db_session: Session, storage: Path
) -> None:
    features = point_features(1200)
    features[1100]["properties"]["code"] = "PT-000001"  # duplicado no arquivo → invalida tudo
    job = import_job_for(db_session, storage, features)
    with pytest.raises(Exception, match="duplicad"):
        execute_import_commit(db_session, job)
    db_session.rollback()
    assert db_session.scalar(select(func.count(Structure.id))) == 0


def test_cancellation_is_checked_between_batches(db_session: Session, storage: Path) -> None:
    job = import_job_for(db_session, storage, point_features(BATCH * 3))
    other = Session(bind=db_session.get_bind())
    other.execute(text("UPDATE async_jobs SET status = 'cancelled' WHERE id = :i"), {"i": job.id})
    other.commit()
    other.close()
    with pytest.raises(InterruptedError):
        execute_import_commit(db_session, job)
    db_session.rollback()
    assert db_session.scalar(select(func.count(Structure.id))) == 0


def test_sites_and_structures_link_by_site_code(db_session: Session, storage: Path) -> None:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-46.1, -23.1]},
            "properties": {"code": "POP-X", "name": "POP X", "type": "pop", "entity_type": "site"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-46.2, -23.2]},
            "properties": {
                "code": "POSTE-X",
                "name": "P",
                "type": "pole",
                "entity_type": "structure",
                "site_code": "POP-X",
            },
        },
    ]
    job = import_job_for(db_session, storage, features)
    execute_import_commit(db_session, job)
    db_session.commit()
    site = db_session.scalar(select(Site).where(Site.code == "POP-X"))
    struct = db_session.scalar(select(Structure).where(Structure.code == "POSTE-X"))
    assert site is not None and struct is not None and struct.site_id == site.id


# ---------------------------------------------------------------------------------------------
# PERF-08 — exportação em fluxo: mesmo conteúdo, memória limitada
# ---------------------------------------------------------------------------------------------


def seed_export_dataset(db: Session, sites: int, structures: int) -> None:
    from sqlalchemy import insert

    db.execute(
        insert(Site),
        [
            {
                "id": uuid.uuid4(),
                "code": f"S-{i:05d}",
                "name": f"Site {i}",
                "kind": "pop",
                "status": "installed",
                "location": f"SRID=4326;POINT({-46 - i * 1e-4} {-23 - i * 1e-4})",
                "version": 1,
            }
            for i in range(sites)
        ],
    )
    kinds = ("pole", "cto", "ceo", "manhole")
    db.execute(
        insert(Structure),
        [
            {
                "id": uuid.uuid4(),
                "code": f"E-{i:06d}",
                "kind": kinds[i % 4],
                "status": "installed",
                "condition": "ok",
                "capacity": 0,
                "location": f"SRID=4326;POINT({-47 - i * 1e-5} {-22 - i * 1e-5})",
                "version": 1,
            }
            for i in range(structures)
        ],
    )
    db.commit()


def export_job(db: Session, fmt: str, layers: list[str]) -> AsyncJob:
    job = AsyncJob(
        type=f"export_{fmt}",
        status="running",
        lease_owner="w",
        idempotency_key=f"e-{uuid.uuid4()}",
        payload={"format": fmt, "layers": layers},
    )
    db.add(job)
    db.commit()
    return job


@pytest.mark.parametrize(
    "layers", [["sites"], ["sites", "structures"], ["ctos"], ["poles", "ceos"]]
)
def test_streaming_geojson_matches_legacy(
    db_session: Session, storage: Path, layers: list[str]
) -> None:
    seed_export_dataset(db_session, sites=6, structures=40)
    job = export_job(db_session, "geojson", layers)
    path = resolve_storage_path(exports_service.execute_export_job(db_session, job))
    new = json.loads(path.read_text())
    old = legacy_exports.generate_geojson_export(db_session, layers)
    key = lambda f: f["id"]  # noqa: E731
    assert new["type"] == old["type"]
    assert sorted(new["features"], key=key) == sorted(old["features"], key=key)


def test_streaming_csv_and_kml_match_legacy(db_session: Session, storage: Path) -> None:
    seed_export_dataset(db_session, sites=5, structures=30)
    layers = ["sites", "structures"]

    csv_path = resolve_storage_path(
        exports_service.execute_export_job(db_session, export_job(db_session, "csv", layers))
    )
    new_rows = sorted(csv.reader(io.StringIO(csv_path.read_text())))
    old_rows = sorted(
        csv.reader(io.StringIO(legacy_exports.generate_csv_export(db_session, layers)))
    )
    assert new_rows == old_rows

    kml_path = resolve_storage_path(
        exports_service.execute_export_job(db_session, export_job(db_session, "kml", layers))
    )
    ns = {"k": "http://www.opengis.net/kml/2.2"}

    def placemarks(root: ET.Element) -> list[tuple[str, str]]:
        return sorted(
            (
                pm.findtext("k:name", namespaces=ns) or "",
                pm.findtext(".//k:coordinates", namespaces=ns) or "",
            )
            for pm in root.iterfind(".//k:Placemark", ns)
        )

    assert placemarks(ET.fromstring(kml_path.read_bytes())) == placemarks(
        ET.fromstring(legacy_exports.generate_kml_export(db_session, layers).encode())
    )


@pytest.mark.parametrize("fmt", ["geojson", "csv", "kml"])
def test_export_memory_stays_within_twice_the_output_size(
    db_session: Session, storage: Path, fmt: str
) -> None:
    seed_export_dataset(db_session, sites=500, structures=40_000)
    job = export_job(db_session, fmt, ["sites", "structures"])
    db_session.expire_all()
    tracemalloc.start()
    stored = exports_service.execute_export_job(db_session, job)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    size = resolve_storage_path(stored).stat().st_size
    print(f"\n[R22] export {fmt}: pico {peak / 1e6:.1f} MB para arquivo de {size / 1e6:.1f} MB")
    assert size > 1_000_000
    assert peak <= 2 * size, (
        f"{fmt}: pico de {peak / 1e6:.1f} MB para arquivo de {size / 1e6:.1f} MB"
    )


def test_export_streaming_output_is_valid_for_every_format(
    db_session: Session, storage: Path
) -> None:
    seed_export_dataset(db_session, sites=3, structures=10)
    for fmt in ("geojson", "csv", "kml"):
        stored = exports_service.execute_export_job(
            db_session, export_job(db_session, fmt, ["sites", "structures"])
        )
        content = resolve_storage_path(stored).read_bytes()
        if fmt == "geojson":
            assert len(json.loads(content)["features"]) == 13
        elif fmt == "csv":
            assert len(list(csv.reader(io.StringIO(content.decode())))) == 14  # cabeçalho + 13
        else:
            assert (
                len(ET.fromstring(content).findall(".//{http://www.opengis.net/kml/2.2}Placemark"))
                == 13
            )


def test_worker_still_runs_export_jobs_end_to_end(
    client: TestClient, db_session: Session, storage: Path
) -> None:
    create_test_user(db_session, "exp_scale@provedor.com.br", "admin")
    csrf = login_test_client(client, "exp_scale@provedor.com.br")
    seed_export_dataset(db_session, sites=2, structures=5)
    job_id = client.post(
        "/api/v1/exports",
        json={"format": "geojson", "layers": ["sites", "structures"]},
        headers={"X-CSRF-Token": csrf},
    ).json()["job_id"]
    assert process_next_job(db_session, "w") is True
    dl = client.get(f"/api/v1/exports/{job_id}/download")
    assert dl.status_code == status.HTTP_200_OK and len(dl.json()["features"]) == 7
    assert jobs_service is not None
