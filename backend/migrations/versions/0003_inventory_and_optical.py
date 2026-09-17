"""create inventory sites structures devices ports and optical profiles

Revision ID: 0003_inventory_and_optical_tables
Revises: 0002_identity_tables
Create Date: 2026-09-17 17:35:00.000000

"""

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_inventory_and_optical"
down_revision: str | None = "0002_identity_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Tabela de Sites (POPs / Locais Técnicos)
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False, server_default="pop"),
        sa.Column(
            "location",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="installed"),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_sites_code", "sites", ["code"], unique=True)

    # 2. Tabela de Estruturas (Postes, CEOs, CTOs, Caixas, Pedestais)
    op.create_table(
        "structures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=False,
        ),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="installed"),
        sa.Column("condition", sa.String(length=50), nullable=False, server_default="ok"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_structures_code", "structures", ["code"], unique=True)
    op.create_index("ix_structures_site_id", "structures", ["site_id"])

    # 3. Tabela de Dispositivos (OLT, DIO, ONU, Switch)
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("manufacturer", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("structure_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="installed"),
        sa.Column("condition", sa.String(length=50), nullable=False, server_default="ok"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["structure_id"], ["structures.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "((site_id IS NOT NULL AND structure_id IS NULL) OR (site_id IS NULL AND structure_id IS NOT NULL))",
            name="chk_device_single_location",
        ),
    )
    op.create_index("ix_devices_code", "devices", ["code"], unique=True)
    op.create_index("ix_devices_site_id", "devices", ["site_id"])
    op.create_index("ix_devices_structure_id", "devices", ["structure_id"])

    # 4. Tabela de Portas (Portas de Dispositivos ou Estruturas)
    op.create_table(
        "ports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("structure_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "has_internal_pass_through", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("connector_type", sa.String(length=50), nullable=False, server_default="SC/APC"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["structure_id"], ["structures.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "((device_id IS NOT NULL AND structure_id IS NULL) OR (device_id IS NULL AND structure_id IS NOT NULL))",
            name="chk_port_single_owner",
        ),
    )
    op.create_index("ix_ports_device_id", "ports", ["device_id"])
    op.create_index("ix_ports_structure_id", "ports", ["structure_id"])
    op.create_index(
        "uq_ports_device_name",
        "ports",
        ["device_id", "name"],
        unique=True,
        postgresql_where=sa.text("device_id IS NOT NULL"),
    )
    op.create_index(
        "uq_ports_structure_name",
        "ports",
        ["structure_id", "name"],
        unique=True,
        postgresql_where=sa.text("structure_id IS NOT NULL"),
    )

    # 5. Tabela de Perfis Ópticos
    op.create_table(
        "optical_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("technology", sa.String(length=50), nullable=False, server_default="GPON"),
        sa.Column("wavelength_nm", sa.Integer(), nullable=False),
        sa.Column("tx_min_dbm", sa.Float(), nullable=False),
        sa.Column("tx_max_dbm", sa.Float(), nullable=False),
        sa.Column("rx_sensitivity_dbm", sa.Float(), nullable=False),
        sa.Column("rx_overload_dbm", sa.Float(), nullable=False),
        sa.Column(
            "default_attenuation_db_per_km",
            sa.Float(),
            nullable=False,
            server_default="0.35",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("tx_min_dbm <= tx_max_dbm", name="chk_optical_profile_tx"),
        sa.CheckConstraint("rx_sensitivity_dbm <= rx_overload_dbm", name="chk_optical_profile_rx"),
        sa.CheckConstraint(
            "wavelength_nm >= 800 AND wavelength_nm <= 2000",
            name="chk_optical_profile_wavelength",
        ),
        sa.CheckConstraint(
            "default_attenuation_db_per_km >= 0.0",
            name="chk_optical_profile_attenuation",
        ),
    )
    op.create_index("ix_optical_profiles_name", "optical_profiles", ["name"], unique=True)


def downgrade() -> None:
    op.drop_table("optical_profiles")
    op.drop_table("ports")
    op.drop_table("devices")
    op.drop_table("structures")
    op.drop_table("sites")
