"""completa CRUD de splitters e configurações persistidas

Revision ID: 0016_splitter_crud_settings
Revises: 0015_retention_indexes
Create Date: 2026-09-20 18:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_splitter_crud_settings"
down_revision: str | None = "0015_retention_indexes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "splitters",
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_splitters_device_id", "splitters", ["device_id"])
    op.create_index("uq_splitters_code", "splitters", ["code"], unique=True)

    for column in ("loss_1310_db", "loss_1490_db", "loss_1550_db"):
        op.add_column("splitter_outputs", sa.Column(column, sa.Float(), nullable=True))
    op.execute(
        "UPDATE splitter_outputs SET loss_1310_db = nominal_loss_db, loss_1490_db = nominal_loss_db"
    )
    op.create_check_constraint(
        "chk_splitter_output_loss_1310_positive",
        "splitter_outputs",
        "loss_1310_db IS NULL OR loss_1310_db >= 0.0",
    )
    op.create_check_constraint(
        "chk_splitter_output_loss_1490_positive",
        "splitter_outputs",
        "loss_1490_db IS NULL OR loss_1490_db >= 0.0",
    )
    op.create_check_constraint(
        "chk_splitter_output_loss_1550_positive",
        "splitter_outputs",
        "loss_1550_db IS NULL OR loss_1550_db >= 0.0",
    )

    op.create_table(
        "app_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_name", sa.String(length=150), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("default_map_longitude", sa.Float(), nullable=False),
        sa.Column("default_map_latitude", sa.Float(), nullable=False),
        sa.Column("default_map_zoom", sa.Integer(), nullable=False),
        sa.Column("excess_loss_tolerance_db", sa.Float(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "default_map_longitude BETWEEN -180 AND 180",
            name="chk_app_settings_longitude",
        ),
        sa.CheckConstraint(
            "default_map_latitude BETWEEN -90 AND 90",
            name="chk_app_settings_latitude",
        ),
        sa.CheckConstraint(
            "default_map_zoom BETWEEN 1 AND 22",
            name="chk_app_settings_zoom",
        ),
        sa.CheckConstraint(
            "excess_loss_tolerance_db BETWEEN 0.1 AND 10.0",
            name="chk_app_settings_excess_loss",
        ),
    )
    op.execute(
        "INSERT INTO app_settings "
        "(id, organization_name, timezone, default_map_longitude, default_map_latitude, "
        "default_map_zoom, excess_loss_tolerance_db, version) VALUES "
        "('00000000-0000-0000-0000-000000000001', 'Operação FTTH', "
        "'America/Sao_Paulo', -46.633308, -23.550520, 14, 2.0, 1)"
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_constraint("chk_splitter_output_loss_1550_positive", "splitter_outputs", type_="check")
    op.drop_constraint("chk_splitter_output_loss_1490_positive", "splitter_outputs", type_="check")
    op.drop_constraint("chk_splitter_output_loss_1310_positive", "splitter_outputs", type_="check")
    op.drop_column("splitter_outputs", "loss_1550_db")
    op.drop_column("splitter_outputs", "loss_1490_db")
    op.drop_column("splitter_outputs", "loss_1310_db")
    op.drop_index("uq_splitters_code", table_name="splitters")
    op.drop_index("ix_splitters_device_id", table_name="splitters")
    op.drop_column("splitters", "device_id")
