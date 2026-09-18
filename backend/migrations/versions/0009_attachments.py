"""create attachments table

Revision ID: 0009_attachments
Revises: 0008_optical_measurements
Create Date: 2026-09-18 04:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_attachments"
down_revision: str | None = "0008_optical_measurements"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=255), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=255), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("caption", sa.String(length=255), nullable=True),
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
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')",
            name="chk_attachment_content_type",
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 20971520",
            name="chk_attachment_file_size",
        ),
    )

    op.create_index(
        "idx_attachments_entity",
        "attachments",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "idx_attachments_checksum",
        "attachments",
        ["checksum_sha256"],
    )


def downgrade() -> None:
    op.drop_index("idx_attachments_checksum", table_name="attachments")
    op.drop_index("idx_attachments_entity", table_name="attachments")
    op.drop_table("attachments")
