"""shared rate limit counters

Revision ID: 0007_rate_limit
Revises: 0006_encrypt_free_text

Global table (no practice, so no RLS): fixed-window counters keyed by a hash of
scope|caller. Replaces the per-process limiters on public endpoints.
"""
import sqlalchemy as sa

from alembic import op
from app.tenancy import rls

revision = "0007_rate_limit"
down_revision = "0006_encrypt_free_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_bucket",
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("key_hash", "window_start"),
    )
    op.create_index("ix_rate_limit_bucket_window", "rate_limit_bucket", ["window_start"])
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON rate_limit_bucket TO {rls.APP_ROLE}")


def downgrade() -> None:
    op.drop_table("rate_limit_bucket")
