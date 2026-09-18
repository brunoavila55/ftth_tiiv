import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, VersionedModelMixin
from app.modules.inventory.models import Device, Port


class Customer(Base, VersionedModelMixin):
    """Cliente ou assinante atendido pela infraestrutura FTTH."""

    __tablename__ = "customers"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    service_links: Mapped[list["ServiceLink"]] = relationship(
        back_populates="customer",
        passive_deletes="all",
    )


class ServiceLink(Base, VersionedModelMixin):
    """Vínculo histórico e operacional entre Cliente, Equipamento ONU e Porta da CTO."""

    __tablename__ = "service_links"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    onu_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    port_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ports.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="service_links")
    onu_device: Mapped[Device] = relationship(foreign_keys=[onu_device_id])
    port: Mapped[Port] = relationship(foreign_keys=[port_id])

    __table_args__ = (
        # Garante que uma porta CTO só possui 1 atendimento ativo por vez
        Index(
            "uq_active_port_service_link",
            "port_id",
            unique=True,
            postgresql_where=(status == "active"),
        ),
        # Garante que um equipamento ONU só possui 1 atendimento ativo por vez
        Index(
            "uq_active_onu_service_link",
            "onu_device_id",
            unique=True,
            postgresql_where=(status == "active"),
        ),
        Index("idx_service_links_customer_status", "customer_id", "status"),
    )
