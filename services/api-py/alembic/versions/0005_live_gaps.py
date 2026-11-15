"""client tags, consultation scheduled_at, practice location

Revision ID: 0005_live_gaps
Revises: 0004_security_hardening
"""
import sqlalchemy as sa

from alembic import op
from app.tenancy import rls

revision = "0005_live_gaps"
down_revision = "0005_messaging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("consultation", sa.Column("scheduled_at", sa.DateTime(timezone=True),
                                            nullable=True))
    op.create_index("ix_consultation_practice_scheduled", "consultation",
                    ["practice_id", "scheduled_at"])
    op.add_column("practice", sa.Column("place_label", sa.String(200), nullable=True))
    op.add_column("practice", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("practice", sa.Column("longitude", sa.Float(), nullable=True))

    op.create_table(
        "client_tag",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("tag", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.ForeignKeyConstraint(["practice_id"], ["practice.id"]),
        sa.ForeignKeyConstraint(["practice_id", "client_id"],
                                ["client.practice_id", "client.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "client_id", "tag"),
    )
    op.create_index("ix_client_tag_client_id", "client_tag", ["client_id"])
    op.create_index("ix_client_tag_practice_tag", "client_tag", ["practice_id", "tag"])
    op.execute("ALTER TABLE client_tag ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE client_tag FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON client_tag "
               f"USING (practice_id = {rls.CURRENT_PRACTICE}) "
               f"WITH CHECK (practice_id = {rls.CURRENT_PRACTICE})")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON client_tag TO {rls.APP_ROLE}")


def downgrade() -> None:
    op.drop_table("client_tag")
    for c in ("longitude", "latitude", "place_label"):
        op.drop_column("practice", c)
    op.drop_index("ix_consultation_practice_scheduled", table_name="consultation")
    op.drop_column("consultation", "scheduled_at")
