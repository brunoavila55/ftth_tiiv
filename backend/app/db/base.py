import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base declarativa raiz para todos os modelos ORM."""

    pass


class TimestampMixin:
    """Mixin com timestamps UTC de auditoria temporal."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class VersionedModelMixin(TimestampMixin):
    """Mixin para modelos de inventário e rede com UUID e versão monotônica de concorrência."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        doc="Versão monotônica incremental para controle de concorrência otimista (If-Match)",
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:
        # UPDATE/DELETE viram `... WHERE id = :id AND version = :versão_lida` (StaleDataError se
        # outra transação gravou antes). O incremento continua sendo feito pelo serviço
        # (`obj.version += 1`), por isso o gerador automático fica desligado.
        return {"version_id_col": cls.version, "version_id_generator": False}
