from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def build_engine(statement_timeout_ms: int | None = None) -> Engine:
    """Cria uma engine com pool, connect_timeout e statement_timeout no servidor.

    `statement_timeout_ms` padrão = DB_STATEMENT_TIMEOUT_MS (API). O worker de jobs usa
    DB_WORKER_STATEMENT_TIMEOUT_MS (importações longas).
    """
    settings = get_settings()
    timeout_ms = (
        settings.DB_STATEMENT_TIMEOUT_MS if statement_timeout_ms is None else statement_timeout_ms
    )
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        connect_args={
            "connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
            "options": f"-c statement_timeout={int(timeout_ms)}",
        },
    )


def get_engine() -> Engine:
    """Retorna a engine SQLAlchemy síncrona (pool pre-ping, connect e statement timeout)."""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Retorna a fábrica de sessões síncronas."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI que fornece uma sessão de banco e garante seu fechamento."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def set_engine_and_factory(custom_engine: Engine) -> None:
    """Permite injetar uma engine customizada (útil para testes isolados)."""
    global _engine, _SessionFactory
    _engine = custom_engine
    _SessionFactory = sessionmaker(
        bind=custom_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
