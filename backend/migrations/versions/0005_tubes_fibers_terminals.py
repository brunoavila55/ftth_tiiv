"""create tubes fibers terminals fiber_segments and connections

Revision ID: 0005_tubes_fibers_terminals
Revises: 0004_gis_and_cables
Create Date: 2026-09-17 17:53:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_tubes_fibers_terminals"
down_revision: str | None = "0004_gis_and_cables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Tabela de Terminais Ópticos (Terminals)
    op.create_table(
        "terminals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
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
        sa.Column("label", sa.String(length=150), nullable=False),
        sa.Column("is_occupied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "structure_id IS NOT NULL OR site_id IS NOT NULL",
            name="chk_terminal_location_defined",
        ),
    )
    op.create_index("idx_terminals_kind_structure", "terminals", ["kind", "structure_id"])

    # 2. Tabela de Tubos Loose (Tubes)
    op.create_table(
        "tubes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cable_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cables.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("color_name", sa.String(length=50), nullable=False),
        sa.Column(
            "is_logical_group", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("cable_id", "number", name="uq_tubes_cable_number"),
        sa.CheckConstraint("number >= 1", name="chk_tube_number_positive"),
    )

    # 3. Tabela de Fibras (Fibers)
    op.create_table(
        "fibers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cable_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cables.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tube_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tubes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("global_number", sa.Integer(), nullable=False),
        sa.Column("tube_position", sa.Integer(), nullable=False),
        sa.Column("color_name", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="installed"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("cable_id", "global_number", name="uq_fibers_cable_global_number"),
        sa.CheckConstraint("global_number >= 1", name="chk_fiber_global_number_positive"),
        sa.CheckConstraint("tube_position >= 1", name="chk_fiber_tube_position_positive"),
    )

    # 4. Tabela de Segmentos de Fibra (Fiber Segments)
    op.create_table(
        "fiber_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cable_segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cable_segments.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "fiber_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fibers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("fiber_number", sa.Integer(), nullable=False),
        sa.Column(
            "terminal_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "terminal_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("occupancy", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("cable_segment_id", "fiber_id", name="uq_fiber_segments_seg_fiber"),
        sa.UniqueConstraint(
            "cable_segment_id", "terminal_a_id", name="uq_fiber_segments_seg_term_a"
        ),
        sa.UniqueConstraint(
            "cable_segment_id", "terminal_b_id", name="uq_fiber_segments_seg_term_b"
        ),
        sa.CheckConstraint(
            "terminal_a_id != terminal_b_id",
            name="chk_fiber_segment_different_terminals",
        ),
    )

    # 5. Tabela de Conexões (Connections)
    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "terminal_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "terminal_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("connection_type", sa.String(length=50), nullable=False),
        sa.Column("loss_db", sa.Float(), nullable=False, server_default="0.10"),
        sa.Column(
            "structure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("structures.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "terminal_a_id != terminal_b_id",
            name="chk_connection_distinct_terminals",
        ),
        sa.CheckConstraint("loss_db >= 0.0", name="chk_connection_loss_positive"),
    )
    op.create_index("idx_connections_term_a_b", "connections", ["terminal_a_id", "terminal_b_id"])


def downgrade() -> None:
    op.drop_index("idx_connections_term_a_b", table_name="connections")
    op.drop_table("connections")
    op.drop_table("fiber_segments")
    op.drop_table("fibers")
    op.drop_table("tubes")
    op.drop_index("idx_terminals_kind_structure", table_name="terminals")
    op.drop_table("terminals")
