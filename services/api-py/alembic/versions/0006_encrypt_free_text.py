"""encrypt the remaining free-text columns

Revision ID: 0006_encrypt_free_text
Revises: 0005_messaging

remedy_item.instructions, remedy_checkin.note, consultation.topic, consent.notice_text,
notification.subject and notification.body become field-encrypted (app.privacy). Ciphertext
is longer than the plaintext, so consultation.topic and notification.subject are widened to
text. consent gets notice_text_sha256 (the evidence hash survives even when the text is
destroyed), filled from existing rows before they are encrypted. Existing rows are encrypted
in place (needs ANKANA_MASTER_KEY unless API_ENV is dev/test and the database has no
practices). Downgrade decrypts these columns again; column widths are not narrowed back.
"""
import sqlalchemy as sa

from alembic import op
from app.privacy import backfill

revision = "0006_encrypt_free_text"
down_revision = "0005_live_gaps"
branch_labels = None
depends_on = None

COLUMNS = {
    ("remedy_item", "instructions"), ("remedy_checkin", "note"), ("consultation", "topic"),
    ("consent", "notice_text"), ("notification", "subject"), ("notification", "body"),
}


def upgrade() -> None:
    op.alter_column("consultation", "topic", type_=sa.Text(), existing_nullable=True)
    op.alter_column("notification", "subject", type_=sa.Text(), existing_nullable=True)
    op.add_column("consent", sa.Column("notice_text_sha256", sa.String(64), nullable=True))
    # hash first, while the text is still plaintext; rows created by older code have none
    conn = op.get_bind()
    for pid in backfill.practice_ids(conn):
        backfill.bind(conn, pid)
        conn.execute(sa.text(
            "UPDATE consent SET notice_text_sha256 = "
            "encode(sha256(convert_to(notice_text, 'UTF8')), 'hex') "
            "WHERE practice_id = :p AND notice_text IS NOT NULL "
            "AND notice_text NOT LIKE 'enc1:%' AND notice_text_sha256 IS NULL"), {"p": pid})
    backfill.encrypt_existing(conn, only=COLUMNS)


def downgrade() -> None:
    backfill.decrypt_existing(op.get_bind(), only=COLUMNS)
    op.drop_column("consent", "notice_text_sha256")
