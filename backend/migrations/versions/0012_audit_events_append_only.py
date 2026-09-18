"""audit_events append-only no banco

Revision ID: 0012_audit_events_append_only
Revises: 0011_terminals_entity_index
Create Date: 2026-09-18 13:00:00.000000

SEC-17: a trilha de auditoria só aceita INSERT. Um trigger por linha bloqueia UPDATE e DELETE
(mesmo para o usuário da aplicação). TRUNCATE não é bloqueado (é operação de administração de
banco; os testes de integração o usam para limpar o ambiente).
"""

from alembic import op

revision: str = "0012_audit_events_append_only"
down_revision: str | None = "0011_terminals_entity_index"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events é append-only: % bloqueado', TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_append_only()")
