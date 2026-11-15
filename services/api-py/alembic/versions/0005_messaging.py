"""messaging: delivery receipts on the notification outbox, webhook lookup function

Revision ID: 0005_messaging
Revises: 0004_security_hardening
"""
import sqlalchemy as sa

from alembic import op
from app.tenancy import rls

revision = "0005_messaging"
down_revision = "0004_security_hardening"
branch_labels = None
depends_on = None

LOOKUP_FN = """
CREATE OR REPLACE FUNCTION app_notification_by_provider(p_provider text, p_message_id text)
RETURNS TABLE (practice_id uuid, id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp SET row_security = off AS $$
    SELECT n.practice_id, n.id FROM notification n
    WHERE n.provider = p_provider AND n.provider_message_id = p_message_id
    LIMIT 1
$$
"""


def upgrade() -> None:
    op.add_column("notification", sa.Column("delivery_status", sa.String(16), nullable=True))
    op.add_column("notification", sa.Column("delivered_at", sa.DateTime(timezone=True),
                                            nullable=True))
    op.add_column("notification", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification", sa.Column("delivery_error", sa.String(200), nullable=True))
    op.create_check_constraint(
        "ck_notification_delivery", "notification",
        "delivery_status IS NULL OR delivery_status IN ('sent','delivered','read','failed')")
    op.create_index("ix_notification_provider_msg", "notification",
                    ["provider", "provider_message_id"])
    op.execute(LOOKUP_FN)
    op.execute("REVOKE ALL ON FUNCTION app_notification_by_provider(text, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_notification_by_provider(text, text) "
               f"TO {rls.APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_notification_by_provider(text, text)")
    op.drop_index("ix_notification_provider_msg", table_name="notification")
    op.drop_constraint("ck_notification_delivery", "notification", type_="check")
    for c in ("delivery_error", "read_at", "delivered_at", "delivery_status"):
        op.drop_column("notification", c)
