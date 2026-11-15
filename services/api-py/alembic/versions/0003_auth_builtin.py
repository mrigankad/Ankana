"""built-in authentication: credentials, identities, one-time codes, sessions, invites

Revision ID: 0003_auth_builtin
Revises: 0002_reports_jobs
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.auth import sql as auth_sql
from app.tenancy import rls

revision = "0003_auth_builtin"
down_revision = "0002_reports_jobs"
branch_labels = None
depends_on = None

UUID_PK = dict(server_default=sa.text("gen_random_uuid()"), nullable=False)
NOW = dict(server_default=sa.text("now()"), nullable=False)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    # One built-in account per email (the OIDC/stub issuers keep their own rows).
    op.execute("CREATE UNIQUE INDEX uq_user_account_builtin_email ON user_account "
               "(lower(email)) WHERE issuer = 'ankana' AND deleted_at IS NULL")
    op.execute("CREATE UNIQUE INDEX uq_user_account_builtin_phone ON user_account "
               "(phone) WHERE issuer = 'ankana' AND deleted_at IS NULL AND phone IS NOT NULL")

    op.create_table(
        "user_credential",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("user_account.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", TZ, **NOW), sa.Column("updated_at", TZ, **NOW),
    )
    op.create_table(
        "auth_identity",
        sa.Column("id", sa.UUID(), primary_key=True, **UUID_PK),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("user_account.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("created_at", TZ, **NOW), sa.Column("updated_at", TZ, **NOW),
        sa.UniqueConstraint("provider", "subject"),
    )
    op.create_index("ix_auth_identity_user_id", "auth_identity", ["user_id"])
    op.create_table(
        "auth_otp",
        sa.Column("id", sa.UUID(), primary_key=True, **UUID_PK),
        sa.Column("created_at", TZ, **NOW),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("destination", sa.String(320), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_at", TZ),
        sa.Column("meta", postgresql.JSONB()),
        sa.CheckConstraint("channel IN ('email', 'phone')", name="auth_otp_channel"),
        sa.CheckConstraint("purpose IN ('signin', 'signup')", name="auth_otp_purpose"),
    )
    op.create_index("ix_auth_otp_destination", "auth_otp", ["destination"])
    op.create_table(
        "auth_session",
        sa.Column("id", sa.UUID(), primary_key=True, **UUID_PK),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("user_account.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("refresh_hash", sa.String(64), nullable=False),
        sa.Column("prev_refresh_hash", sa.String(64)),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("practice_id", sa.UUID()),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
        sa.Column("last_used_at", TZ, **NOW),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("absolute_expires_at", TZ, nullable=False),
        sa.Column("revoked_at", TZ),
        sa.Column("revoked_reason", sa.String(32)),
        sa.Column("created_at", TZ, **NOW), sa.Column("updated_at", TZ, **NOW),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])
    op.create_table(
        "auth_oidc_state",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("redirect_to", sa.String(500)),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("created_at", TZ, **NOW),
    )
    op.create_table(
        "auth_event",
        sa.Column("id", sa.UUID(), primary_key=True, **UUID_PK),
        sa.Column("created_at", TZ, **NOW),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("user_id", sa.UUID()),
        sa.Column("subject_hash", sa.String(64)),
        sa.Column("ip", sa.String(64)),
        sa.Column("meta", postgresql.JSONB()),
    )
    op.create_index("ix_auth_event_user_id", "auth_event", ["user_id"])
    op.create_index("ix_auth_event_action_subject", "auth_event",
                    ["action", "subject_hash", "created_at"])
    op.create_index("ix_auth_event_action_ip", "auth_event", ["action", "ip", "created_at"])

    # Tenant-scoped: invitations belong to a practice.
    op.create_table(
        "practice_invite",
        sa.Column("id", sa.UUID(), primary_key=True, **UUID_PK),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("client_id", sa.UUID()),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by_member_id", sa.UUID()),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("accepted_at", TZ),
        sa.Column("revoked_at", TZ),
        sa.Column("created_at", TZ, **NOW), sa.Column("updated_at", TZ, **NOW),
        sa.CheckConstraint("role IN ('owner', 'astrologer', 'assistant', 'client')",
                           name="invite_role"),
        sa.ForeignKeyConstraint(["practice_id", "client_id"], ["client.practice_id", "client.id"],
                                name="fk_invite_client"),
    )
    op.create_index("ix_practice_invite_practice_id", "practice_invite", ["practice_id"])
    for stmt in (
        "ALTER TABLE practice_invite ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE practice_invite FORCE ROW LEVEL SECURITY",
        "CREATE POLICY tenant_isolation ON practice_invite "
        f"USING (practice_id = {rls.CURRENT_PRACTICE}) "
        f"WITH CHECK (practice_id = {rls.CURRENT_PRACTICE})",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON practice_invite TO {rls.APP_ROLE}",
        auth_sql.INVITE_LOOKUP_FUNCTION_SQL,
        *auth_sql.grants_sql(),
    ):
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_invite_lookup(text)")
    for table in ("practice_invite", "auth_event", "auth_oidc_state", "auth_session", "auth_otp",
                  "auth_identity", "user_credential"):
        op.drop_table(table)
    op.execute("DROP INDEX IF EXISTS uq_user_account_builtin_phone")
    op.execute("DROP INDEX IF EXISTS uq_user_account_builtin_email")
