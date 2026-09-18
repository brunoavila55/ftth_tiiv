import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, VersionedModelMixin


class OpticalMeasurement(Base, VersionedModelMixin):
    """Registro de medição de potência óptica realizada em campo ou via telemetria."""

    __tablename__ = "optical_measurements"
    __table_args__ = (
        CheckConstraint(
            "wavelength_nm >= 800 AND wavelength_nm <= 2000",
            name="chk_optical_measurement_wavelength",
        ),
        CheckConstraint(
            "direction IN ('downstream', 'upstream')",
            name="chk_optical_measurement_direction",
        ),
        CheckConstraint(
            "origin IN ('manual_entry', 'field_power_meter', 'otdr')",
            name="chk_optical_measurement_origin",
        ),
    )

    terminal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_links.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    power_dbm: Mapped[float] = mapped_column(Float, nullable=False)
    wavelength_nm: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="downstream")
    origin: Mapped[str] = mapped_column(String(50), nullable=False, default="manual_entry")
    instrument_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    predicted_power_dbm: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_loss_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    topology_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calculation_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(astext_type=Text()), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relacionamentos
    terminal = relationship("Terminal", foreign_keys=[terminal_id])
    service_link = relationship("ServiceLink", foreign_keys=[service_link_id])
    user = relationship("User", foreign_keys=[user_id])
