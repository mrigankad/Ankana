"""consultation workflow: pinned chart facts, session summary, predictions, life events

Revision ID: 0009_consult_flow
Revises: 0008_erasure_log

Adds consultation.client_question and consultation_note.facts, and the tables
consultation_summary, consult_prediction and client_life_event (RLS forced, free text
encrypted at the application layer). New tables start empty, so no backfill is needed.
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.tenancy import rls

revision = "0009_consult_flow"
down_revision = "0008_erasure_log"
branch_labels = None
depends_on = None

NEW_TABLES = ("consultation_summary", "consult_prediction", "client_life_event")


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    ]


def _id():
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                     primary_key=True)


def upgrade() -> None:
    op.add_column("consultation", sa.Column("client_question", sa.Text(), nullable=True))
    op.add_column("consultation_note", sa.Column(
        "facts", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))

    op.create_table(
        "consultation_summary", _id(),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("consultation_id", sa.UUID(), nullable=False),
        sa.Column("topics", sa.Text(), nullable=False),
        sa.Column("remedies_given", sa.Text(), nullable=False),
        sa.Column("source", sa.String(8), server_default="manual", nullable=False),
        sa.Column("author_member_id", sa.UUID()),
        *_ts(),
        sa.ForeignKeyConstraint(["practice_id", "consultation_id"],
                                ["consultation.practice_id", "consultation.id"]),
        sa.UniqueConstraint("consultation_id"),
        sa.CheckConstraint("source IN ('manual','ai')", name="ck_consultation_summary_source"),
    )
    op.create_index("ix_consultation_summary_practice_id", "consultation_summary", ["practice_id"])
    op.create_index("ix_consultation_summary_consultation_id", "consultation_summary",
                    ["consultation_id"])

    op.create_table(
        "consult_prediction", _id(),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("consultation_id", sa.UUID(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("window_start", sa.Date()),
        sa.Column("window_end", sa.Date()),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("outcome_note", sa.Text()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.ForeignKeyConstraint(["practice_id", "client_id"],
                                ["client.practice_id", "client.id"]),
        sa.ForeignKeyConstraint(["practice_id", "consultation_id"],
                                ["consultation.practice_id", "consultation.id"]),
        sa.CheckConstraint("status IN ('pending','came_true','did_not','unclear')",
                           name="ck_consult_prediction_status"),
        sa.CheckConstraint(
            "window_end IS NULL OR window_start IS NULL OR window_end >= window_start",
            name="ck_consult_prediction_window"),
    )
    op.create_index("ix_consult_prediction_practice_id", "consult_prediction", ["practice_id"])
    op.create_index("ix_consult_prediction_client_id", "consult_prediction", ["client_id"])
    op.create_index("ix_consult_prediction_consultation_id", "consult_prediction",
                    ["consultation_id"])

    op.create_table(
        "client_life_event", _id(),
        sa.Column("practice_id", sa.UUID(), sa.ForeignKey("practice.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(24), server_default="other", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.ForeignKeyConstraint(["practice_id", "client_id"],
                                ["client.practice_id", "client.id"]),
    )
    op.create_index("ix_client_life_event_practice_id", "client_life_event", ["practice_id"])
    op.create_index("ix_client_life_event_client_id", "client_life_event", ["client_id"])

    for stmt in rls.enable_rls_sql(NEW_TABLES, append_only=())[:-3]:
        op.execute(stmt)  # [:-3] drops the practice-root statements (already done in 0001)
    for table in NEW_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {rls.APP_ROLE}")


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
    op.drop_column("consultation_note", "facts")
    op.drop_column("consultation", "client_question")
