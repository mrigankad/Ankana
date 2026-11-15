"""AI connections and routing per practice (RLS)

Revision ID: 0003_ai_connections
Revises: 0002_reports_jobs
"""
import sqlalchemy as sa

from alembic import op
from app.tenancy import rls

revision = "0003_ai_connections"
down_revision = "0003_auth_builtin"
branch_labels = None
depends_on = None

TABLES = ("ai_connection", "ai_routing")
KINDS = ("anthropic", "claude_code", "ollama_local", "ollama_cloud", "gemini", "gemini_cli",
         "codex", "openai_compatible", "mock")
ROLES = ("classify", "narrate", "synthesise", "report")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


def _stamps() -> list[sa.Column]:
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                      nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                      nullable=False)]


def upgrade() -> None:
    op.create_table(
        "ai_connection",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("model_top", sa.String(120), nullable=True),
        sa.Column("model_strong", sa.String(120), nullable=True),
        sa.Column("model_fast", sa.String(120), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_stamps(),
        sa.CheckConstraint(_in("kind", KINDS), name="ck_ai_connection_kind"),
        sa.ForeignKeyConstraint(["practice_id"], ["practice.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "id"),
        sa.UniqueConstraint("practice_id", "label"),
    )
    op.create_index("ix_ai_connection_practice_id", "ai_connection", ["practice_id"])
    op.create_table(
        "ai_routing",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("preset", sa.String(32), nullable=True),
        *_stamps(),
        sa.CheckConstraint(_in("role", ROLES), name="ck_ai_routing_role"),
        sa.ForeignKeyConstraint(["practice_id"], ["practice.id"]),
        sa.ForeignKeyConstraint(["practice_id", "connection_id"],
                                ["ai_connection.practice_id", "ai_connection.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "role"),
    )
    op.create_index("ix_ai_routing_practice_id", "ai_routing", ["practice_id"])
    for stmt in rls.enable_rls_sql(TABLES)[:-3]:  # skip the practice-root statements
        op.execute(stmt)
    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {rls.APP_ROLE}")


def downgrade() -> None:
    op.drop_table("ai_routing")
    op.drop_table("ai_connection")
