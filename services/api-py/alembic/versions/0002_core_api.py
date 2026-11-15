"""core practice API: consent purposes, notice text, idempotency keys

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.tenancy import rls

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

NEW_PURPOSES = ('chart_compute', 'ai_assistant', 'report_sharing', 'marketing')
OLD_PURPOSES = ('chart_processing', 'consultation_notes', 'ai_assistance', 'reminders', 'analytics')
REMAP = {
    'chart_processing': 'chart_compute', 'consultation_notes': 'chart_compute',
    'ai_assistance': 'ai_assistant', 'reminders': 'marketing', 'analytics': 'marketing',
}


def _check(values) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"purpose IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint('consent_purpose', 'consent', type_='check')
    for old, new in REMAP.items():
        op.execute(f"UPDATE consent SET purpose = '{new}' WHERE purpose = '{old}'")
    op.create_check_constraint('consent_purpose', 'consent', _check(NEW_PURPOSES))
    op.add_column('consent', sa.Column('notice_text', sa.Text(), nullable=True))

    op.create_table('idempotency_key',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('practice_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('endpoint', sa.String(length=128), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['practice_id'], ['practice.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('practice_id', 'endpoint', 'key'),
    )
    op.create_index(op.f('ix_idempotency_key_practice_id'), 'idempotency_key', ['practice_id'])
    for stmt in (
        "ALTER TABLE idempotency_key ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE idempotency_key FORCE ROW LEVEL SECURITY",
        "CREATE POLICY tenant_isolation ON idempotency_key "
        f"USING (practice_id = {rls.CURRENT_PRACTICE}) "
        f"WITH CHECK (practice_id = {rls.CURRENT_PRACTICE})",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON idempotency_key TO {rls.APP_ROLE}",
    ):
        op.execute(stmt)


# Lossy on purpose: several old purposes collapsed into one new one on the way up.
UNMAP = {'chart_compute': 'chart_processing', 'ai_assistant': 'ai_assistance',
         'report_sharing': 'chart_processing', 'marketing': 'reminders'}


def downgrade() -> None:
    op.drop_table('idempotency_key')
    op.drop_column('consent', 'notice_text')
    op.drop_constraint('consent_purpose', 'consent', type_='check')
    for new, old in UNMAP.items():  # rows must satisfy the old CHECK before it is re-created
        op.execute(f"UPDATE consent SET purpose = '{old}' WHERE purpose = '{new}'")
    op.create_check_constraint('consent_purpose', 'consent', _check(OLD_PURPOSES))
