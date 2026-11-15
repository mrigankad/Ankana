"""privacy: field encryption keys, blind indexes, legal hold, privacy requests,
correction log, consent receipts, retention settings

Revision ID: 0004_privacy
Revises: 0003_ai_connections

Encrypts existing client email/phone, birth place labels and consultation note
bodies in place (needs ANKANA_MASTER_KEY unless API_ENV is dev/test and the
database has no practices).
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.privacy import backfill
from app.privacy.models import APPEND_ONLY_PRIVACY, PRIVACY_TABLES
from app.tenancy import rls

revision = "0004_privacy"
down_revision = "0004_notifications"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)
NOW = dict(server_default=sa.text("now()"), nullable=False)
PK = dict(server_default=sa.text("gen_random_uuid()"), nullable=False)

PRACTICES_FN = """
CREATE OR REPLACE FUNCTION privacy_practices()
RETURNS TABLE (practice_id uuid, retention_inactive_years int, retention_auto_apply boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public SET row_security = off AS $$
    SELECT p.id, s.retention_inactive_years, coalesce(s.retention_auto_apply, false)
    FROM practice p LEFT JOIN privacy_settings s ON s.practice_id = p.id
    WHERE p.deleted_at IS NULL
$$
"""


# Columns this revision encrypts; later revisions (0005) add their own.
_ENCRYPTED_AT_0004 = {
    ("client", "contact_email"), ("client", "contact_phone"), ("client", "legal_hold_reason"),
    ("birth_record", "place_label"), ("consultation_note", "body"),
    ("correction_log", "old_value"), ("correction_log", "new_value"),
    ("privacy_request", "reason"),
}


def _in(col: str, values) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "practice_key",
        sa.Column("id", sa.UUID(), primary_key=True, **PK),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("wrapped", sa.Text(), nullable=False),
        sa.Column("master_key_id", sa.String(512), nullable=False),
        sa.Column("status", sa.String(8), server_default="active", nullable=False),
        sa.Column("created_at", TZ, **NOW),
        sa.Column("retired_at", TZ),
        sa.ForeignKeyConstraint(["practice_id"], ["practice.id"], deferrable=True,
                                initially="DEFERRED"),
        sa.UniqueConstraint("practice_id", "kind", "version"),
        sa.CheckConstraint("kind IN ('dek','blind')", name="ck_practice_key_kind"),
        sa.CheckConstraint("status IN ('active','retired')", name="ck_practice_key_status"),
    )
    op.create_index("ix_practice_key_practice_id", "practice_key", ["practice_id"])

    op.create_table(
        "privacy_settings",
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), primary_key=True),
        sa.Column("retention_inactive_years", sa.Integer()),
        sa.Column("retention_auto_apply", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.Column("created_at", TZ, **NOW), sa.Column("updated_at", TZ, **NOW),
        sa.CheckConstraint("retention_inactive_years IS NULL OR "
                           "retention_inactive_years BETWEEN 1 AND 50",
                           name="ck_privacy_retention_years"),
    )

    kinds = ("client_export", "client_erase", "practice_export", "practice_delete",
             "retention_dry_run", "retention_apply")
    statuses = ("queued", "running", "done", "failed", "blocked")
    op.create_table(
        "privacy_request",
        sa.Column("id", sa.UUID(), primary_key=True, **PK),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("client_id", sa.UUID()),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(12), server_default="queued", nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("requested_by_member_id", sa.UUID()),
        sa.Column("job_id", sa.UUID()),
        sa.Column("result_key", sa.String(512)),
        sa.Column("result", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("completed_at", TZ),
        sa.Column("expires_at", TZ),
        sa.Column("created_at", TZ, **NOW), sa.Column("updated_at", TZ, **NOW),
        sa.UniqueConstraint("practice_id", "id"),
        sa.CheckConstraint(_in("kind", kinds), name="ck_privacy_request_kind"),
        sa.CheckConstraint(_in("status", statuses), name="ck_privacy_request_status"),
    )
    op.create_index("ix_privacy_request_practice_id", "privacy_request", ["practice_id"])
    op.create_index("ix_privacy_request_client", "privacy_request", ["practice_id", "client_id"])

    op.create_table(
        "correction_log",
        sa.Column("id", sa.UUID(), primary_key=True, **PK),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("reason", sa.String(500)),
        sa.Column("changed_by_member_id", sa.UUID()),
        sa.Column("created_at", TZ, **NOW),
        sa.ForeignKeyConstraint(["practice_id", "client_id"],
                                ["client.practice_id", "client.id"]),
    )
    op.create_index("ix_correction_log_practice_id", "correction_log", ["practice_id"])
    op.create_index("ix_correction_log_client", "correction_log",
                    ["practice_id", "client_id", "created_at"])

    op.create_table(
        "consent_receipt",
        sa.Column("id", sa.UUID(), primary_key=True, **PK),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("consent_id", sa.UUID(), nullable=False),
        sa.Column("event", sa.String(12), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("notice_version", sa.String(32), nullable=False),
        sa.Column("notice_language", sa.String(16)),
        sa.Column("notice_text_sha256", sa.String(64)),
        sa.Column("channel", sa.String(32)),
        sa.Column("collected_by_member_id", sa.UUID()),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("receipt_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["practice_id", "client_id"],
                                ["client.practice_id", "client.id"]),
        sa.CheckConstraint("event IN ('granted','withdrawn')", name="ck_consent_receipt_event"),
    )
    op.create_index("ix_consent_receipt_practice_id", "consent_receipt", ["practice_id"])
    op.create_index("ix_consent_receipt_client", "consent_receipt",
                    ["practice_id", "client_id", "occurred_at"])

    # Encrypted columns hold envelopes (longer than the plaintext limits).
    op.alter_column("client", "contact_email", type_=sa.Text(), existing_nullable=True)
    op.alter_column("client", "contact_phone", type_=sa.Text(), existing_nullable=True)
    op.alter_column("birth_record", "place_label", type_=sa.Text(), existing_nullable=False)
    op.add_column("client", sa.Column("contact_email_bidx", sa.String(64)))
    op.add_column("client", sa.Column("contact_phone_bidx", sa.String(64)))
    op.create_index("ix_client_contact_email_bidx", "client", ["contact_email_bidx"])
    op.create_index("ix_client_contact_phone_bidx", "client", ["contact_phone_bidx"])
    op.add_column("client", sa.Column("legal_hold", sa.Boolean(), server_default=sa.text("false"),
                                      nullable=False))
    op.add_column("client", sa.Column("legal_hold_reason", sa.Text()))
    op.add_column("client", sa.Column("legal_hold_at", TZ))

    for stmt in rls.enable_rls_sql(PRIVACY_TABLES, append_only=APPEND_ONLY_PRIVACY)[:-3]:
        op.execute(stmt)  # [:-3] drops the practice-root statements (already done in 0001)
    for table in PRIVACY_TABLES:
        verbs = ("SELECT, INSERT" if table in APPEND_ONLY_PRIVACY
                 else "SELECT, INSERT, UPDATE, DELETE")
        op.execute(f"GRANT {verbs} ON {table} TO {rls.APP_ROLE}")
    # Erasing a portal user removes their password hash (0003 granted no DELETE).
    op.execute(f"GRANT DELETE ON user_credential TO {rls.APP_ROLE}")
    op.execute(PRACTICES_FN)
    op.execute("REVOKE ALL ON FUNCTION privacy_practices() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION privacy_practices() TO {rls.APP_ROLE}")

    backfill.encrypt_existing(op.get_bind(), only=_ENCRYPTED_AT_0004)


def downgrade() -> None:
    backfill.decrypt_existing(op.get_bind(), only=_ENCRYPTED_AT_0004)
    op.execute(f"REVOKE DELETE ON user_credential FROM {rls.APP_ROLE}")
    op.execute("DROP FUNCTION IF EXISTS privacy_practices()")
    for table in ("consent_receipt", "correction_log", "privacy_request", "privacy_settings",
                  "practice_key"):
        op.drop_table(table)
    for col in ("legal_hold_at", "legal_hold_reason", "legal_hold"):
        op.drop_column("client", col)
    op.drop_index("ix_client_contact_phone_bidx", table_name="client")
    op.drop_index("ix_client_contact_email_bidx", table_name="client")
    op.drop_column("client", "contact_phone_bidx")
    op.drop_column("client", "contact_email_bidx")
    op.alter_column("birth_record", "place_label", type_=sa.String(300), existing_nullable=False)
    op.alter_column("client", "contact_phone", type_=sa.String(32), existing_nullable=True)
    op.alter_column("client", "contact_email", type_=sa.String(320), existing_nullable=True)
