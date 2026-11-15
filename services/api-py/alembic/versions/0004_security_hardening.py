"""pin search_path (pg_temp last) on the SECURITY DEFINER functions

Revision ID: 0004_security_hardening
Revises: 0004_privacy
"""
from alembic import op
from app.auth import sql as auth_sql
from app.tenancy import rls

revision = "0004_security_hardening"
down_revision = "0004_privacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CREATE OR REPLACE keeps the existing grants; the sources now say "public, pg_temp".
    op.execute(rls.MEMBERSHIPS_FUNCTION_SQL)
    op.execute(auth_sql.INVITE_LOOKUP_FUNCTION_SQL)
    # Later SECURITY DEFINER functions (billing, notifications, privacy) get the same pin.
    for fn in ("billing_find_practice(text, text)", "app_notify_practices()",
               "privacy_practices()"):
        op.execute(f"ALTER FUNCTION {fn} SET search_path = public, pg_temp")


def downgrade() -> None:
    # Hardening is not rolled back: the previous definitions were strictly weaker.
    pass
