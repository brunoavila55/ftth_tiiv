import re
import threading
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

# Buckets padrão em segundos para latência HTTP
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
NUMBER_PATTERN = re.compile(r"(?<=/)\d+(?=/|$)")


def normalize_route_path(path: str, route_format: str | None = None) -> str:
    """Normaliza o caminho da URL substituindo identificadores dinâmicos por placeholders.

    Garante cardinalidade baixa (bounded cardinality) para métricas do Prometheus.
    Nunca expõe IDs, seriais ou dados pessoais nas labels das métricas.
    """
    if route_format:
        return route_format

    # Fallback caso a rota do Starlette/FastAPI não tenha sido identificada
    clean = UUID_PATTERN.sub("{id}", path)
    clean = NUMBER_PATTERN.sub("{id}", clean)
    return clean


class MetricsCollector:
    """Coletor thread-safe de métricas de desempenho e observabilidade (B16)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()

        # (method, path_pattern, status_code) -> count
        self._http_requests: dict[tuple[str, str, int], int] = {}

        # (method, path_pattern) -> {bucket: count, sum: float, count: int}
        self._http_durations: dict[tuple[str, str], dict[str, Any]] = {}

        # (job_type, status) -> count
        self._job_counts: dict[tuple[str, str], int] = {}

    def reset(self) -> None:
        """Limpa as métricas coletadas (útil para testes)."""
        with self._lock:
            self._http_requests.clear()
            self._http_durations.clear()
            self._job_counts.clear()
            self._start_time = time.time()

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
        route_format: str | None = None,
    ) -> None:
        """Registra a conclusão de uma requisição HTTP."""
        norm_path = normalize_route_path(path, route_format)
        req_key = (method.upper(), norm_path, status_code)
        dur_key = (method.upper(), norm_path)

        with self._lock:
            # Contador de requisições
            self._http_requests[req_key] = self._http_requests.get(req_key, 0) + 1

            # Histograma de duração
            if dur_key not in self._http_durations:
                self._http_durations[dur_key] = {
                    "count": 0,
                    "sum": 0.0,
                    "buckets": dict.fromkeys(LATENCY_BUCKETS, 0),
                }

            entry = self._http_durations[dur_key]
            entry["count"] += 1
            entry["sum"] += duration_seconds

            for b in LATENCY_BUCKETS:
                if duration_seconds <= b:
                    entry["buckets"][b] += 1

    def record_job(self, job_type: str, status: str) -> None:
        """Registra a contagem de tarefas assíncronas."""
        key = (job_type.lower(), status.lower())
        with self._lock:
            self._job_counts[key] = self._job_counts.get(key, 0) + 1

    def get_json_metrics(
        self,
        engine: Engine | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        """Retorna métricas em formato JSON estruturado."""
        uptime_seconds = round(time.time() - self._start_time, 2)

        with self._lock:
            requests_summary = [
                {
                    "method": k[0],
                    "path": k[1],
                    "status_code": k[2],
                    "count": v,
                }
                for k, v in self._http_requests.items()
            ]

            durations_summary = [
                {
                    "method": k[0],
                    "path": k[1],
                    "count": v["count"],
                    "sum_seconds": round(v["sum"], 4),
                    "avg_latency_ms": (
                        round((v["sum"] / v["count"]) * 1000, 2) if v["count"] > 0 else 0.0
                    ),
                    "p95_approx_seconds": self._calculate_p95_approx(v),
                }
                for k, v in self._http_durations.items()
            ]

            jobs_summary = [
                {
                    "job_type": k[0],
                    "status": k[1],
                    "count": v,
                }
                for k, v in self._job_counts.items()
            ]

        # Estatísticas do pool de conexões do banco
        pool_stats: dict[str, Any] = {}
        if engine and hasattr(engine, "pool") and isinstance(engine.pool, QueuePool):
            pool = engine.pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

        topology_revision: int | None = None
        if db:
            try:
                rev = db.execute(
                    text(
                        "SELECT topology_revision FROM network_topology_state WHERE id = 1 LIMIT 1;"
                    )
                ).scalar()
                topology_revision = int(rev) if rev is not None else 1
            except Exception:
                topology_revision = None

        return {
            "uptime_seconds": uptime_seconds,
            "topology_revision": topology_revision,
            "database_pool": pool_stats,
            "http_requests": requests_summary,
            "http_durations": durations_summary,
            "background_jobs": jobs_summary,
        }

    def _calculate_p95_approx(self, entry: dict[str, Any]) -> float:
        """Estima o p95 a partir dos buckets de histograma."""
        total = entry["count"]
        if total == 0:
            return 0.0
        target = 0.95 * total
        for b in LATENCY_BUCKETS:
            if entry["buckets"][b] >= target:
                return b
        return LATENCY_BUCKETS[-1]

    def to_prometheus_text(
        self,
        engine: Engine | None = None,
        db: Session | None = None,
    ) -> str:
        """Serializa todas as métricas no formato padrão de exposição do Prometheus."""
        lines: list[str] = [
            "# HELP ftth_uptime_seconds Tempo de atividade do processo em segundos",
            "# TYPE ftth_uptime_seconds gauge",
            f"ftth_uptime_seconds {round(time.time() - self._start_time, 2)}",
            "",
            "# HELP ftth_http_requests_total Total de requisições HTTP atendidas por método, rota e status",
            "# TYPE ftth_http_requests_total counter",
        ]

        with self._lock:
            for (method, path, status), count in sorted(self._http_requests.items()):
                lines.append(
                    f'ftth_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

            lines.extend(
                [
                    "",
                    "# HELP ftth_http_request_duration_seconds Duração das requisições HTTP em segundos",
                    "# TYPE ftth_http_request_duration_seconds histogram",
                ]
            )

            for (method, path), entry in sorted(self._http_durations.items()):
                for b in LATENCY_BUCKETS:
                    b_count = entry["buckets"][b]
                    lines.append(
                        f'ftth_http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{b}"}} {b_count}'
                    )
                lines.append(
                    f'ftth_http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="+Inf"}} {entry["count"]}'
                )
                lines.append(
                    f'ftth_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {round(entry["sum"], 6)}'
                )
                lines.append(
                    f'ftth_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {entry["count"]}'
                )

            lines.extend(
                [
                    "",
                    "# HELP ftth_background_jobs_total Total de jobs assíncronos processados",
                    "# TYPE ftth_background_jobs_total counter",
                ]
            )

            for (job_type, job_status), count in sorted(self._job_counts.items()):
                lines.append(
                    f'ftth_background_jobs_total{{job_type="{job_type}",status="{job_status}"}} {count}'
                )

        # Métricas do Banco de Dados
        if engine and hasattr(engine, "pool") and isinstance(engine.pool, QueuePool):
            pool = engine.pool
            lines.extend(
                [
                    "",
                    "# HELP ftth_db_pool_size Capacidade configurada do pool de conexões do banco",
                    "# TYPE ftth_db_pool_size gauge",
                    f"ftth_db_pool_size {pool.size()}",
                    "# HELP ftth_db_pool_checked_out Conexões ativas em uso concorrente",
                    "# TYPE ftth_db_pool_checked_out gauge",
                    f"ftth_db_pool_checked_out {pool.checkedout()}",
                    "# HELP ftth_db_pool_overflow Conexões temporárias excedentes abertas além do pool",
                    "# TYPE ftth_db_pool_overflow gauge",
                    f"ftth_db_pool_overflow {pool.overflow()}",
                ]
            )

        # Revisão monotônica da topologia
        if db:
            try:
                rev = db.execute(
                    text(
                        "SELECT topology_revision FROM network_topology_state WHERE id = 1 LIMIT 1;"
                    )
                ).scalar()
                current_rev = int(rev) if rev is not None else 1
                lines.extend(
                    [
                        "",
                        "# HELP ftth_topology_revision Revisão monotônica atual da topologia física e lógica",
                        "# TYPE ftth_topology_revision gauge",
                        f"ftth_topology_revision {current_rev}",
                    ]
                )
            except Exception:
                pass

        lines.append("")
        return "\n".join(lines)


# Instância global singleton
metrics_collector = MetricsCollector()
