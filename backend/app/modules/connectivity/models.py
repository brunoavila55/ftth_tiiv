import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, VersionedModelMixin
from app.modules.identity.models import User
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
    occupancy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free"
    )  # free, reserved, connected
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    structure: Mapped[Structure | None] = relationship(foreign_keys=[structure_id])
    site: Mapped[Site | None] = relationship(foreign_keys=[site_id])

    __table_args__ = (
        CheckConstraint(
            "structure_id IS NOT NULL OR site_id IS NOT NULL",
            name="chk_terminal_location_defined",
        ),
        Index("idx_terminals_kind_structure", "kind", "structure_id"),
        Index("idx_terminals_occupancy", "occupancy"),
        Index("idx_terminals_entity", "entity_type", "entity_id"),
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
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    terminal_a: Mapped[Terminal] = relationship(foreign_keys=[terminal_a_id])
    terminal_b: Mapped[Terminal] = relationship(foreign_keys=[terminal_b_id])
    structure: Mapped[Structure | None] = relationship(foreign_keys=[structure_id])
    site: Mapped[Site | None] = relationship(foreign_keys=[site_id])

    __table_args__ = (
        CheckConstraint(
            "terminal_a_id != terminal_b_id",
            name="chk_connection_distinct_terminals",
        ),
        CheckConstraint("loss_db >= 0.0", name="chk_connection_loss_positive"),
        CheckConstraint(
            "structure_id IS NOT NULL OR site_id IS NOT NULL",
            name="chk_connection_location_defined",
        ),
        Index("idx_connections_term_a_b", "terminal_a_id", "terminal_b_id"),
        Index("idx_connections_active", "is_active"),
    )


class ConnectionEndpoint(Base, VersionedModelMixin):
    """Mapeamento e controle de unicidade de terminal em conexão ativa."""

    __tablename__ = "connection_endpoints"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    terminal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    connection: Mapped[Connection] = relationship(foreign_keys=[connection_id])
    terminal: Mapped[Terminal] = relationship(foreign_keys=[terminal_id])

    __table_args__ = (
        Index(
            "uq_active_connection_endpoint",
            "terminal_id",
            unique=True,
            postgresql_where=(is_active == True),  # noqa: E712
        ),
        Index("idx_conn_endpoints_conn_active", "connection_id", "is_active"),
    )


class TerminalReservation(Base, VersionedModelMixin):
    """Reserva de terminal óptico com motivo, responsável e expiração opcional."""

    __tablename__ = "terminal_reservations"

    terminal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    reserved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    terminal: Mapped[Terminal] = relationship(foreign_keys=[terminal_id])
    reserved_by: Mapped[User | None] = relationship(foreign_keys=[reserved_by_id])

    __table_args__ = (
        Index(
            "uq_active_terminal_reservation",
            "terminal_id",
            unique=True,
            postgresql_where=(is_active == True),  # noqa: E712
        ),
        Index("idx_term_reservations_term_active", "terminal_id", "is_active"),
    )


class InternalEdge(Base, VersionedModelMixin):
    """Aresta interna normalizada (continuidade de fibra A-B, travessia frente-trás de DIO ou caminho de splitter)."""

    __tablename__ = "internal_edges"

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
    edge_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # fiber_continuity, port_adapter, splitter_pass
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # fiber_segment, port, splitter
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    loss_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_bidirectional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    terminal_a: Mapped[Terminal] = relationship(foreign_keys=[terminal_a_id])
    terminal_b: Mapped[Terminal] = relationship(foreign_keys=[terminal_b_id])

    __table_args__ = (
        CheckConstraint(
            "terminal_a_id != terminal_b_id", name="chk_internal_edge_distinct_terminals"
        ),
        CheckConstraint("loss_db >= 0.0", name="chk_internal_edge_loss_positive"),
        Index("uq_internal_edge_terminals", "terminal_a_id", "terminal_b_id", unique=True),
    )


class Splitter(Base, VersionedModelMixin):
    """Splitter óptico passivo (balanceado ou desbalanceado) com entrada e N saídas."""

    __tablename__ = "splitters"

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
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    splitter_type: Mapped[str] = mapped_column(String(50), nullable=False, default="balanced")
    ratio: Mapped[str] = mapped_column(String(20), nullable=False, default="1:8")
    input_terminal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    structure: Mapped[Structure | None] = relationship(foreign_keys=[structure_id])
    site: Mapped[Site | None] = relationship(foreign_keys=[site_id])
    input_terminal: Mapped[Terminal] = relationship(foreign_keys=[input_terminal_id])
    outputs: Mapped[list["SplitterOutput"]] = relationship(
        back_populates="splitter",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "structure_id IS NOT NULL OR site_id IS NOT NULL",
            name="chk_splitter_location_defined",
        ),
        Index("idx_splitters_structure", "structure_id"),
    )


class SplitterOutput(Base, VersionedModelMixin):
    """Saída óptica de um splitter com perda nominal de derivação."""

    __tablename__ = "splitter_outputs"

    splitter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("splitters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    output_number: Mapped[int] = mapped_column(nullable=False)
    terminal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nominal_loss_db: Mapped[float] = mapped_column(Float, nullable=False, default=10.5)
    measured_loss_db: Mapped[float | None] = mapped_column(Float, nullable=True)

    splitter: Mapped[Splitter] = relationship(back_populates="outputs")
    terminal: Mapped[Terminal] = relationship(foreign_keys=[terminal_id])

    __table_args__ = (
        CheckConstraint("nominal_loss_db >= 0.0", name="chk_splitter_output_nominal_loss_positive"),
        Index("uq_splitter_outputs_num", "splitter_id", "output_number", unique=True),
    )
