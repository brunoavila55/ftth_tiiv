import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AsyncJob(Base, TimestampMixin):
    """Fila de execução assíncrona de jobs (importações e exportações) baseada em PostgreSQL."""

    __tablename__ = "async_jobs"
    __table_args__ = (
        CheckConstraint(
            "type IN ('import_commit', 'export_geojson', 'export_kml', 'export_csv')",
            name="chk_async_job_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="chk_async_job_status",
        ),
        CheckConstraint(
            "progress_percentage >= 0 AND progress_percentage <= 100",
            name="chk_async_job_progress",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Concorrência, lease e recuperação de crash
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    user = relationship("User", foreign_keys=[user_id])


class ImportPreview(Base, TimestampMixin):
    """Rascunho temporário com validações sintáticas e semânticas de arquivo antes do commit."""

    __tablename__ = "import_previews"
    __table_args__ = (
        CheckConstraint(
            "format IN ('geojson', 'kml', 'csv')",
            name="chk_import_preview_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collision_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    file_storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    committed_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("async_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relacionamentos
    user = relationship("User", foreign_keys=[user_id])
    committed_job = relationship("AsyncJob", foreign_keys=[committed_job_id])
