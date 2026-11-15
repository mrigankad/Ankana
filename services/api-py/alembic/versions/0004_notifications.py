"""remedy reminders: notification outbox, preferences, templates, missed-day state

Revision ID: 0004_notifications
Revises: 0003_ai_connections
"""
import sqlalchemy as sa

from alembic import op
from app.tenancy import rls

revision = "0004_notifications"
down_revision = "0003_billing"
branch_labels = None
depends_on = None

NOTIFY_TABLES = ("notification_pref", "notification_template", "notification")
OLD_PURPOSES = ("chart_compute", "ai_assistant", "report_sharing", "marketing")
NEW_PURPOSES = (*OLD_PURPOSES, "reminders")


def _check(values) -> str:
    return "purpose IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _ts(name):
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"),
                     nullable=False)


def _id():
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                     nullable=False)


def upgrade() -> None:
    op.drop_constraint("consent_purpose", "consent", type_="check")
    op.create_check_constraint("consent_purpose", "consent", _check(NEW_PURPOSES))

    op.add_column("practice", sa.Column("timezone", sa.String(64), server_default="Asia/Kolkata",
                                        nullable=False))
    op.add_column("practice", sa.Column("notify_hour", sa.SmallInteger(), server_default="8",
                                        nullable=False))
    op.add_column("practice", sa.Column("notify_enabled", sa.Boolean(),
                                        server_default=sa.text("true"), nullable=False))
    op.create_check_constraint("ck_practice_notify_hour", "practice",
                               "notify_hour BETWEEN 0 AND 23")
    op.add_column("consultation", sa.Column("follow_up_date", sa.Date(), nullable=True))
    for name in ("missed_days", "restart_count", "extended_days"):
        op.add_column("remedy_plan", sa.Column(name, sa.Integer(), server_default="0",
                                               nullable=False))
    op.add_column("remedy_plan", sa.Column("evaluated_through", sa.Date(), nullable=True))
    op.add_column("remedy_plan", sa.Column("last_missed_date", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_remedy_missed_policy", "remedy_plan",
        "missed_day_policy IN ('restart','extend','ignore','warn')")

    op.create_table(
        "notification_pref", _id(),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("email_opt_in", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("whatsapp_opt_in", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.Column("sms_opt_in", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("quiet_start", sa.Time(), server_default="21:00", nullable=False),
        sa.Column("quiet_end", sa.Time(), server_default="07:00", nullable=False),
        sa.Column("language", sa.String(8), nullable=True),
        _ts("created_at"), _ts("updated_at"),
        sa.CheckConstraint("language IN ('en','hi')", name="ck_notification_pref_language"),
        sa.ForeignKeyConstraint(["practice_id"], ["practice.id"]),
        sa.ForeignKeyConstraint(["practice_id", "client_id"],
                                ["client.practice_id", "client.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "client_id"),
    )
    op.create_table(
        "notification_template", _id(),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(16), server_default="*", nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("updated_by_member_id", sa.UUID(), nullable=True),
        _ts("created_at"), _ts("updated_at"),
        sa.CheckConstraint("language IN ('en','hi')", name="ck_notification_template_language"),
        sa.ForeignKeyConstraint(["practice_id"], ["practice.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "kind", "channel", "language"),
    )
    op.create_table(
        "notification", _id(),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("language", sa.String(8), server_default="en", nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("skip_reason", sa.String(64), nullable=True),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("resend_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        _ts("created_at"), _ts("updated_at"),
        sa.CheckConstraint("status IN ('pending','sent','failed','skipped','cancelled')",
                           name="ck_notification_status"),
        sa.CheckConstraint("channel IN ('email','whatsapp','sms')",
                           name="ck_notification_channel"),
        sa.ForeignKeyConstraint(["practice_id"], ["practice.id"]),
        sa.ForeignKeyConstraint(["practice_id", "client_id"],
                                ["client.practice_id", "client.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "dedupe_key", name="uq_notification_dedupe"),
    )
    op.create_index("ix_notification_practice_status", "notification",
                    ["practice_id", "status", "created_at"])
    op.create_index("ix_notification_client", "notification",
                    ["practice_id", "client_id", "created_at"])
    op.create_index("ix_notification_pref_practice", "notification_pref", ["practice_id"])
    op.create_index("ix_notification_template_practice", "notification_template",
                    ["practice_id"])

    for table in NOTIFY_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} "
                   f"USING (practice_id = {rls.CURRENT_PRACTICE}) "
                   f"WITH CHECK (practice_id = {rls.CURRENT_PRACTICE})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {rls.APP_ROLE}")

    # Cross-tenant listing for the scheduler tick (the app role is bound by RLS and
    # cannot enumerate practices). Returns only ids and schedule settings.
    op.execute(
        "CREATE OR REPLACE FUNCTION app_notify_practices() "
        "RETURNS TABLE (id uuid, timezone text, notify_hour int) "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public "
        "SET row_security = off AS $$ "
        "SELECT p.id, p.timezone::text, p.notify_hour::int FROM practice p "
        "WHERE p.deleted_at IS NULL AND p.notify_enabled $$")
    op.execute("REVOKE ALL ON FUNCTION app_notify_practices() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_notify_practices() TO {rls.APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_notify_practices()")
    op.drop_table("notification")
    op.drop_table("notification_template")
    op.drop_table("notification_pref")
    op.drop_constraint("ck_remedy_missed_policy", "remedy_plan", type_="check")
    for c in ("last_missed_date", "evaluated_through", "extended_days", "restart_count", "missed_days"):
        op.drop_column("remedy_plan", c)
    op.drop_column("consultation", "follow_up_date")
    op.drop_constraint("ck_practice_notify_hour", "practice", type_="check")
    for c in ("notify_enabled", "notify_hour", "timezone"):
        op.drop_column("practice", c)
    op.execute("DELETE FROM consent WHERE purpose = 'reminders'")
    op.drop_constraint("consent_purpose", "consent", type_="check")
    op.create_check_constraint("consent_purpose", "consent", _check(OLD_PURPOSES))
