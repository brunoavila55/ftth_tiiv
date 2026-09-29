import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, VersionedModelMixin


class Site(Base, VersionedModelMixin):
    """Local técnico central, POP ou abrigo de telecomunicações."""

    __tablename__ = "sites"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="pop")
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="installed")
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    structures: Mapped[list["Structure"]] = relationship(
        back_populates="site",
        passive_deletes="all",
    )
    devices: Mapped[list["Device"]] = relationship(
        back_populates="site",
        passive_deletes="all",
    )


class Structure(Base, VersionedModelMixin):
    """Infraestrutura física externa ou interna: Poste, CEO, CTO, Caixa de Passagem ou Pedestal."""

    __tablename__ = "structures"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="installed")
    condition: Mapped[str] = mapped_column(String(50), nullable=False, default="ok")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site | None"] = relationship(back_populates="structures")
    devices: Mapped[list["Device"]] = relationship(
        back_populates="structure",
        passive_deletes="all",
    )
    ports: Mapped[list["Port"]] = relationship(
        back_populates="structure",
        passive_deletes="all",
    )


class Device(Base, VersionedModelMixin):
    """Dispositivo de rede ativo ou passivo: OLT, DIO, ONU ou Switch."""

    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(
            "((site_id IS NOT NULL AND structure_id IS NULL) OR (site_id IS NULL AND structure_id IS NOT NULL))",
            name="chk_device_single_location",
        ),
        UniqueConstraint("id", "site_id", name="uq_devices_id_site_id"),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structures.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="installed")
    condition: Mapped[str] = mapped_column(String(50), nullable=False, default="ok")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site | None"] = relationship(back_populates="devices")
    structure: Mapped["Structure | None"] = relationship(back_populates="devices")
    ports: Mapped[list["Port"]] = relationship(
        back_populates="device",
        passive_deletes="all",
    )


class RadioLink(Base, VersionedModelMixin):
    """Enlace de rádio entre dois sites wireless e seus rádios de ponta."""

    __tablename__ = "radio_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["radio_a_id", "site_a_id"],
            ["devices.id", "devices.site_id"],
            name="fk_radio_link_a_device_site",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["radio_b_id", "site_b_id"],
            ["devices.id", "devices.site_id"],
            name="fk_radio_link_b_device_site",
            ondelete="RESTRICT",
        ),
        CheckConstraint("site_a_id <> site_b_id", name="chk_radio_link_distinct_sites"),
        CheckConstraint("radio_a_id <> radio_b_id", name="chk_radio_link_distinct_radios"),
        CheckConstraint(
            "frequency_mhz > 0 AND frequency_mhz <= 100000", name="chk_radio_link_frequency"
        ),
        CheckConstraint(
            "channel_width_mhz > 0 AND channel_width_mhz <= 10000", name="chk_radio_link_width"
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    site_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    radio_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    radio_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    frequency_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    channel_width_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planned")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Port(Base, VersionedModelMixin):
    """Porta física óptica pertencente exclusivamente a um dispositivo ou a uma estrutura."""

    __tablename__ = "ports"
    __table_args__ = (
        CheckConstraint(
            "((device_id IS NOT NULL AND structure_id IS NULL) OR (device_id IS NULL AND structure_id IS NOT NULL))",
            name="chk_port_single_owner",
        ),
        Index(
            "uq_ports_device_name",
            "device_id",
            "name",
            unique=True,
            postgresql_where=(text("device_id IS NOT NULL")),
        ),
        Index(
            "uq_ports_structure_name",
            "structure_id",
            "name",
            unique=True,
            postgresql_where=(text("structure_id IS NOT NULL")),
        ),
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("structures.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    has_internal_pass_through: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SC/APC")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    device: Mapped["Device | None"] = relationship(back_populates="ports")
    structure: Mapped["Structure | None"] = relationship(back_populates="ports")
