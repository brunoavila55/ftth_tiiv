"""índices de retenção e de rate limit de login

Revision ID: 0015_retention_indexes
Revises: 0014_search_and_list_indexes
Create Date: 2026-09-19 13:00:00.000000

PERF-11: o rate limit de login consulta `login_attempts` por (e-mail | IP) numa janela de tempo e
a rotina de retenção varre `attempted_at`/`expires_at`/`last_activity_at`; sem índices compostos
isso vira seq scan conforme a tabela cresce. CREATE INDEX CONCURRENTLY.
"""

from alembic import op

revision: str = "0015_retention_indexes"
down_revision: str | None = "0014_search_and_list_indexes"
branch_labels: str | None = None
depends_on: str | None = None

INDEXES = [
    ("idx_login_attempts_email_attempted", "login_attempts", "email, attempted_at"),
    ("idx_login_attempts_ip_attempted", "login_attempts", "ip_address, attempted_at"),
    ("idx_user_sessions_expires_at", "user_sessions", "expires_at"),
    ("idx_user_sessions_last_activity", "user_sessions", "last_activity_at"),
]


# Índices simples que os compostos acima tornam redundantes (a coluna é a primeira do composto):
# menos índices para manter numa tabela de escrita intensa.
REDUNDANT = [
    ("ix_login_attempts_email", "login_attempts", "email"),
    ("ix_login_attempts_ip_address", "login_attempts", "ip_address"),
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, columns in INDEXES:
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} ({columns})")
        for name, _table, _columns in REDUNDANT:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, columns in REDUNDANT:
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} ({columns})")
        for name, _table, _columns in reversed(INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
