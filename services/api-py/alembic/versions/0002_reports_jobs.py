"""report pipeline: job queue, report status/options, practice branding

Revision ID: 0002_reports_jobs
Revises: 0001
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.tenancy import rls

revision = "0002_reports_jobs"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Practice branding.
    op.add_column("practice", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column("practice", sa.Column("brand_primary_color", sa.String(7), nullable=True))
    op.add_column("practice", sa.Column("brand_accent_color", sa.String(7), nullable=True))
    op.add_column("practice", sa.Column("brand_footer", sa.String(200), nullable=True))

    # Report: status machine + request snapshot.
    op.alter_column("report", "storage_key", existing_type=sa.String(512), nullable=True)
    op.add_column("report", sa.Column("template", sa.String(32), server_default="standard",
                                      nullable=False))
    op.add_column("report", sa.Column("language", sa.String(8), server_default="en",
                                      nullable=False))
    op.add_column("report", sa.Column("options", postgresql.JSONB(), nullable=True))
    op.add_column("report", sa.Column("options_hash", sa.String(64), nullable=True))
    op.add_column("report", sa.Column("status", sa.String(16), server_default="queued",
                                      nullable=False))
    op.add_column("report", sa.Column("error", sa.Text(), nullable=True))
    op.add_column("report", sa.Column("job_id", sa.UUID(), nullable=True))
    op.add_column("report", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.create_unique_constraint("uq_report_practice_id_id", "report", ["practice_id", "id"])
    op.create_check_constraint(
        "ck_report_status", "report", "status IN ('queued','rendering','done','failed')")
    op.create_index(
        "uq_report_key", "report",
        ["practice_id", "chart_artifact_id", "template_version", "options_hash"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"))

    # Queue (global table, no RLS; payloads carry ids only).
    op.create_table(
        "job",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint("status IN ('queued','running','done','failed')", name="ck_job_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_claim", "job", ["status", "run_at"])
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON job TO {rls.APP_ROLE}")


def downgrade() -> None:
    op.drop_table("job")
    op.drop_index("uq_report_key", table_name="report")
    op.drop_constraint("ck_report_status", "report", type_="check")
    op.drop_constraint("uq_report_practice_id_id", "report", type_="unique")
    for c in ("size_bytes", "job_id", "error", "status", "options_hash", "options",
              "language", "template"):
        op.drop_column("report", c)
    op.alter_column("report", "storage_key", existing_type=sa.String(512), nullable=False)
    for c in ("brand_footer", "brand_accent_color", "brand_primary_color", "logo_url"):
        op.drop_column("practice", c)
