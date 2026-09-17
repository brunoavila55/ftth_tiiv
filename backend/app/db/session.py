from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Retorna a engine SQLAlchemy síncrona com pool pre-ping ativo."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
        )
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
