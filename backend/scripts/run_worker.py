"""Worker em segundo plano do FTTH Manager para processamento de jobs assíncronos.

Consome filas do PostgreSQL usando 'SELECT FOR UPDATE SKIP LOCKED', renova leases/heartbeats,
processa importações, exportações, e executa rotinas de limpeza de arquivos expirados.

A cada iteração saudável do loop o worker grava um heartbeat em `WORKER_HEARTBEAT_FILE`, que o
HEALTHCHECK do compose consulta (`scripts/check_worker_heartbeat.py`).
"""

from __future__ import annotations

import logging
import signal
import sys
import time
import uuid
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import job_id_ctx, setup_logging
from app.db.session import get_session_factory
from app.modules.jobs.service import (
    claim_next_job,
    clean_expired_previews_and_exports,
    process_claimed_job,
)

logger = logging.getLogger("ftth.worker")

running = True
CLEANUP_INTERVAL_SECONDS = 60


def handle_shutdown(signum: int, frame: object) -> None:
    global running
    sig_name = signal.Signals(signum).name
    logger.info(
        "Sinal de encerramento recebido (%s). Finalizando worker graciosamente...", sig_name
    )
    running = False


def touch_heartbeat(path: Path) -> None:
    """Atualiza o arquivo de heartbeat (mtime) consultado pelo HEALTHCHECK."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    except OSError:
        logger.warning("Não foi possível gravar o heartbeat em '%s'.", path, exc_info=True)


def run_iteration(
    factory: sessionmaker[Session],
    worker_id: str,
    heartbeat_file: Path,
    cleanup_state: dict[str, float] | None = None,
) -> str:
    """Executa uma iteração do loop. Retorna 'job' se processou um job, senão 'idle'."""
    cleanup_state = cleanup_state if cleanup_state is not None else {"last": 0.0}

    with factory() as db:
        job = claim_next_job(db, worker_id=worker_id)
        touch_heartbeat(heartbeat_file)
        if job:
            token = job_id_ctx.set(str(job.id))
            try:
                logger.info("Processando job '%s' [Tipo: %s]...", job.id, job.type)
                start_t = time.time()
                success = process_claimed_job(
                    db,
                    job,
                    worker_id=worker_id,
                    # jobs longos: a thread de lease também mantém o heartbeat do healthcheck
                    on_heartbeat=lambda: touch_heartbeat(heartbeat_file),
                )
                duration = time.time() - start_t
                logger.info(
                    "Job '%s' finalizado com %s em %.2fs.",
                    job.id,
                    "sucesso" if success else "falha",
                    duration,
                )
            finally:
                job_id_ctx.reset(token)
            touch_heartbeat(heartbeat_file)
            return "job"

        # Rotina periódica de limpeza de arquivos temporários e prévias expiradas
        now = time.time()
        if now - cleanup_state["last"] > CLEANUP_INTERVAL_SECONDS:
            clean_res = clean_expired_previews_and_exports(db)
            if clean_res.get("cleaned_previews", 0) > 0:
                logger.info("Limpeza de retenção: %s", clean_res)
            cleanup_state["last"] = now

    return "idle"


def main() -> int:
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    logger.info(
        "FTTH Manager Worker iniciado [ID: %s] (Ambiente: %s)", worker_id, settings.ENVIRONMENT
    )

    factory = get_session_factory()
    heartbeat_file = Path(settings.WORKER_HEARTBEAT_FILE)
    cleanup_state: dict[str, float] = {"last": 0.0}

    while running:
        outcome = "idle"
        try:
            outcome = run_iteration(factory, worker_id, heartbeat_file, cleanup_state)
        except Exception:
            logger.exception("Erro no loop do worker")

        if outcome == "job":
            continue  # há possivelmente mais jobs na fila: não espera

        # Intervalo de espera entre polling (2 segundos)
        for _ in range(20):
            if not running:
                break
            time.sleep(0.1)

    logger.info("FTTH Manager Worker [ID: %s] encerrado com sucesso.", worker_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
