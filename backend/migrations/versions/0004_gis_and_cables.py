"""create network topology state, cables and cable segments with PostGIS linestring geometries

Revision ID: 0004_gis_and_cables
Revises: 0003_inventory_and_optical
Create Date: 2026-09-17 17:46:00.000000

"""

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_gis_and_cables"
down_revision: str | None = "0003_inventory_and_optical"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Tabela de Estado Monotônico da Topologia
    topology_table = op.create_table(
        "network_topology_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("topology_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Inicializa a revisão topológica global em 1
    op.bulk_insert(
        topology_table,
        [
            {"id": 1, "topology_revision": 1},
        ],
    )

    # 2. Tabela de Cabos Ópticos
    op.create_table(
        "cables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("fiber_count", sa.Integer(), nullable=False),
        sa.Column("tube_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("color_standard", sa.String(length=50), nullable=False, server_default="NBR"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="installed"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_cables_code", "cables", ["code"], unique=True)

    # 3. Tabela de Trechos de Cabo (Cable Segments)
    op.create_table(
        "cable_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cable_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cables.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "origin_structure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("structures.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "destination_structure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("structures.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "geometry",
            geoalchemy2.Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
            nullable=False,
        ),
        sa.Column("map_length_m", sa.Float(), nullable=False),
        sa.Column("measured_length_m", sa.Float(), nullable=True),
        sa.Column("slack_length_m", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("effective_length_m", sa.Float(), nullable=False),
        sa.Column(
            "length_source", sa.String(length=20), nullable=False, server_default="calculated"
        ),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="installed"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("slack_length_m >= 0", name="chk_cable_segment_slack_positive"),
        sa.CheckConstraint(
            "measured_length_m IS NULL OR measured_length_m >= 0",
            name="chk_cable_segment_measured_positive",
        ),
        sa.CheckConstraint("map_length_m >= 0", name="chk_cable_segment_map_positive"),
        sa.CheckConstraint(
            "origin_structure_id != destination_structure_id",
            name="chk_cable_segment_different_structures",
        ),
    )
    op.create_index(
        "idx_cable_segments_origin_dest",
        "cable_segments",
        ["origin_structure_id", "destination_structure_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_cable_segments_origin_dest", table_name="cable_segments")
    op.drop_table("cable_segments")
    op.drop_index("ix_cables_code", table_name="cables")
    op.drop_table("cables")
    op.drop_table("network_topology_state")
