"""índice de splitters por terminal de entrada

Revision ID: 0013_splitters_input_idx
Revises: 0012_audit_events_append_only
Create Date: 2026-09-18 14:00:00.000000

PERF-02: o rastreio downstream localiza o splitter pelo terminal de entrada; sem índice a busca
varria splitters/splitter_outputs a cada salto. CONCURRENTLY (fora da transação da migração).
"""

from alembic import op

revision: str = "0013_splitters_input_idx"
down_revision: str | None = "0012_audit_events_append_only"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_splitters_input_terminal "
            "ON splitters (input_terminal_id)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_splitters_input_terminal")
