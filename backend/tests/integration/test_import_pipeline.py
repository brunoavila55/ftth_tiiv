"""R12 (EST-05/06/07/08): pipeline de importação — geometria de cabos, idempotência, lease, storage."""

import concurrent.futures
import io
import json
import threading
import time
import uuid
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.cables.models import Cable, CableSegment, Fiber
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob, ImportPreview
from app.modules.imports.service import commit_import_job
from app.modules.inventory.models import Structure
from app.modules.jobs import service as jobs_service
from app.modules.jobs.service import claim_next_job, process_next_job
from app.schemas.imports_exports import ImportCommitRequest
from tests.conftest import create_test_user, login_test_client

PT_A = [-46.6330, -23.5500]
PT_B = [-46.6340, -23.5510]


@pytest.fixture
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    return tmp_path


@pytest.fixture
def admin(client: TestClient, db_session: Session, storage: Path) -> tuple[User, str]:
    user = create_test_user(db_session, "admin_import_r12@provedor.com.br", "admin")
    return user, login_test_client(client, user.email)


def structure_feature(code: str, coords: list[float], kind: str = "pole") -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coords},
        "properties": {"code": code, "name": code, "entity_type": "structure", "type": kind},
    }


def cable_feature(code: str, coords: list[list[float]], **props: object) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "code": code,
            "name": "Cabo importado",
            "entity_type": "cable",
            "fiber_count": 6,
            "tube_count": 1,
            **props,
        },
    }


def preview(
    client: TestClient, csrf: str, features: list[dict], name: str = "rede.geojson"
) -> dict:
    body = json.dumps({"type": "FeatureCollection", "features": features}).encode()
    resp = client.post(
        "/api/v1/imports/preview",
        files={"file": (name, io.BytesIO(body), "application/geo+json")},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return resp.json()


def commit(client: TestClient, csrf: str, prev: dict, key: str | None = None):  # type: ignore[no-untyped-def]
    return client.post(
        f"/api/v1/imports/{prev['import_id']}/commit",
        json={"import_id": prev["import_id"], "file_hash": prev["file_hash"]},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key or f"idem-{uuid.uuid4()}"},
    )


def run_worker(db: Session) -> None:
    assert process_next_job(db, worker_id="test-worker") is True


# ---------------------------------------------------------------------------------------------
# EST-05 — cabos importados mantêm geometria (CableSegment) e sem coordenadas fictícias
# ---------------------------------------------------------------------------------------------


def test_cable_import_creates_segment_with_geometry_by_explicit_codes(
    client: TestClient, db_session: Session, admin: tuple[User, str]
) -> None:
    _, csrf = admin
    prev = preview(
        client,
        csrf,
        [
            structure_feature("POSTE-IMP-A", PT_A),
            structure_feature("POSTE-IMP-B", PT_B),
            cable_feature(
                "CAB-IMP-1",
                [PT_A, [-46.6335, -23.5505], PT_B],
                origin_code="POSTE-IMP-A",
                destination_code="POSTE-IMP-B",
            ),
        ],
    )
    assert prev["error_records"] == 0, prev
    assert commit(client, csrf, prev).status_code == status.HTTP_202_ACCEPTED
    run_worker(db_session)

    cable = db_session.scalar(select(Cable).where(Cable.code == "CAB-IMP-1"))
    assert cable is not None
    segments = db_session.scalars(
        select(CableSegment).where(CableSegment.cable_id == cable.id)
    ).all()
    assert len(segments) >= 1  # a geometria do arquivo NÃO é descartada
    seg = segments[0]
    origin = db_session.scalar(select(Structure).where(Structure.code == "POSTE-IMP-A"))
    dest = db_session.scalar(select(Structure).where(Structure.code == "POSTE-IMP-B"))
    assert origin is not None and dest is not None
    assert seg.origin_structure_id == origin.id and seg.destination_structure_id == dest.id
    assert seg.map_length_m > 0
    assert db_session.scalar(select(func.count(Fiber.id)).where(Fiber.cable_id == cable.id)) == 6


def test_cable_import_resolves_endpoints_by_proximity(
    client: TestClient, db_session: Session, admin: tuple[User, str]
) -> None:
    _, csrf = admin
    prev = preview(
        client,
        csrf,
        [
            structure_feature("POSTE-PX-A", PT_A),
            structure_feature("POSTE-PX-B", PT_B),
            cable_feature("CAB-PX-1", [PT_A, PT_B]),  # sem origin_code/destination_code
        ],
    )
    assert prev["error_records"] == 0, prev
    assert commit(client, csrf, prev).status_code == status.HTTP_202_ACCEPTED
    run_worker(db_session)
    seg = db_session.scalar(
        select(CableSegment)
        .join(Cable, Cable.id == CableSegment.cable_id)
        .where(Cable.code == "CAB-PX-1")
    )
    assert seg is not None
    codes = {
        db_session.get(Structure, seg.origin_structure_id).code,  # type: ignore[union-attr]
        db_session.get(Structure, seg.destination_structure_id).code,  # type: ignore[union-attr]
    }
    assert codes == {"POSTE-PX-A", "POSTE-PX-B"}


def test_cable_endpoints_can_match_structures_already_in_the_database(
    client: TestClient, db_session: Session, admin: tuple[User, str]
) -> None:
    _, csrf = admin
    first = preview(
        client, csrf, [structure_feature("POSTE-DB-A", PT_A), structure_feature("POSTE-DB-B", PT_B)]
    )
    assert commit(client, csrf, first).status_code == status.HTTP_202_ACCEPTED
    run_worker(db_session)

    second = preview(client, csrf, [cable_feature("CAB-DB-1", [PT_A, PT_B])], "cabos.geojson")
    assert second["error_records"] == 0, second
    assert commit(client, csrf, second).status_code == status.HTTP_202_ACCEPTED
    run_worker(db_session)
    assert db_session.scalar(select(func.count(CableSegment.id))) == 1


def test_cable_without_resolvable_structures_is_a_preview_error_and_blocks_commit(
    client: TestClient, db_session: Session, admin: tuple[User, str]
) -> None:
    _, csrf = admin
    prev = preview(
        client,
        csrf,
        [
            structure_feature("POSTE-LONGE", [-40.0, -10.0]),
            cable_feature("CAB-SOLTO", [PT_A, PT_B]),  # pontas longe de qualquer estrutura
        ],
    )
    assert prev["error_records"] == 1
    item = next(i for i in prev["sample_preview"] if i["entity_code"] == "CAB-SOLTO")
    assert item["validation_status"] == "error"
    assert "estrutura" in item["message"].lower()
    assert commit(client, csrf, prev).status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert db_session.scalar(select(func.count(Cable.id))) == 0


def test_csv_cable_without_coordinates_is_an_error_not_a_fictitious_route(
    client: TestClient, db_session: Session, admin: tuple[User, str]
) -> None:
    _, csrf = admin
    csv_body = b"code,entity_type,fiber_count\nCAB-CSV-1,cable,12\n"
    resp = client.post(
        "/api/v1/imports/preview",
        files={"file": ("cabos.csv", io.BytesIO(csv_body), "text/csv")},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["error_records"] == 1 and data["valid_records"] == 0
    assert "coordenadas" in data["sample_preview"][0]["message"].lower()


# ---------------------------------------------------------------------------------------------
# EST-06 — idempotência atômica do commit
# ---------------------------------------------------------------------------------------------


def _new_preview_row(db: Session, user: User, tag: str) -> ImportPreview:
    from datetime import UTC, datetime, timedelta

    row = ImportPreview(
        file_hash=f"{abs(hash(tag)):064x}"[:64],
        format="geojson",
        total_records=1,
        valid_records=1,
        error_records=0,
        collision_records=0,
        sample_items=[],
        file_storage_path=f"imports/{tag}.geojson",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_concurrent_commits_with_same_key_return_the_same_job(db_session: Session) -> None:
    user = create_test_user(db_session, "idem@provedor.com.br", "admin")
    row = _new_preview_row(db_session, user, "concorrente")
    payload = ImportCommitRequest(import_id=str(row.id), file_hash=row.file_hash)
    factory = get_session_factory()
    barrier = threading.Barrier(6)

    def attempt() -> str:
        with factory() as db:
            barrier.wait()
            u = db.get(User, user.id)
            return commit_import_job(db, str(row.id), payload, "chave-concorrente", user=u).job_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = [f.result() for f in [pool.submit(attempt) for _ in range(6)]]

    assert len(set(results)) == 1, results
    assert db_session.scalar(select(func.count(AsyncJob.id))) == 1


def test_same_key_with_another_import_is_a_conflict(db_session: Session) -> None:
    from fastapi import HTTPException

    user = create_test_user(db_session, "idem2@provedor.com.br", "admin")
    first = _new_preview_row(db_session, user, "um")
    second = _new_preview_row(db_session, user, "dois")
    commit_import_job(
        db_session,
        str(first.id),
        ImportCommitRequest(import_id=str(first.id), file_hash=first.file_hash),
        "k-1",
        user,
    )
    with pytest.raises(HTTPException) as exc:
        commit_import_job(
            db_session,
            str(second.id),
            ImportCommitRequest(import_id=str(second.id), file_hash=second.file_hash),
            "k-1",
            user,
        )
    assert exc.value.status_code == status.HTTP_409_CONFLICT


def test_same_preview_cannot_be_committed_twice_with_different_keys(db_session: Session) -> None:
    from fastapi import HTTPException

    user = create_test_user(db_session, "idem3@provedor.com.br", "admin")
    row = _new_preview_row(db_session, user, "unico")
    payload = ImportCommitRequest(import_id=str(row.id), file_hash=row.file_hash)
    commit_import_job(db_session, str(row.id), payload, "k-a", user)
    with pytest.raises(HTTPException) as exc:
        commit_import_job(db_session, str(row.id), payload, "k-b", user)
    assert exc.value.status_code == status.HTTP_409_CONFLICT


def test_idempotency_key_is_scoped_by_user_and_size_limited(
    client: TestClient, db_session: Session, admin: tuple[User, str]
) -> None:
    _, csrf = admin
    prev = preview(client, csrf, [structure_feature("POSTE-K-1", PT_A)])
    long_key = "x" * 200
    resp = client.post(
        f"/api/v1/imports/{prev['import_id']}/commit",
        json={"import_id": prev["import_id"], "file_hash": prev["file_hash"]},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": long_key},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # duas contas com a MESMA chave textual não colidem entre si
    other = create_test_user(db_session, "outra@provedor.com.br", "admin")
    row = _new_preview_row(db_session, other, "outra-conta")
    p = ImportCommitRequest(import_id=str(row.id), file_hash=row.file_hash)
    job_other = commit_import_job(db_session, str(row.id), p, "mesma-chave", other).job_id
    user2 = create_test_user(db_session, "terceira@provedor.com.br", "admin")
    row2 = _new_preview_row(db_session, user2, "terceira-conta")
    p2 = ImportCommitRequest(import_id=str(row2.id), file_hash=row2.file_hash)
    job_third = commit_import_job(db_session, str(row2.id), p2, "mesma-chave", user2).job_id
    assert job_other != job_third


# ---------------------------------------------------------------------------------------------
# EST-07 — lease renovada (heartbeat) e checagem de dono antes de gravar
# ---------------------------------------------------------------------------------------------


def _export_job(db: Session) -> AsyncJob:
    job = AsyncJob(
        type="export_geojson",
        status="queued",
        idempotency_key=f"lease-{uuid.uuid4()}",
        payload={"format": "geojson", "layers": ["sites"]},
    )
    db.add(job)
    db.commit()
    return job


def test_long_job_keeps_its_lease_and_runs_once_with_two_workers(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Versão comprimida do cenário de 120 s: lease de 1,2 s, job de ~4 s, 2º worker tentando."""
    monkeypatch.setenv("JOB_LEASE_SECONDS", "1.2")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    job = _export_job(db_session)
    runs: list[str] = []

    def slow_export(db: Session, j: AsyncJob) -> str:
        runs.append(str(j.id))
        time.sleep(4.0)
        target = tmp_path / "exports" / f"{j.id}.geojson"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
        return str(target)

    monkeypatch.setattr(jobs_service, "execute_export_job", slow_export)

    claims: list[AsyncJob | None] = []
    lease_samples: list[bool] = []
    stop = threading.Event()

    def rival_worker() -> None:
        factory = get_session_factory()
        while not stop.is_set():
            with factory() as db2:
                claims.append(claim_next_job(db2, "worker-B", lease_seconds=1))
                row = db2.get(AsyncJob, job.id)
                if row is not None and row.status == "running" and row.lease_expires_at:
                    from datetime import UTC, datetime

                    lease_samples.append(row.lease_expires_at > datetime.now(UTC))
            time.sleep(0.15)

    rival = threading.Thread(target=rival_worker)
    rival.start()
    try:
        with get_session_factory()() as db1:
            claimed = claim_next_job(
                db1, "worker-A", lease_seconds=get_settings().JOB_LEASE_SECONDS
            )
            assert claimed is not None
            assert jobs_service.process_claimed_job(db1, claimed, worker_id="worker-A") is True
    finally:
        stop.set()
        rival.join()

    assert runs == [str(job.id)], "o job deveria executar uma única vez"
    assert all(c is None for c in claims), (
        "o 2º worker nunca pode reivindicar um job com lease renovada"
    )
    assert lease_samples and all(lease_samples), (
        "a lease deve permanecer no futuro durante a execução"
    )
    db_session.expire_all()
    done = db_session.get(AsyncJob, job.id)
    assert done is not None and done.status == "succeeded" and done.retry_count == 0


def test_result_is_not_written_when_the_lease_was_lost(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    job = _export_job(db_session)

    def steal_lease(db: Session, j: AsyncJob) -> str:
        with get_session_factory()() as other:  # outro worker assume o job durante a execução
            row = other.get(AsyncJob, j.id)
            assert row is not None
            row.lease_owner = "worker-B"
            other.commit()
        target = tmp_path / "exports" / f"{j.id}.geojson"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
        return str(target)

    monkeypatch.setattr(jobs_service, "execute_export_job", steal_lease)
    with get_session_factory()() as db1:
        claimed = claim_next_job(db1, "worker-A")
        assert claimed is not None
        assert jobs_service.process_claimed_job(db1, claimed, worker_id="worker-A") is False

    db_session.expire_all()
    row = db_session.get(AsyncJob, job.id)
    assert row is not None
    assert row.status == "running" and row.lease_owner == "worker-B"  # nada foi sobrescrito
    assert row.result_path is None


# ---------------------------------------------------------------------------------------------
# EST-08 — STORAGE_PATH e caminhos relativos ao storage root
# ---------------------------------------------------------------------------------------------


def test_import_and_export_use_storage_path_with_relative_paths(
    client: TestClient, db_session: Session, admin: tuple[User, str], storage: Path
) -> None:
    _, csrf = admin
    prev = preview(client, csrf, [structure_feature("POSTE-ST-1", PT_A)])
    row = db_session.get(ImportPreview, uuid.UUID(prev["import_id"]))
    assert row is not None
    assert not Path(row.file_storage_path).is_absolute()
    assert row.file_storage_path.startswith("imports/")
    assert (storage / row.file_storage_path).is_file()

    assert commit(client, csrf, prev).status_code == status.HTTP_202_ACCEPTED
    run_worker(db_session)
    assert db_session.scalar(select(func.count(Structure.id))) == 1

    resp = client.post(
        "/api/v1/exports",
        json={"format": "geojson", "layers": ["structures"]},
        headers={"X-CSRF-Token": csrf},
    )
    job_id = resp.json()["job_id"]
    run_worker(db_session)
    job = db_session.get(AsyncJob, uuid.UUID(job_id))
    assert job is not None and job.result_path and not Path(job.result_path).is_absolute()
    assert job.result_path.startswith("exports/")
    assert (storage / job.result_path).is_file()
    dl = client.get(f"/api/v1/exports/{job_id}/download")
    assert dl.status_code == status.HTTP_200_OK
    assert dl.json()["features"]


def test_legacy_cwd_relative_paths_still_resolve(
    storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.storage import resolve_storage_path

    legacy_dir = Path("storage") / "imports"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy = legacy_dir / "legado-r12.csv"
    legacy.write_text("x")
    try:
        assert resolve_storage_path("storage/imports/legado-r12.csv") == legacy
        assert resolve_storage_path("imports/novo.csv") == storage / "imports" / "novo.csv"
    finally:
        legacy.unlink()
