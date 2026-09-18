"""Worker em segundo plano do FTTH Manager para processamento de jobs assíncronos.

Consome filas do PostgreSQL usando 'SELECT FOR UPDATE SKIP LOCKED', renova leases/heartbeats,
processa importações, exportações, e executa rotinas de limpeza de arquivos expirados.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
import uuid

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.jobs.service import (
    claim_next_job,
    clean_expired_previews_and_exports,
    process_claimed_job,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("ftth.worker")

running = True


def handle_shutdown(signum: int, frame: object) -> None:
    global running
    sig_name = signal.Signals(signum).name
    logger.info(f"Sinal de encerramento recebido ({sig_name}). Finalizando worker graciosamente...")
    running = False


def main() -> int:
    global running
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    settings = get_settings()
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    logger.info(f"FTTH Manager Worker iniciado [ID: {worker_id}] (Ambiente: {settings.ENVIRONMENT})")

    factory = get_session_factory()
    last_cleanup_time = 0.0

    while running:
        try:
            with factory() as db:
                # 1. Tenta reivindicar próximo job pendente
                job = claim_next_job(db, worker_id=worker_id, lease_seconds=60)
                if job:
                    logger.info(f"Processando job '{job.id}' [Tipo: {job.type}]...")
                    start_t = time.time()
                    success = process_claimed_job(db, job, worker_id=worker_id)
                    duration = time.time() - start_t
                    status_str = "sucesso" if success else "falha"
                    logger.info(
                        f"Job '{job.id}' finalizado com {status_str} em {duration:.2f}s."
                    )
                    continue

                # 2. Rotina periódica de limpeza de arquivos temporários e prévias expiradas
                now = time.time()
                if now - last_cleanup_time > 60:
                    clean_res = clean_expired_previews_and_exports(db)
                    if clean_res.get("cleaned_previews", 0) > 0:
                        logger.info(f"Limpeza de retenção: {clean_res}")
                    last_cleanup_time = now

        except Exception as e:
            logger.error(f"Erro no loop do worker: {e}", exc_info=True)

        # Intervalo de espera entre polling (2 segundos)
        for _ in range(20):
            if not running:
                break
            time.sleep(0.1)

    logger.info(f"FTTH Manager Worker [ID: {worker_id}] encerrado com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
