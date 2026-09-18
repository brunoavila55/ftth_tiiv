"""create async_jobs and import_previews tables

Revision ID: 0010_async_jobs_and_imports
Revises: 0009_attachments
Create Date: 2026-09-18 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_async_jobs_and_imports"
down_revision: str | None = "0009_attachments"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. async_jobs
    op.create_table(
        "async_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(length=50), nullable=False, index=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued", index=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_path", sa.String(length=500), nullable=True),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "type IN ('import_commit', 'export_geojson', 'export_kml', 'export_csv')",
            name="chk_async_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="chk_async_job_status",
        ),
        sa.CheckConstraint(
            "progress_percentage >= 0 AND progress_percentage <= 100",
            name="chk_async_job_progress",
        ),
    )

    op.create_index(
        "idx_async_jobs_worker_poll",
        "async_jobs",
        ["status", "lease_expires_at", "created_at"],
    )

    # 2. import_previews
    op.create_table(
        "import_previews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_hash", sa.String(length=64), nullable=False, index=True),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("collision_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("file_storage_path", sa.String(length=500), nullable=False),
        sa.Column(
            "committed_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("async_jobs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "format IN ('geojson', 'kml', 'csv')",
            name="chk_import_preview_format",
        ),
    )


def downgrade() -> None:
    op.drop_table("import_previews")
    op.drop_table("async_jobs")
