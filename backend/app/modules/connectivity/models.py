import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, VersionedModelMixin
from app.modules.inventory.models import Site, Structure


class Terminal(Base, VersionedModelMixin):
    """Terminal óptico normalizado (extremidade de fibra, porta ou entrada/saída de splitter)."""

    __tablename__ = "terminals"

    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structures.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    is_occupied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    structure: Mapped[Structure | None] = relationship(foreign_keys=[structure_id])
    site: Mapped[Site | None] = relationship(foreign_keys=[site_id])

    __table_args__ = (
        CheckConstraint(
            "structure_id IS NOT NULL OR site_id IS NOT NULL",
            name="chk_terminal_location_defined",
        ),
        Index("idx_terminals_kind_structure", "kind", "structure_id"),
    )


class Connection(Base, VersionedModelMixin):
    """Conexão física ou lógica entre dois terminais ópticos (fusão, patch cord ou continuidade)."""

    __tablename__ = "connections"

    terminal_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    terminal_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    connection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    loss_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structures.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    terminal_a: Mapped[Terminal] = relationship(foreign_keys=[terminal_a_id])
    terminal_b: Mapped[Terminal] = relationship(foreign_keys=[terminal_b_id])
    structure: Mapped[Structure | None] = relationship(foreign_keys=[structure_id])

    __table_args__ = (
        CheckConstraint(
            "terminal_a_id != terminal_b_id",
            name="chk_connection_distinct_terminals",
        ),
        CheckConstraint("loss_db >= 0.0", name="chk_connection_loss_positive"),
        Index("idx_connections_term_a_b", "terminal_a_id", "terminal_b_id"),
    )
