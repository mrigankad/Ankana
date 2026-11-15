"""schema v1

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.tenancy import rls

# Frozen copy: later migrations add their own tables to RLS explicitly.
V1_TENANT_TABLES = (
    "member", "client", "consent", "birth_record", "chart_artifact",
    "consultation", "consultation_note", "remedy_plan", "remedy_item",
    "remedy_checkin", "report", "audit_event", "usage_counter",
)

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Non-superuser role the API connects as. Created NOLOGIN here when absent;
    # deployments run ALTER ROLE ... LOGIN PASSWORD (dev: docker/postgres-init).
    op.execute(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{rls.APP_ROLE}') "
        f"THEN CREATE ROLE {rls.APP_ROLE} NOLOGIN; END IF; END $$"
    )
    op.create_table('practice',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('gstin', sa.String(length=15), nullable=True),
    sa.Column('state', sa.String(length=64), nullable=True),
    sa.Column('plan', sa.String(length=32), server_default='trial', nullable=False),
    sa.Column('razorpay_customer_id', sa.String(length=64), nullable=True),
    sa.Column('razorpay_subscription_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_account',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('issuer', sa.String(length=255), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('display_name', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('issuer', 'subject')
    )
    op.create_table('audit_event',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('actor_member_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('request_id', sa.String(length=64), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_event_created_at'), 'audit_event', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_event_practice_id'), 'audit_event', ['practice_id'], unique=False)
    op.create_table('client',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('display_name', sa.String(length=200), nullable=False),
    sa.Column('contact_email', sa.String(length=320), nullable=True),
    sa.Column('contact_phone', sa.String(length=32), nullable=True),
    sa.Column('timezone', sa.String(length=64), nullable=True),
    sa.Column('preferred_language', sa.String(length=16), nullable=True),
    sa.Column('created_by_member_id', sa.UUID(), nullable=True),
    sa.Column('erased_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('practice_id', 'id')
    )
    op.create_index(op.f('ix_client_practice_id'), 'client', ['practice_id'], unique=False)
    op.create_table('member',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Enum('owner', 'astrologer', 'assistant', 'client', name='member_role', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['practice_id', 'client_id'], ['client.practice_id', 'client.id'], name='fk_member_client', use_alter=True),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('practice_id', 'id'),
    sa.UniqueConstraint('practice_id', 'user_id')
    )
    op.create_index(op.f('ix_member_practice_id'), 'member', ['practice_id'], unique=False)
    op.create_index(op.f('ix_member_user_id'), 'member', ['user_id'], unique=False)
    op.create_table('usage_counter',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('metric', sa.String(length=64), nullable=False),
    sa.Column('period', sa.Date(), nullable=False),
    sa.Column('value', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('practice_id', 'metric', 'period')
    )
    op.create_index(op.f('ix_usage_counter_practice_id'), 'usage_counter', ['practice_id'], unique=False)
    op.create_table('birth_record',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('supersedes_id', sa.UUID(), nullable=True),
    sa.Column('birth_date', sa.Date(), nullable=False),
    sa.Column('birth_time', sa.Time(), nullable=True),
    sa.Column('time_source', sa.Enum('certificate', 'memory', 'approximate', 'unknown', name='birth_time_source', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('place_label', sa.String(length=300), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('timezone_name', sa.String(length=64), nullable=False),
    sa.Column('tz_source', sa.String(length=32), nullable=True),
    sa.Column('rectification_status', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('latitude BETWEEN -90 AND 90', name='ck_birth_lat'),
    sa.CheckConstraint('longitude BETWEEN -180 AND 180', name='ck_birth_lon'),
    sa.ForeignKeyConstraint(['practice_id', 'client_id'], ['client.practice_id', 'client.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('client_id', 'version'),
    sa.UniqueConstraint('practice_id', 'id')
    )
    op.create_index(op.f('ix_birth_record_practice_id'), 'birth_record', ['practice_id'], unique=False)
    op.create_table('consent',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('purpose', sa.Enum('chart_processing', 'consultation_notes', 'ai_assistance', 'reminders', 'analytics', name='consent_purpose', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('notice_version', sa.String(length=32), nullable=False),
    sa.Column('notice_language', sa.String(length=16), nullable=True),
    sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('channel', sa.String(length=32), nullable=True),
    sa.Column('collected_by_member_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['practice_id', 'client_id'], ['client.practice_id', 'client.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_consent_client_purpose', 'consent', ['practice_id', 'client_id', 'purpose'], unique=False)
    op.create_index(op.f('ix_consent_practice_id'), 'consent', ['practice_id'], unique=False)
    op.create_table('chart_artifact',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('birth_record_id', sa.UUID(), nullable=False),
    sa.Column('settings_hash', sa.String(length=64), nullable=False),
    sa.Column('engine_version', sa.String(length=32), nullable=False),
    sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['practice_id', 'birth_record_id'], ['birth_record.practice_id', 'birth_record.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('birth_record_id', 'settings_hash', 'engine_version'),
    sa.UniqueConstraint('practice_id', 'id')
    )
    op.create_index(op.f('ix_chart_artifact_birth_record_id'), 'chart_artifact', ['birth_record_id'], unique=False)
    op.create_index(op.f('ix_chart_artifact_practice_id'), 'chart_artifact', ['practice_id'], unique=False)
    op.create_table('consultation',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('member_id', sa.UUID(), nullable=False),
    sa.Column('chart_artifact_id', sa.UUID(), nullable=True),
    sa.Column('consulted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('mode', sa.String(length=32), nullable=True),
    sa.Column('topic', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['practice_id', 'chart_artifact_id'], ['chart_artifact.practice_id', 'chart_artifact.id'], ),
    sa.ForeignKeyConstraint(['practice_id', 'client_id'], ['client.practice_id', 'client.id'], ),
    sa.ForeignKeyConstraint(['practice_id', 'member_id'], ['member.practice_id', 'member.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('practice_id', 'id')
    )
    op.create_index(op.f('ix_consultation_client_id'), 'consultation', ['client_id'], unique=False)
    op.create_index(op.f('ix_consultation_practice_id'), 'consultation', ['practice_id'], unique=False)
    op.create_table('report',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('chart_artifact_id', sa.UUID(), nullable=False),
    sa.Column('template_version', sa.String(length=32), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
    sa.Column('generated_by_member_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['practice_id', 'chart_artifact_id'], ['chart_artifact.practice_id', 'chart_artifact.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_chart_artifact_id'), 'report', ['chart_artifact_id'], unique=False)
    op.create_index(op.f('ix_report_practice_id'), 'report', ['practice_id'], unique=False)
    op.create_table('consultation_note',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('consultation_id', sa.UUID(), nullable=False),
    sa.Column('author_member_id', sa.UUID(), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['practice_id', 'consultation_id'], ['consultation.practice_id', 'consultation.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consultation_note_consultation_id'), 'consultation_note', ['consultation_id'], unique=False)
    op.create_index(op.f('ix_consultation_note_practice_id'), 'consultation_note', ['practice_id'], unique=False)
    op.create_table('remedy_plan',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('consultation_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('status', sa.Enum('draft', 'active', 'completed', 'cancelled', name='remedy_status', native_enum=False, create_constraint=True, length=32), server_default='draft', nullable=False),
    sa.Column('cycle_days', sa.Integer(), server_default='43', nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('missed_day_policy', sa.String(length=16), server_default='restart', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('cycle_days > 0', name='ck_remedy_cycle_positive'),
    sa.ForeignKeyConstraint(['practice_id', 'client_id'], ['client.practice_id', 'client.id'], ),
    sa.ForeignKeyConstraint(['practice_id', 'consultation_id'], ['consultation.practice_id', 'consultation.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('practice_id', 'id')
    )
    op.create_index(op.f('ix_remedy_plan_client_id'), 'remedy_plan', ['client_id'], unique=False)
    op.create_index(op.f('ix_remedy_plan_practice_id'), 'remedy_plan', ['practice_id'], unique=False)
    op.create_index('uq_remedy_plan_one_active', 'remedy_plan', ['practice_id', 'client_id'], unique=True, postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"))
    op.create_table('remedy_item',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('plan_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('instructions', sa.Text(), nullable=True),
    sa.Column('planet', sa.String(length=16), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['practice_id', 'plan_id'], ['remedy_plan.practice_id', 'remedy_plan.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('practice_id', 'id')
    )
    op.create_index(op.f('ix_remedy_item_plan_id'), 'remedy_item', ['plan_id'], unique=False)
    op.create_index(op.f('ix_remedy_item_practice_id'), 'remedy_item', ['practice_id'], unique=False)
    op.create_table('remedy_checkin',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('checkin_date', sa.Date(), nullable=False),
    sa.Column('done', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['practice_id', 'item_id'], ['remedy_item.practice_id', 'remedy_item.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practice.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id', 'checkin_date')
    )
    op.create_index(op.f('ix_remedy_checkin_item_id'), 'remedy_checkin', ['item_id'], unique=False)
    op.create_index(op.f('ix_remedy_checkin_practice_id'), 'remedy_checkin', ['practice_id'], unique=False)
    op.create_foreign_key(
        "fk_member_client", "member", "client",
        ["practice_id", "client_id"], ["practice_id", "id"],
    )

    for stmt in rls.enable_rls_sql(V1_TENANT_TABLES):
        op.execute(stmt)
    op.execute(rls.MEMBERSHIPS_FUNCTION_SQL)
    for stmt in rls.grants_sql(V1_TENANT_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    op.execute('DROP FUNCTION IF EXISTS app_memberships(uuid)')
    op.drop_constraint('fk_member_client', 'member', type_='foreignkey')
    op.drop_index(op.f('ix_remedy_checkin_practice_id'), table_name='remedy_checkin')
    op.drop_index(op.f('ix_remedy_checkin_item_id'), table_name='remedy_checkin')
    op.drop_table('remedy_checkin')
    op.drop_index(op.f('ix_remedy_item_practice_id'), table_name='remedy_item')
    op.drop_index(op.f('ix_remedy_item_plan_id'), table_name='remedy_item')
    op.drop_table('remedy_item')
    op.drop_index('uq_remedy_plan_one_active', table_name='remedy_plan', postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"))
    op.drop_index(op.f('ix_remedy_plan_practice_id'), table_name='remedy_plan')
    op.drop_index(op.f('ix_remedy_plan_client_id'), table_name='remedy_plan')
    op.drop_table('remedy_plan')
    op.drop_index(op.f('ix_consultation_note_practice_id'), table_name='consultation_note')
    op.drop_index(op.f('ix_consultation_note_consultation_id'), table_name='consultation_note')
    op.drop_table('consultation_note')
    op.drop_index(op.f('ix_report_practice_id'), table_name='report')
    op.drop_index(op.f('ix_report_chart_artifact_id'), table_name='report')
    op.drop_table('report')
    op.drop_index(op.f('ix_consultation_practice_id'), table_name='consultation')
    op.drop_index(op.f('ix_consultation_client_id'), table_name='consultation')
    op.drop_table('consultation')
    op.drop_index(op.f('ix_chart_artifact_practice_id'), table_name='chart_artifact')
    op.drop_index(op.f('ix_chart_artifact_birth_record_id'), table_name='chart_artifact')
    op.drop_table('chart_artifact')
    op.drop_index(op.f('ix_consent_practice_id'), table_name='consent')
    op.drop_index('ix_consent_client_purpose', table_name='consent')
    op.drop_table('consent')
    op.drop_index(op.f('ix_birth_record_practice_id'), table_name='birth_record')
    op.drop_table('birth_record')
    op.drop_index(op.f('ix_usage_counter_practice_id'), table_name='usage_counter')
    op.drop_table('usage_counter')
    op.drop_index(op.f('ix_member_user_id'), table_name='member')
    op.drop_index(op.f('ix_member_practice_id'), table_name='member')
    op.drop_table('member')
    op.drop_index(op.f('ix_client_practice_id'), table_name='client')
    op.drop_table('client')
    op.drop_index(op.f('ix_audit_event_practice_id'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_created_at'), table_name='audit_event')
    op.drop_table('audit_event')
    op.drop_table('user_account')
    op.drop_table('practice')
