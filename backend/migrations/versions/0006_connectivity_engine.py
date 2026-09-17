"""create connectivity engine tables and audit events

Revision ID: 0006_connectivity_engine
Revises: 0005_tubes_fibers_terminals
Create Date: 2026-09-17 18:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_connectivity_engine"
down_revision: str | None = "0005_tubes_fibers_terminals"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Expandir tabela terminals
    op.add_column(
        "terminals",
        sa.Column("occupancy", sa.String(length=20), nullable=False, server_default="free"),
    )
    op.add_column(
        "terminals",
        sa.Column("entity_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "terminals",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("idx_terminals_occupancy", "terminals", ["occupancy"])

    # 2. Expandir tabela connections
    op.add_column(
        "connections",
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
    )
    op.create_check_constraint(
        "chk_connection_location_defined",
        "connections",
        "structure_id IS NOT NULL OR site_id IS NOT NULL",
    )
    op.create_index("idx_connections_active", "connections", ["is_active"])

    # 3. Tabela connection_endpoints (controle e unicidade de conexão ativa por terminal)
    op.create_table(
        "connection_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connections.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "terminal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    )
    op.create_index(
        "uq_active_connection_endpoint",
        "connection_endpoints",
        ["terminal_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_conn_endpoints_conn_active",
        "connection_endpoints",
        ["connection_id", "is_active"],
    )

    # 4. Tabela terminal_reservations (reservas de terminais)
    op.create_table(
        "terminal_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "terminal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminals.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column(
            "reserved_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    )
    op.create_index(
        "uq_active_terminal_reservation",
        "terminal_reservations",
        ["terminal_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_term_reservations_term_active",
        "terminal_reservations",
        ["terminal_id", "is_active"],
    )

    # 5. Tabela internal_edges (arestas internas: continuidade de fibra, adaptador de porta, splitters)
    op.create_table(
        "internal_edges",
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
        sa.Column("edge_type", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("loss_db", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_bidirectional", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
            "terminal_a_id != terminal_b_id",
            name="chk_internal_edge_distinct_terminals",
        ),
        sa.CheckConstraint("loss_db >= 0.0", name="chk_internal_edge_loss_positive"),
    )
    op.create_index(
        "uq_internal_edge_terminals",
        "internal_edges",
        ["terminal_a_id", "terminal_b_id"],
        unique=True,
    )

    # 6. Tabela audit_events (auditoria append-only)
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("actor_name", sa.String(length=150), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )
    op.create_index("idx_audit_events_entity", "audit_events", ["entity_type", "entity_id"])

    # 7. Backfill de integridade para dados existentes
    op.execute(
        """
        UPDATE terminals SET occupancy = 'connected' WHERE is_occupied = true;
        """
    )
    op.execute(
        """
        INSERT INTO connection_endpoints (id, connection_id, terminal_id, is_active, version, created_at, updated_at)
        SELECT gen_random_uuid(), id, terminal_a_id, is_active, 1, created_at, updated_at FROM connections;
        """
    )
    op.execute(
        """
        INSERT INTO connection_endpoints (id, connection_id, terminal_id, is_active, version, created_at, updated_at)
        SELECT gen_random_uuid(), id, terminal_b_id, is_active, 1, created_at, updated_at FROM connections;
        """
    )
    op.execute(
        """
        INSERT INTO internal_edges (id, terminal_a_id, terminal_b_id, edge_type, entity_type, entity_id, loss_db, is_bidirectional, version, created_at, updated_at)
        SELECT gen_random_uuid(), terminal_a_id, terminal_b_id, 'fiber_continuity', 'fiber_segment', id, 0.0, true, 1, created_at, updated_at
        FROM fiber_segments;
        """
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("internal_edges")
    op.drop_table("terminal_reservations")
    op.drop_table("connection_endpoints")

    op.drop_index("idx_connections_active", table_name="connections")
    op.drop_constraint("chk_connection_location_defined", "connections", type_="check")
    op.drop_column("connections", "site_id")

    op.drop_index("idx_terminals_occupancy", table_name="terminals")
    op.drop_column("terminals", "entity_id")
    op.drop_column("terminals", "entity_type")
    op.drop_column("terminals", "occupancy")
