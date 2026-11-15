"""erasure log: ids-only record of every erasure, replayed after a database restore

Revision ID: 0008_erasure_log
Revises: 0007_rate_limit

Append-only under RLS (SELECT and INSERT only). `privacy_erasure_events(since)` is a
SECURITY DEFINER read across practices for the operator CLI (replay-erasures, export-erasure-log);
it returns ids and timestamps only. Existing erasures are seeded from the `client.erased`
audit events so the log is complete from day one.
"""
import sqlalchemy as sa

from alembic import op
from app.tenancy import rls

revision = "0008_erasure_log"
down_revision = "0007_rate_limit"
branch_labels = None
depends_on = None

FN = """
CREATE OR REPLACE FUNCTION privacy_erasure_events(p_since timestamptz)
RETURNS TABLE (event_id uuid, kind text, practice_id uuid, client_id uuid, via text,
               erased_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp SET row_security = off AS $$
    SELECT l.event_id, l.kind, l.practice_id, l.client_id, l.via, l.erased_at
    FROM erasure_log l WHERE l.erased_at >= p_since ORDER BY l.erased_at
$$
"""


def upgrade() -> None:
    op.create_table(
        "erasure_log",
        sa.Column("event_id", sa.UUID(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID()),
        sa.Column("via", sa.String(32), nullable=False, server_default="request"),
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("kind IN ('client','practice')", name="ck_erasure_log_kind"),
    )
    op.create_index("ix_erasure_log_erased_at", "erasure_log", ["erased_at"])
    op.create_index("ix_erasure_log_practice_id", "erasure_log", ["practice_id"])
    for stmt in rls.enable_rls_sql(("erasure_log",), append_only=("erasure_log",))[:-3]:
        op.execute(stmt)  # [:-3] drops the practice-root statements (already done in 0001)
    op.execute(f"GRANT SELECT, INSERT ON erasure_log TO {rls.APP_ROLE}")
    op.execute(FN)
    op.execute("REVOKE ALL ON FUNCTION privacy_erasure_events(timestamptz) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION privacy_erasure_events(timestamptz) TO {rls.APP_ROLE}")
    # Seed from the audit trail. A throwaway SECURITY DEFINER function reads every practice
    # (FORCE RLS binds the owner too) so practices deleted since are covered as well.
    op.execute("""
        CREATE FUNCTION _seed_erasure_log() RETURNS void LANGUAGE sql SECURITY DEFINER
        SET search_path = public, pg_temp SET row_security = off AS $$
            INSERT INTO erasure_log (event_id, kind, practice_id, client_id, via, erased_at)
            SELECT gen_random_uuid(), 'client', a.practice_id, a.entity_id::uuid,
                   coalesce(a.meta->>'via', 'request'), a.created_at
            FROM audit_event a WHERE a.action = 'client.erased'
            UNION ALL
            SELECT gen_random_uuid(), 'practice', a.practice_id, NULL, 'request', a.created_at
            FROM audit_event a WHERE a.action = 'practice.deleted'
        $$
    """)
    op.execute("SELECT _seed_erasure_log()")
    op.execute("DROP FUNCTION _seed_erasure_log()")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS privacy_erasure_events(timestamptz)")
    op.drop_table("erasure_log")
