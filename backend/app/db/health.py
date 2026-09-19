import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.db.health")


@lru_cache
def _readiness_engine(database_url: str, timeout_seconds: int) -> Engine:
    """Engine dedicada da readiness: sem pool (NullPool), com connect/statement timeout curtos.

    Independe do pool da aplicação — uma API saturada não derruba a sonda nem a faz esperar.
    """
    return create_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": timeout_seconds,
            "options": f"-c statement_timeout={timeout_seconds * 1000}",
        },
    )


def _engine() -> Engine:
    settings = get_settings()
    return _readiness_engine(settings.DATABASE_URL, settings.HEALTH_DB_TIMEOUT_SECONDS)


def check_database_connectivity() -> dict[str, Any]:
    """Verifica a conectividade (conexão curta e dedicada) com medição de latência."""
    start_time = time.perf_counter()
    try:
        with _engine().connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if result == 1:
            return {
                "status": "connected",
                "latency_ms": latency_ms,
            }
        return {
            "status": "error",
            "message": "Resposta inesperada do banco de dados",
        }
    except Exception as exc:
        logger.warning(f"Falha na verificação de conectividade do banco: {exc}")
        return {
            "status": "disconnected",
            "message": "Não foi possível conectar ao banco de dados",
        }


@lru_cache
def get_expected_migration_head() -> str | None:
    """Revisão 'head' esperada do Alembic — lida uma vez (cache), não a cada chamada da sonda."""
    try:
        backend_dir = Path(__file__).resolve().parent.parent.parent
        alembic_ini_path = backend_dir / "alembic.ini"
        if not alembic_ini_path.exists():
            return None
        alembic_cfg = Config(str(alembic_ini_path))
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        head = script_dir.get_current_head()
        return head
    except Exception as exc:
        logger.warning(f"Não foi possível obter a revisão head do Alembic: {exc}")
        return None


def check_database_migrations() -> dict[str, Any]:
    """Verifica a versão atual das migrações aplicadas no banco contra a head esperada."""
    try:
        # Checa se a tabela alembic_version existe e obtém a versão atual
        with _engine().connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        current_version = str(result) if result else None
    except Exception:
        return {
            "status": "pending",
            "message": "Tabela de migrações alembic_version não encontrada no banco",
            "current_revision": None,
            "expected_revision": get_expected_migration_head(),
        }

    expected_head = get_expected_migration_head()
    if expected_head and current_version != expected_head:
        return {
            "status": "mismatch",
            "message": "Migrações pendentes ou divergentes no banco",
            "current_revision": current_version,
            "expected_revision": expected_head,
        }

    return {
        "status": "applied",
        "current_revision": current_version,
        "expected_revision": expected_head,
    }
