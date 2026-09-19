"""R16 (EST-13): cardinalidade limitada e métricas agregadas entre processos (API × worker)."""

import importlib.util
import json
import time
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import MAX_LABEL_SETS, UNMATCHED_ROUTE, MetricsCollector, metrics_collector
from app.core.metrics_store import MetricsStore, get_metrics_store, publish_metrics
from app.db.session import get_session_factory
from app.modules.imports.models import AsyncJob
from tests.conftest import create_test_user, login_test_client

WORKER_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_worker.py"


# ---------------------------------------------------------------------------------------------
# Cardinalidade
# ---------------------------------------------------------------------------------------------


def test_thousands_of_distinct_404_paths_do_not_grow_metric_keys() -> None:
    collector = MetricsCollector()
    collector.record_request(
        "GET", "/api/v1/existente", 200, 0.01, route_format="/api/v1/existente"
    )
    baseline = len(collector._http_requests)
    for i in range(10_000):
        collector.record_request("GET", f"/scan-{i}/segredo-{i * 7}", 404, 0.001, route_format=None)
    # todos os 404 sem rota caem na MESMA chave: __unmatched__
    assert len(collector._http_requests) == baseline + 1
    assert ("GET", UNMATCHED_ROUTE, 404) in collector._http_requests
    assert collector._http_requests[("GET", UNMATCHED_ROUTE, 404)] == 10_000
    assert len(collector._http_durations) == 2


def test_real_404_requests_use_the_fixed_unmatched_label(client: TestClient) -> None:
    metrics_collector.reset()
    for i in range(200):
        assert client.get(f"/nao-existe-{i}/x/{i}").status_code == status.HTTP_404_NOT_FOUND
    keys = {k for k in metrics_collector._http_requests if k[2] == 404}
    assert keys == {("GET", UNMATCHED_ROUTE, 404)}


def test_label_sets_are_capped_defensively() -> None:
    collector = MetricsCollector()
    for i in range(MAX_LABEL_SETS + 500):
        collector.record_request("GET", "/x", 200, 0.001, route_format=f"/rota/{i}")
    assert len(collector._http_requests) <= MAX_LABEL_SETS + 1  # + a chave de overflow
    assert len(collector._http_durations) <= MAX_LABEL_SETS + 1
    total = sum(collector._http_requests.values())
    assert total == MAX_LABEL_SETS + 500  # nada é perdido: só agregado em __overflow__


# ---------------------------------------------------------------------------------------------
# Agregação entre processos (API com vários workers + worker de jobs)
# ---------------------------------------------------------------------------------------------


def _collector_with(requests: int, jobs: int = 0) -> MetricsCollector:
    c = MetricsCollector()
    for _ in range(requests):
        c.record_request("GET", "/api/v1/sites", 200, 0.02, route_format="/api/v1/sites")
    for _ in range(jobs):
        c.record_job("export_geojson", "succeeded")
    return c


def test_snapshots_from_several_processes_are_summed(tmp_path: Path) -> None:
    api_a = MetricsStore(tmp_path, role="api", process_id="api-1")
    api_b = MetricsStore(tmp_path, role="api", process_id="api-2")
    worker = MetricsStore(tmp_path, role="worker", process_id="worker-1")
    api_a.publish(_collector_with(5), force=True)
    api_b.publish(_collector_with(7), force=True)
    worker.publish(_collector_with(0, jobs=3), force=True)

    reader = MetricsCollector()
    text = reader.to_prometheus_text(
        store=MetricsStore(tmp_path, role="api", process_id="api-reader")
    )
    assert 'ftth_http_requests_total{method="GET",path="/api/v1/sites",status="200"} 12' in text
    assert 'ftth_background_jobs_total{job_type="export_geojson",status="succeeded"} 3' in text
    assert 'ftth_processes{role="api"} 3' in text  # 2 publicados + o processo que atende o scrape
    assert 'ftth_processes{role="worker"} 1' in text
    assert 'ftth_http_request_duration_seconds_count{method="GET",path="/api/v1/sites"} 12' in text


def test_own_live_data_is_not_double_counted(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path, role="api", process_id="api-1")
    live = _collector_with(4)
    store.publish(live, force=True)  # o arquivo do próprio processo também existe
    text = live.to_prometheus_text(store=store)
    assert 'ftth_http_requests_total{method="GET",path="/api/v1/sites",status="200"} 4' in text


def test_stale_snapshots_are_ignored_and_removed(tmp_path: Path) -> None:
    dead = MetricsStore(tmp_path, role="api", process_id="api-morto", ttl_seconds=60)
    dead.publish(_collector_with(9), force=True)
    file = next(tmp_path.glob("*.json"))
    old = time.time() - 4000
    import os

    os.utime(file, (old, old))
    payload = json.loads(file.read_text())
    payload["updated_at"] = old
    file.write_text(json.dumps(payload))

    reader = MetricsStore(tmp_path, role="api", process_id="api-vivo", ttl_seconds=60)
    assert reader.load_peers() == []  # fora do TTL: não conta
    assert file.exists()  # ainda não é velho o bastante para ser apagado
    very_old = time.time() - 7200
    os.utime(file, (very_old, very_old))
    reader.load_peers()
    assert not file.exists()  # limpeza de arquivos muito antigos


def test_publish_is_throttled(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path, role="api", process_id="api-1", min_interval_seconds=60)
    collector = _collector_with(1)
    assert store.publish(collector) is True
    assert store.publish(collector) is False  # dentro do intervalo: não regrava
    assert store.publish(collector, force=True) is True


def test_metrics_endpoint_aggregates_worker_metrics(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METRICS_DIR", str(tmp_path))
    get_settings.cache_clear()
    MetricsStore(tmp_path, role="worker", process_id="worker-9").publish(
        _collector_with(0, jobs=4), force=True
    )
    create_test_user(db_session, "admin_metrics_r16@provedor.com.br", "admin")
    login_test_client(client, "admin_metrics_r16@provedor.com.br")

    resp = client.get("/api/v1/metrics")
    assert resp.status_code == status.HTTP_200_OK
    assert 'ftth_background_jobs_total{job_type="export_geojson",status="succeeded"} 4' in resp.text
    assert 'ftth_processes{role="worker"} 1' in resp.text
    assert 'ftth_processes{role="api"} 1' in resp.text

    as_json = client.get("/api/v1/metrics?format=json").json()
    assert {"job_type": "export_geojson", "status": "succeeded", "count": 4} in as_json[
        "background_jobs"
    ]


def test_metrics_stay_protected_with_multiprocess_enabled(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METRICS_DIR", str(tmp_path))
    get_settings.cache_clear()
    assert client.get("/api/v1/metrics").status_code == status.HTTP_401_UNAUTHORIZED


def test_worker_iteration_publishes_its_metrics(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METRICS_DIR", str(tmp_path / "metrics"))
    get_settings.cache_clear()
    db_session.add(
        AsyncJob(
            type="import_commit",
            status="queued",
            idempotency_key="metrics-worker",
            payload={"file_storage_path": "imports/nao-existe.geojson", "format": "geojson"},
        )
    )
    db_session.commit()
    spec = importlib.util.spec_from_file_location("run_worker_metrics", WORKER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metrics_collector.reset()
    module.run_iteration(get_session_factory(), "worker-metrics", tmp_path / "hb")

    files = list((tmp_path / "metrics").glob("worker-*.json"))
    assert files, "o worker deveria publicar seu snapshot de métricas"
    payload = json.loads(files[0].read_text())
    assert payload["role"] == "worker"
    assert payload["snapshot"]["jobs"]["import_commit|failed"] == 1


def test_single_process_mode_when_metrics_dir_is_not_configured() -> None:
    get_settings.cache_clear()
    assert get_settings().METRICS_DIR == ""
    assert get_metrics_store() is None
    publish_metrics(metrics_collector, force=True)  # no-op, sem erro


def test_heartbeat_keeps_an_idle_process_fresh_and_dead_ones_expire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.metrics_store import start_metrics_heartbeat, stop_metrics_heartbeats

    monkeypatch.setenv("METRICS_DIR", str(tmp_path))
    monkeypatch.setenv("METRICS_PUBLISH_INTERVAL_SECONDS", "0.1")
    get_settings.cache_clear()
    assert get_settings().METRICS_SNAPSHOT_TTL_SECONDS == 60
    start_metrics_heartbeat(metrics_collector, role="api")
    try:
        file = next(tmp_path.glob("api-*.json"))
        first = json.loads(file.read_text())["updated_at"]
        time.sleep(0.5)
        assert json.loads(file.read_text())["updated_at"] > first  # ocioso, mas vivo
    finally:
        stop_metrics_heartbeats()
