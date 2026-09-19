"""Métricas agregadas entre processos (API com vários workers + worker de jobs) — EST-13.

Cada processo publica periodicamente um snapshot JSON (escrita atômica) em `METRICS_DIR`; o
`/metrics` soma o snapshot vivo do processo que atende o scrape com os dos demais. Sem dependência
externa. Snapshots parados há mais de `ttl` segundos (processo morto) deixam de contar — os
contadores dele "zeram", como em qualquer reinício de processo no Prometheus — e arquivos com mais
de 1 h são apagados.
"""

import contextlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.core.metrics import MetricsCollector

STALE_FILE_SECONDS = 3600


class MetricsStore:
    def __init__(
        self,
        directory: Path | str,
        role: str,
        process_id: str | None = None,
        ttl_seconds: int = 300,
        min_interval_seconds: float = 5.0,
    ) -> None:
        self.directory = Path(directory)
        self.role = role
        self.process_id = process_id or f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.ttl_seconds = ttl_seconds
        self.min_interval_seconds = min_interval_seconds
        self._last_publish = 0.0

    @property
    def path(self) -> Path:
        return self.directory / f"{self.role}-{self.process_id}.json"

    def publish(self, collector: "MetricsCollector", force: bool = False) -> bool:
        """Grava o snapshot deste processo (no máximo a cada `min_interval_seconds`)."""
        now = time.monotonic()
        if not force and now - self._last_publish < self.min_interval_seconds:
            return False
        payload: dict[str, Any] = {
            "role": self.role,
            "process_id": self.process_id,
            "updated_at": time.time(),
            "snapshot": collector.snapshot(),
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, self.path)  # atômico: o leitor nunca vê arquivo pela metade
        self._last_publish = now
        return True

    def load_peers(self) -> list[dict[str, Any]]:
        """Snapshots frescos dos OUTROS processos (exclui o próprio); limpa arquivos muito velhos."""
        peers: list[dict[str, Any]] = []
        if not self.directory.exists():
            return peers
        now = time.time()
        for file in self.directory.glob("*.json"):
            if file == self.path:
                continue
            try:
                if now - file.stat().st_mtime > STALE_FILE_SECONDS:
                    file.unlink(missing_ok=True)
                    continue
                payload = json.loads(file.read_text())
            except (OSError, ValueError):
                continue  # arquivo sendo substituído/corrompido: ignora nesta leitura
            if now - float(payload.get("updated_at", 0)) <= self.ttl_seconds:
                peers.append(payload)
        return peers


_stores: dict[tuple[str, str], MetricsStore] = {}


def get_metrics_store(role: str = "api") -> MetricsStore | None:
    """Store do processo (por papel) se METRICS_DIR estiver configurado; senão None."""
    settings = get_settings()
    if not settings.METRICS_DIR:
        return None
    key = (settings.METRICS_DIR, role)
    store = _stores.get(key)
    if store is None:
        store = _stores[key] = MetricsStore(
            settings.METRICS_DIR, role, ttl_seconds=settings.METRICS_SNAPSHOT_TTL_SECONDS
        )
    return store


def publish_metrics(collector: "MetricsCollector", role: str = "api", force: bool = False) -> None:
    """Publica o snapshot do processo se o modo multiprocesso estiver ligado (no-op caso contrário)."""
    store = get_metrics_store(role)
    if store is None:
        return
    with contextlib.suppress(OSError):  # métricas nunca podem derrubar a requisição/worker
        store.publish(collector, force=force)


_heartbeats: dict[tuple[str, str], threading.Event] = {}


def start_metrics_heartbeat(collector: "MetricsCollector", role: str = "api") -> None:
    """Publica o snapshot a cada METRICS_PUBLISH_INTERVAL_SECONDS numa thread daemon.

    Mantém `updated_at` fresco mesmo com o processo ocioso; assim o TTL pode ser curto e um
    processo morto some rápido do somatório (sem inflar `ftth_processes` após um deploy).
    """
    store = get_metrics_store(role)
    if store is None:
        return
    key = (str(store.directory), role)
    if key in _heartbeats:
        return
    stop = threading.Event()
    _heartbeats[key] = stop
    interval = get_settings().METRICS_PUBLISH_INTERVAL_SECONDS

    def loop() -> None:
        while not stop.wait(interval):
            with contextlib.suppress(OSError):
                store.publish(collector, force=True)

    threading.Thread(target=loop, name=f"metrics-heartbeat-{role}", daemon=True).start()
    with contextlib.suppress(OSError):
        store.publish(collector, force=True)


def stop_metrics_heartbeats() -> None:
    for stop in _heartbeats.values():
        stop.set()
    _heartbeats.clear()
