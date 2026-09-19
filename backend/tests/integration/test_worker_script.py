"""Testes do script do worker (R02 / issue 13 — EST-01, EST-18).

O diretório `scripts/` não é um pacote: o script é carregado via importlib, exatamente como o
`python scripts/run_worker.py` do compose o executa.
"""

import importlib.util
import io
import json
import logging
import os
import time
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.logging import JSONFormatter
from app.core.metrics import metrics_collector
from app.core.storage_backend import get_storage_backend
from app.db.session import get_session_factory
from app.modules.imports.models import AsyncJob
from app.schemas.common import UserRole
from tests.integration.test_imports_exports_jobs import auth_client_login, create_user

BACKEND_DIR = Path(__file__).resolve().parents[2]
WORKER_SCRIPT = BACKEND_DIR / "scripts" / "run_worker.py"
COMPOSE_FILE = BACKEND_DIR.parent / "compose.yaml"


def load_worker_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_worker_under_test", WORKER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_export(client: TestClient, db_session: Session) -> tuple[str, str]:
    admin = create_user(db_session, "admin_worker@provedor.com.br", UserRole.ADMIN.value)
    csrf_token = auth_client_login(client, admin.email)
    resp = client.post(
        "/api/v1/exports",
        json={"format": "geojson", "layers": ["sites"]},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    return resp.json()["job_id"], csrf_token


def test_worker_script_is_importable() -> None:
    module = load_worker_module()
    assert callable(module.main)
    assert callable(module.run_iteration)


def test_worker_loop_iteration_processes_export_end_to_end(
    client: TestClient, db_session: Session, tmp_path: Path
) -> None:
    job_id, _ = request_export(client, db_session)
    module = load_worker_module()
    heartbeat_file = tmp_path / "worker.heartbeat"
    metrics_collector.reset()

    outcome = module.run_iteration(
        get_session_factory(),
        worker_id="test-worker",
        heartbeat_file=heartbeat_file,
    )

    assert outcome == "job"
    db_session.expire_all()
    job = db_session.get(AsyncJob, job_id)
    assert job is not None
    assert job.status == "succeeded"
    assert job.result_path is not None and get_storage_backend().exists(job.result_path)
    assert heartbeat_file.exists()
    assert ("export_geojson", "succeeded") in metrics_collector._job_counts

    dl = client.get(f"/api/v1/exports/{job_id}/download")
    assert dl.status_code == status.HTTP_200_OK


def test_worker_iteration_without_jobs_is_idle_and_beats(tmp_path: Path) -> None:
    module = load_worker_module()
    heartbeat_file = tmp_path / "worker.heartbeat"
    outcome = module.run_iteration(
        get_session_factory(), worker_id="test-worker", heartbeat_file=heartbeat_file
    )
    assert outcome == "idle"
    assert heartbeat_file.exists()
    assert time.time() - heartbeat_file.stat().st_mtime < 5


def test_worker_records_failed_job_metric(db_session: Session, tmp_path: Path) -> None:
    db_session.add(
        AsyncJob(
            type="import_commit",
            status="queued",
            idempotency_key="worker-fail-1",
            payload={"file_storage_path": "/nao/existe.geojson", "format": "geojson"},
        )
    )
    db_session.commit()
    module = load_worker_module()
    metrics_collector.reset()
    outcome = module.run_iteration(
        get_session_factory(),
        worker_id="test-worker",
        heartbeat_file=tmp_path / "hb",
    )
    assert outcome == "job"
    assert ("import_commit", "failed") in metrics_collector._job_counts


def test_worker_logs_are_valid_json_with_job_id(
    client: TestClient, db_session: Session, tmp_path: Path
) -> None:
    job_id, _ = request_export(client, db_session)
    module = load_worker_module()

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    worker_logger = logging.getLogger("ftth.worker")
    previous_level = worker_logger.level
    worker_logger.addHandler(handler)
    worker_logger.setLevel(logging.INFO)
    try:
        module.run_iteration(
            get_session_factory(),
            worker_id='worker-"aspas"',
            heartbeat_file=tmp_path / "hb",
        )
    finally:
        worker_logger.removeHandler(handler)
        worker_logger.setLevel(previous_level)

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert lines, "o worker deveria ter registrado logs"
    parsed = [json.loads(line) for line in lines]
    assert any(entry.get("job_id") == job_id for entry in parsed)


def test_compose_worker_has_heartbeat_healthcheck() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    worker = compose["services"]["worker"]
    healthcheck = worker.get("healthcheck")
    assert healthcheck, "serviço worker precisa de healthcheck (heartbeat)"
    assert healthcheck["test"]
    assert "WORKER_HEARTBEAT_FILE" in json.dumps(worker.get("environment", {})) or (
        "heartbeat" in json.dumps(healthcheck["test"]).lower()
    )


def test_heartbeat_healthcheck_script_detects_stale_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    heartbeat = tmp_path / "hb"
    monkeypatch.setenv("WORKER_HEARTBEAT_FILE", str(heartbeat))
    monkeypatch.setenv("WORKER_HEARTBEAT_MAX_AGE_SECONDS", "60")
    spec = importlib.util.spec_from_file_location(
        "check_worker_heartbeat", BACKEND_DIR / "scripts" / "check_worker_heartbeat.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.main() == 1  # ausente
    heartbeat.touch()
    assert module.main() == 0  # fresco
    old = time.time() - 3600
    os.utime(heartbeat, (old, old))
    assert module.main() == 1  # velho
