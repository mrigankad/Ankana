"""ORM for the notification tables (RLS by practice_id, see migration 0003)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.privacy.types import EncryptedText
from app.tenancy.models import Base, Timestamps, _pk, _practice_fk

KINDS = ("remedy_due", "remedy_missed", "ending_soon", "plan_complete", "followup_due")
LANGUAGES = ("en", "hi")
STATUSES = ("pending", "sent", "failed", "skipped", "cancelled")


class NotificationPref(Base, Timestamps):
    __tablename__ = "notification_pref"
    __table_args__ = (
        UniqueConstraint("practice_id", "client_id"),
        ForeignKeyConstraint(["practice_id", "client_id"], ["client.practice_id", "client.id"]),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=False,
                                               server_default=text("false"))
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False,
                                                  server_default=text("false"))
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    quiet_start: Mapped[time] = mapped_column(Time, default=time(21, 0), server_default="21:00")
    quiet_end: Mapped[time] = mapped_column(Time, default=time(7, 0), server_default="07:00")
    language: Mapped[str | None] = mapped_column(String(8))  # null: use the client's


class NotificationTemplate(Base, Timestamps):
    __tablename__ = "notification_template"
    __table_args__ = (UniqueConstraint("practice_id", "kind", "channel", "language"),)

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    kind: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16), default="*", server_default="*")
    language: Mapped[str] = mapped_column(String(8))
    subject: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    updated_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Notification(Base, Timestamps):
    """Outbox row. Rendered text is stored so the outbox shows exactly what was (or
    will be) sent. `dedupe_key` makes scheduling idempotent per practice."""

    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint("practice_id", "dedupe_key", name="uq_notification_dedupe"),
        ForeignKeyConstraint(["practice_id", "client_id"], ["client.practice_id", "client.id"]),
        CheckConstraint("status IN ('pending','sent','failed','skipped','cancelled')",
                        name="ck_notification_status"),
        CheckConstraint("delivery_status IS NULL OR delivery_status IN "
                        "('sent','delivered','read','failed')", name="ck_notification_delivery"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("practice.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    local_date: Mapped[date] = mapped_column(Date)
    dedupe_key: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    skip_reason: Mapped[str | None] = mapped_column(String(64))
    subject: Mapped[str | None] = mapped_column(EncryptedText("notification.subject"))
    body: Mapped[str] = mapped_column(EncryptedText("notification.body"))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    resend_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(32))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    # Provider receipts (webhooks): sent | delivered | read | failed. `status` stays the
    # outbox state; this is what the carrier or WhatsApp reported afterwards.
    delivery_status: Mapped[str | None] = mapped_column(String(16))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_error: Mapped[str | None] = mapped_column(String(200))
