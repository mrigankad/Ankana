"""Privacy tables. All tenant scoped (RLS on practice_id, see PRIVACY_TABLES).

- practice_key       wrapped per-practice keys (dek versions + blind index key)
- privacy_settings   per-practice retention configuration
- privacy_request    export / erasure / retention jobs and their outcome (no PII
                     except `reason`, which is encrypted)
- correction_log     before/after values of rectified personal data (encrypted;
                     nulled when the client is erased)
- consent_receipt    immutable, signed record of every consent grant or withdrawal
                     (append-only: RLS allows SELECT and INSERT only)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.tenancy.models import Base, Timestamps, _pk, _practice_fk

from .types import EncryptedText

REQUEST_KINDS = ("client_export", "client_erase", "practice_export", "practice_delete",
                 "retention_dry_run", "retention_apply")
REQUEST_STATUSES = ("queued", "running", "done", "failed", "blocked")


class PracticeKey(Base):
    __tablename__ = "practice_key"
    __table_args__ = (
        UniqueConstraint("practice_id", "kind", "version"),
        CheckConstraint("kind IN ('dek','blind')", name="ck_practice_key_kind"),
        CheckConstraint("status IN ('active','retired')", name="ck_practice_key_status"),
    )

    id: Mapped[uuid.UUID] = _pk()
    # Deferred FK: the first flush of a brand-new practice writes its keys before the row.
    practice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice.id", deferrable=True, initially="DEFERRED"),
        nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(8))
    version: Mapped[int] = mapped_column(Integer)
    wrapped: Mapped[str] = mapped_column(Text)
    master_key_id: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(8), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PrivacySettings(Base, Timestamps):
    __tablename__ = "privacy_settings"

    practice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practice.id"), primary_key=True)
    # None disables retention. Clients with no activity for this many years are
    # candidates (see service.retention_candidates).
    retention_inactive_years: Mapped[int | None] = mapped_column(Integer)
    retention_auto_apply: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"))
    __table_args__ = (
        CheckConstraint("retention_inactive_years IS NULL OR retention_inactive_years BETWEEN 1 AND 50",
                        name="ck_privacy_retention_years"),
    )


class PrivacyRequest(Base, Timestamps):
    __tablename__ = "privacy_request"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        CheckConstraint(
            "kind IN (" + ",".join(f"'{k}'" for k in REQUEST_KINDS) + ")",
            name="ck_privacy_request_kind"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{s}'" for s in REQUEST_STATUSES) + ")",
            name="ck_privacy_request_status"),
        Index("ix_privacy_request_client", "practice_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    # No FK: the request outlives the client's data (the client row stays as a tombstone).
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(12), default="queued", server_default="queued")
    reason: Mapped[str | None] = mapped_column(EncryptedText("privacy_request.reason"))
    requested_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    result_key: Mapped[str | None] = mapped_column(String(512))
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CorrectionLog(Base):
    __tablename__ = "correction_log"
    __table_args__ = (
        ForeignKeyConstraint(["practice_id", "client_id"], ["client.practice_id", "client.id"]),
        Index("ix_correction_log_client", "practice_id", "client_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    field: Mapped[str] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(EncryptedText("correction_log.old_value"))
    new_value: Mapped[str | None] = mapped_column(EncryptedText("correction_log.new_value"))
    reason: Mapped[str | None] = mapped_column(String(500))
    changed_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConsentReceipt(Base):
    """Append-only. `receipt_hash` is sha256 of the canonical receipt body and
    `signature` an HMAC under the practice key, so a stored receipt can be
    re-verified later (service.verify_receipt)."""

    __tablename__ = "consent_receipt"
    __table_args__ = (
        ForeignKeyConstraint(["practice_id", "client_id"], ["client.practice_id", "client.id"]),
        CheckConstraint("event IN ('granted','withdrawn')", name="ck_consent_receipt_event"),
        Index("ix_consent_receipt_client", "practice_id", "client_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    consent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    event: Mapped[str] = mapped_column(String(12))
    purpose: Mapped[str] = mapped_column(String(32))
    notice_version: Mapped[str] = mapped_column(String(32))
    notice_language: Mapped[str | None] = mapped_column(String(16))
    # sha256 of the notice text the client saw; null when the caller sent no text.
    notice_text_sha256: Mapped[str | None] = mapped_column(String(64))
    channel: Mapped[str | None] = mapped_column(String(32))
    collected_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    receipt_hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(64))


PRIVACY_TABLES: tuple[str, ...] = (
    "practice_key", "privacy_settings", "privacy_request", "correction_log", "consent_receipt",
)
APPEND_ONLY_PRIVACY = ("consent_receipt",)
