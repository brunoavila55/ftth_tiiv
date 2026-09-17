import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, VersionedModelMixin
from app.modules.connectivity.models import Terminal
from app.modules.inventory.models import Structure


class Cable(Base, VersionedModelMixin):
    """Cabo óptico instalado ou projetado na rede."""

    __tablename__ = "cables"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    fiber_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tube_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    color_standard: Mapped[str] = mapped_column(String(50), nullable=False, default="NBR")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="installed")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tubes: Mapped[list["Tube"]] = relationship(
        back_populates="cable",
        cascade="all, delete-orphan",
        order_by="Tube.number",
    )
    fibers: Mapped[list["Fiber"]] = relationship(
        back_populates="cable",
        cascade="all, delete-orphan",
        order_by="Fiber.global_number",
    )
    segments: Mapped[list["CableSegment"]] = relationship(
        back_populates="cable",
        passive_deletes="all",
    )


class Tube(Base, VersionedModelMixin):
    """Tubo loose ou agrupamento lógico de fibras dentro de um cabo."""

    __tablename__ = "tubes"

    cable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cables.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    color_name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_logical_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    cable: Mapped[Cable] = relationship(back_populates="tubes")
    fibers: Mapped[list["Fiber"]] = relationship(
        back_populates="tube",
        order_by="Fiber.tube_position",
    )

    __table_args__ = (
        UniqueConstraint("cable_id", "number", name="uq_tubes_cable_number"),
        CheckConstraint("number >= 1", name="chk_tube_number_positive"),
    )


class Fiber(Base, VersionedModelMixin):
    """Fibra óptica física individual de um cabo óptico."""

    __tablename__ = "fibers"

    cable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cables.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tube_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tubes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    global_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tube_position: Mapped[int] = mapped_column(Integer, nullable=False)
    color_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="installed")

    cable: Mapped[Cable] = relationship(back_populates="fibers")
    tube: Mapped[Tube] = relationship(back_populates="fibers")
    fiber_segments: Mapped[list["FiberSegment"]] = relationship(
        back_populates="fiber",
        passive_deletes="all",
    )

    __table_args__ = (
        UniqueConstraint("cable_id", "global_number", name="uq_fibers_cable_global_number"),
        CheckConstraint("global_number >= 1", name="chk_fiber_global_number_positive"),
        CheckConstraint("tube_position >= 1", name="chk_fiber_tube_position_positive"),
    )


class CableSegment(Base, VersionedModelMixin):
    """Trecho físico contínuo de cabo óptico ligando duas estruturas de acesso."""

    __tablename__ = "cable_segments"

    cable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cables.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    origin_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    destination_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    geometry: Mapped[Any] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )
    map_length_m: Mapped[float] = mapped_column(Float, nullable=False)
    measured_length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    slack_length_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    effective_length_m: Mapped[float] = mapped_column(Float, nullable=False)
    length_source: Mapped[str] = mapped_column(String(20), nullable=False, default="calculated")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="installed")

    cable: Mapped[Cable] = relationship(back_populates="segments")
    origin_structure: Mapped[Structure] = relationship(
        foreign_keys=[origin_structure_id],
    )
    destination_structure: Mapped[Structure] = relationship(
        foreign_keys=[destination_structure_id],
    )
    fiber_segments: Mapped[list["FiberSegment"]] = relationship(
        back_populates="cable_segment",
        cascade="all, delete-orphan",
        order_by="FiberSegment.fiber_number",
    )

    __table_args__ = (
        CheckConstraint("slack_length_m >= 0", name="chk_cable_segment_slack_positive"),
        CheckConstraint(
            "measured_length_m IS NULL OR measured_length_m >= 0",
            name="chk_cable_segment_measured_positive",
        ),
        CheckConstraint("map_length_m >= 0", name="chk_cable_segment_map_positive"),
        CheckConstraint(
            "origin_structure_id != destination_structure_id",
            name="chk_cable_segment_different_structures",
        ),
        Index("idx_cable_segments_origin_dest", "origin_structure_id", "destination_structure_id"),
    )


class FiberSegment(Base, VersionedModelMixin):
    """Instanciação de uma fibra óptica em um segmento de cabo específico, com duas pontas (A e B)."""

    __tablename__ = "fiber_segments"

    cable_segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cable_segments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiber_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fibers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiber_number: Mapped[int] = mapped_column(Integer, nullable=False)
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
    occupancy: Mapped[str] = mapped_column(String(50), nullable=False, default="free")

    cable_segment: Mapped[CableSegment] = relationship(back_populates="fiber_segments")
    fiber: Mapped[Fiber] = relationship(back_populates="fiber_segments")
    terminal_a: Mapped[Terminal] = relationship(foreign_keys=[terminal_a_id])
    terminal_b: Mapped[Terminal] = relationship(foreign_keys=[terminal_b_id])

    __table_args__ = (
        UniqueConstraint("cable_segment_id", "fiber_id", name="uq_fiber_segments_seg_fiber"),
        UniqueConstraint("cable_segment_id", "terminal_a_id", name="uq_fiber_segments_seg_term_a"),
        UniqueConstraint("cable_segment_id", "terminal_b_id", name="uq_fiber_segments_seg_term_b"),
        CheckConstraint(
            "terminal_a_id != terminal_b_id",
            name="chk_fiber_segment_different_terminals",
        ),
    )
