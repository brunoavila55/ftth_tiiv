import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, VersionedModelMixin
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

    segments: Mapped[list["CableSegment"]] = relationship(
        back_populates="cable",
        passive_deletes="all",
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
