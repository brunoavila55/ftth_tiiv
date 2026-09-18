"""create customers, splitters and service_links tables

Revision ID: 0007_customers_splitters_service_links
Revises: 0006_connectivity_engine
Create Date: 2026-09-18 01:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_customers_and_services"
down_revision: str | None = "0006_connectivity_engine"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Tabela customers
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_customers_code", "customers", ["code"], unique=True)

    # 2. Tabela splitters
    op.create_table(
        "splitters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "structure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("structures.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("splitter_type", sa.String(length=50), nullable=False, server_default="balanced"),
        sa.Column("ratio", sa.String(length=20), nullable=False, server_default="1:8"),
        sa.Column(
            "input_terminal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "chk_splitter_location_defined",
        "splitters",
        "structure_id IS NOT NULL OR site_id IS NOT NULL",
    )
    op.create_index("idx_splitters_structure", "splitters", ["structure_id"])

    # 3. Tabela splitter_outputs
    op.create_table(
        "splitter_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "splitter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("splitters.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("output_number", sa.Integer(), nullable=False),
        sa.Column(
            "terminal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("nominal_loss_db", sa.Float(), nullable=False, server_default="10.5"),
        sa.Column("measured_loss_db", sa.Float(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "chk_splitter_output_nominal_loss_positive",
        "splitter_outputs",
        "nominal_loss_db >= 0.0",
    )
    op.create_index("uq_splitter_outputs_num", "splitter_outputs", ["splitter_id", "output_number"], unique=True)

    # 4. Tabela service_links
    op.create_table(
        "service_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "onu_device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "port_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ports.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_active_port_service_link",
        "service_links",
        ["port_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_active_onu_service_link",
        "service_links",
        ["onu_device_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("idx_service_links_customer_status", "service_links", ["customer_id", "status"])


def downgrade() -> None:
    op.drop_table("service_links")
    op.drop_table("splitter_outputs")
    op.drop_table("splitters")
    op.drop_table("customers")
