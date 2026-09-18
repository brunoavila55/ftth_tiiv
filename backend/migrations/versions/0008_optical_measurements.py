"""create optical_measurements table

Revision ID: 0008_optical_measurements
Revises: 0007_customers_and_services
Create Date: 2026-09-18 03:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_optical_measurements"
down_revision: str | None = "0007_customers_and_services"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "optical_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "terminal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "service_link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_links.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("power_dbm", sa.Float(), nullable=False),
        sa.Column("wavelength_nm", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False, server_default="downstream"),
        sa.Column("origin", sa.String(length=50), nullable=False, server_default="manual_entry"),
        sa.Column("instrument_model", sa.String(length=100), nullable=True),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("predicted_power_dbm", sa.Float(), nullable=True),
        sa.Column("excess_loss_db", sa.Float(), nullable=True),
        sa.Column("topology_revision", sa.Integer(), nullable=True),
        sa.Column("calculation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "wavelength_nm >= 800 AND wavelength_nm <= 2000",
            name="chk_optical_measurement_wavelength",
        ),
        sa.CheckConstraint(
            "direction IN ('downstream', 'upstream')",
            name="chk_optical_measurement_direction",
        ),
        sa.CheckConstraint(
            "origin IN ('manual_entry', 'field_power_meter', 'otdr')",
            name="chk_optical_measurement_origin",
        ),
    )
    op.create_index(
        "ix_optical_measurements_terminal_measured",
        "optical_measurements",
        ["terminal_id", "measured_at"],
    )
    op.create_index(
        "ix_optical_measurements_service_link",
        "optical_measurements",
        ["service_link_id"],
    )


def downgrade() -> None:
    op.drop_table("optical_measurements")
