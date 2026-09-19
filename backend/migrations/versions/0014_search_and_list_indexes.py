"""índices trigram (busca ILIKE) e de listagem (created_at DESC, id)

Revision ID: 0014_search_and_list_indexes
Revises: 0013_splitters_input_idx
Create Date: 2026-09-19 12:00:00.000000

PERF-06: buscas `ILIKE '%termo%'` varriam a tabela inteira; índices GIN com `gin_trgm_ops` (pg_trgm)
as atendem. PERF-07: as listagens ordenam por `created_at DESC, id` e paginam com OFFSET; o índice
composto evita ordenar a tabela toda a cada página. Tudo com CREATE INDEX CONCURRENTLY.
"""

from alembic import op

revision: str = "0014_search_and_list_indexes"
down_revision: str | None = "0013_splitters_input_idx"
branch_labels: str | None = None
depends_on: str | None = None

# (tabela, coluna) → índice GIN trigram
TRIGRAM_INDEXES = [
    ("sites", "code"),
    ("sites", "name"),
    ("structures", "code"),
    ("cables", "code"),
    ("cables", "model"),
    ("devices", "code"),
    ("devices", "manufacturer"),
    ("devices", "model"),
    ("devices", "serial_number"),
    ("customers", "code"),
    ("customers", "name"),
    ("customers", "phone"),
    ("customers", "email"),
    ("users", "name"),
    ("users", "email"),
    ("ports", "notes"),
]

# tabelas listadas por `ORDER BY created_at DESC, id`
LIST_INDEX_TABLES = ["sites", "structures", "devices", "ports", "users", "optical_profiles"]
# listadas só por `ORDER BY created_at DESC`
LIST_INDEX_TABLES_DESC_ONLY = ["connections", "attachments"]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        for table, column in TRIGRAM_INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{table}_{column}_trgm "
                f"ON {table} USING gin ({column} gin_trgm_ops)"
            )
        for table in LIST_INDEX_TABLES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{table}_created_desc_id "
                f"ON {table} (created_at DESC, id)"
            )
        for table in LIST_INDEX_TABLES_DESC_ONLY:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{table}_created_desc "
                f"ON {table} (created_at DESC)"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for table in LIST_INDEX_TABLES_DESC_ONLY:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS idx_{table}_created_desc")
        for table in LIST_INDEX_TABLES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS idx_{table}_created_desc_id")
        for table, column in reversed(TRIGRAM_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS idx_{table}_{column}_trgm")
    # a extensão pg_trgm é mantida (outros objetos podem depender dela)
