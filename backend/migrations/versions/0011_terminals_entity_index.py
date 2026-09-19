"""índice de terminais por (entity_type, entity_id)

Revision ID: 0011_terminals_entity_index
Revises: 0010_async_jobs_and_imports
Create Date: 2026-09-18 12:00:00.000000

PERF-03: as consultas de ocupação/dashboard/CTO buscam terminais de portas por
(entity_type, entity_id); sem índice viravam seq scan. Criado com CONCURRENTLY (não bloqueia
escritas), por isso fora da transação da migração.
"""

from alembic import op

revision: str = "0011_terminals_entity_index"
down_revision: str | None = "0010_async_jobs_and_imports"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_terminals_entity "
            "ON terminals (entity_type, entity_id)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_terminals_entity")
