"""billing: subscription, invoice, invoice_line, webhook ledger, invoice series

Revision ID: 0003_billing
Revises: 0003_ai_connections
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.tenancy import rls

revision = "0003_billing"
down_revision = "0003_ai_connections"
branch_labels = None
depends_on = None

TENANT = ("subscription", "invoice", "invoice_line")

# Webhooks arrive without a practice. This resolves one from a provider id,
# bypassing RLS for exactly this lookup (same pattern as app_memberships).
FIND_PRACTICE_FN = """
CREATE OR REPLACE FUNCTION billing_find_practice(p_subscription_id text, p_customer_id text)
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public SET row_security = off AS $$
    SELECT practice_id FROM (
        SELECT s.practice_id, 1 AS rank FROM subscription s
        WHERE p_subscription_id IS NOT NULL AND s.provider_subscription_id = p_subscription_id
        UNION ALL
        SELECT s.practice_id, 2 FROM subscription s
        WHERE p_customer_id IS NOT NULL AND s.provider_customer_id = p_customer_id
    ) q ORDER BY rank LIMIT 1
$$
"""


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    ]


def _id():
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.add_column("practice", sa.Column("billing_legal_name", sa.String(200), nullable=True))
    op.add_column("practice", sa.Column("billing_state_code", sa.String(2), nullable=True))
    op.add_column("practice", sa.Column("billing_address", sa.Text(), nullable=True))

    op.create_table(
        "subscription", _id(),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("plan_key", sa.String(32), nullable=False),
        sa.Column("interval", sa.String(8), server_default="month", nullable=False),
        sa.Column("status", sa.String(16), server_default="created", nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("provider_customer_id", sa.String(64)),
        sa.Column("provider_subscription_id", sa.String(64), nullable=False),
        sa.Column("checkout_url", sa.Text()),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("status IN ('created','active','past_due','halted','cancelled')",
                           name="ck_subscription_status"),
        sa.CheckConstraint("interval IN ('month','year')", name="ck_subscription_interval"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "id"),
    )
    op.create_index("ix_subscription_practice_id", "subscription", ["practice_id"])
    op.create_index("uq_subscription_provider_id", "subscription",
                    ["provider", "provider_subscription_id"], unique=True)

    op.create_table(
        "invoice", _id(),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("subscription_id", sa.UUID()),
        sa.Column("number", sa.String(16), nullable=False),
        sa.Column("fy", sa.String(4), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_payment_id", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("supplier", postgresql.JSONB(), nullable=False),
        sa.Column("recipient", postgresql.JSONB(), nullable=False),
        sa.Column("place_of_supply", sa.String(2), nullable=False),
        sa.Column("intra_state", sa.Boolean(), nullable=False),
        sa.Column("taxable_paise", sa.BigInteger(), nullable=False),
        sa.Column("cgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("sgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("igst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("total_paise", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("pdf_storage_key", sa.String(512)),
        *_ts(),
        sa.CheckConstraint(
            "total_paise = taxable_paise + cgst_paise + sgst_paise + igst_paise",
            name="ck_invoice_total"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "id"),
        sa.UniqueConstraint("number"),
        sa.UniqueConstraint("provider_payment_id"),
    )
    op.create_index("ix_invoice_practice_id", "invoice", ["practice_id"])

    op.create_table(
        "invoice_line", _id(),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="1", nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("sac", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("taxable_paise", sa.BigInteger(), nullable=False),
        sa.Column("tax_rate_bp", sa.Integer(), nullable=False),
        sa.Column("cgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("sgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("igst_paise", sa.BigInteger(), server_default="0", nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["practice_id", "invoice_id"],
                                ["invoice.practice_id", "invoice.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_line_practice_id", "invoice_line", ["practice_id"])
    op.create_index("ix_invoice_line_invoice_id", "invoice_line", ["invoice_id"])

    op.create_table(
        "billing_event",
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("practice_id", sa.UUID()),
        sa.Column("outcome", sa.String(32), server_default="applied", nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_table(
        "invoice_sequence",
        sa.Column("fy", sa.String(4), nullable=False),
        sa.Column("last_value", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("fy"),
    )

    for table in TENANT:  # enable_rls_sql() would also re-create the practice policy
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (practice_id = {rls.CURRENT_PRACTICE}) "
            f"WITH CHECK (practice_id = {rls.CURRENT_PRACTICE})")
    op.execute(FIND_PRACTICE_FN)
    app = rls.APP_ROLE
    # Invoices are tax records: the app may insert and read them but never
    # update (except the cached PDF key) or delete them.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON subscription TO {app}")
    op.execute(f"GRANT SELECT, INSERT ON invoice, invoice_line TO {app}")
    op.execute(f"GRANT UPDATE (pdf_storage_key, updated_at) ON invoice TO {app}")
    op.execute(f"GRANT SELECT, INSERT ON billing_event TO {app}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON invoice_sequence TO {app}")
    op.execute("REVOKE ALL ON FUNCTION billing_find_practice(text, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION billing_find_practice(text, text) TO {app}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS billing_find_practice(text, text)")
    for t in ("invoice_sequence", "billing_event", "invoice_line", "invoice", "subscription"):
        op.drop_table(t)
    for c in ("billing_address", "billing_state_code", "billing_legal_name"):
        op.drop_column("practice", c)
