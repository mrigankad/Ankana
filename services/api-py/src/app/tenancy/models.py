"""SQLAlchemy 2 models for the tenant schema (v1).

Conventions
- UUID primary keys (python-side uuid4 plus a server default for raw SQL).
- created_at / updated_at on every table; deleted_at where DPDP erasure or
  undo needs a tombstone.
- Every tenant table carries practice_id and is covered by an RLS policy
  (see app.tenancy.rls). `user_account` is the only global table.
- Enumerations are stored as text with CHECK constraints, not native PG enums,
  so adding a value is a one-line migration.
- Composite FKs (practice_id, x_id) -> x(practice_id, id) make it impossible
  for a row to point at another practice's client or birth record, even for a
  superuser-written row.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.privacy.types import EncryptedText

REMEDY_CYCLE_DAYS_DEFAULT = 43


class Role(enum.StrEnum):
    owner = "owner"
    astrologer = "astrologer"
    assistant = "assistant"
    client = "client"


class TimeSource(enum.StrEnum):
    certificate = "certificate"
    memory = "memory"
    approximate = "approximate"
    unknown = "unknown"


class ConsentPurpose(enum.StrEnum):
    chart_compute = "chart_compute"
    ai_assistant = "ai_assistant"
    report_sharing = "report_sharing"
    marketing = "marketing"
    reminders = "reminders"


class RemedyStatus(enum.StrEnum):
    draft = "draft"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(
        e,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda x: [m.value for m in x],
        length=32,
    )


class Base(DeclarativeBase):
    pass


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDelete:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


def _practice_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("practice.id"), nullable=False, index=True
    )


# --------------------------------------------------------------------------
# Global
# --------------------------------------------------------------------------
class UserAccount(Base, Timestamps, SoftDelete):
    """A person who can log in. Global (not tenant scoped): one user may belong
    to several practices through `member`. Identity comes from the auth
    provider; (issuer, subject) is the stable key."""

    __tablename__ = "user_account"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)

    id: Mapped[uuid.UUID] = _pk()
    issuer: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    display_name: Mapped[str | None] = mapped_column(String(200))


# --------------------------------------------------------------------------
# Tenant tables
# --------------------------------------------------------------------------
class Practice(Base, Timestamps, SoftDelete):
    """The tenant. Its RLS key is `id` itself."""

    __tablename__ = "practice"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(15))
    state: Mapped[str | None] = mapped_column(String(64))
    plan: Mapped[str] = mapped_column(String(32), default="trial", server_default="trial")
    razorpay_customer_id: Mapped[str | None] = mapped_column(String(64))
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(64))
    # GST invoice recipient details (see app.billing). state_code is the GST state
    # code of the place of supply; with a GSTIN it must equal the GSTIN prefix.
    billing_legal_name: Mapped[str | None] = mapped_column(String(200))
    billing_state_code: Mapped[str | None] = mapped_column(String(2))
    billing_address: Mapped[str | None] = mapped_column(Text)
    # Report branding (see app.reports). logo_url is https or a small data: URI.
    logo_url: Mapped[str | None] = mapped_column(Text)
    brand_primary_color: Mapped[str | None] = mapped_column(String(7))  # #RRGGBB
    brand_accent_color: Mapped[str | None] = mapped_column(String(7))
    brand_footer: Mapped[str | None] = mapped_column(String(200))
    # Reminders (see app.notify): IANA zone, local hour for daily reminders.
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Kolkata", server_default="Asia/Kolkata")
    notify_hour: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    notify_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"))
    # Where the practice sits, for the daily panchang on Today. Null falls back to the
    # time zone's default city.
    place_label: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)


class Member(Base, Timestamps, SoftDelete):
    """Membership of a user in a practice with a role. Members with role
    `client` are portal users tied to one client record (own data only,
    enforced in the app layer)."""

    __tablename__ = "member"
    __table_args__ = (
        UniqueConstraint("practice_id", "user_id"),
        UniqueConstraint("practice_id", "id"),
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"],
            name="fk_member_client", use_alter=True,
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), index=True)
    role: Mapped[Role] = mapped_column(_enum(Role, "member_role"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Client(Base, Timestamps, SoftDelete):
    """A person the practice serves. Contact fields are field-encrypted
    (app.privacy) with HMAC blind indexes for equality lookup; the display name
    stays queryable for search."""

    __tablename__ = "client"
    __table_args__ = (UniqueConstraint("practice_id", "id"),)

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    display_name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(EncryptedText("client.contact_email"))
    contact_phone: Mapped[str | None] = mapped_column(EncryptedText("client.contact_phone"))
    # HMAC-SHA256 blind indexes (app.privacy.blind); maintained on insert/update.
    contact_email_bidx: Mapped[str | None] = mapped_column(String(64), index=True)
    contact_phone_bidx: Mapped[str | None] = mapped_column(String(64), index=True)
    timezone: Mapped[str | None] = mapped_column(String(64))
    preferred_language: Mapped[str | None] = mapped_column(String(16))
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # DPDP erasure: PII columns are nulled and erased_at stamped; the row and
    # its id survive so audit and counters stay consistent.
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Legal hold blocks erasure and retention deletion until released.
    legal_hold: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"))
    legal_hold_reason: Mapped[str | None] = mapped_column(EncryptedText("client.legal_hold_reason"))
    legal_hold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Consent(Base, Timestamps):
    """One row per grant. Withdrawal stamps withdrawn_at; a re-grant is a new
    row. Never deleted (evidence)."""

    __tablename__ = "consent"
    __table_args__ = (
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"]
        ),
        Index("ix_consent_client_purpose", "practice_id", "client_id", "purpose"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[ConsentPurpose] = mapped_column(_enum(ConsentPurpose, "consent_purpose"))
    notice_version: Mapped[str] = mapped_column(String(32))
    notice_text: Mapped[str | None] = mapped_column(EncryptedText("consent.notice_text"))
    notice_text_sha256: Mapped[str | None] = mapped_column(String(64))
    notice_language: Mapped[str | None] = mapped_column(String(16))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str | None] = mapped_column(String(32))
    collected_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ClientTag(Base, Timestamps):
    """A practitioner's own label on a client (free text, e.g. "Lal Kitab", "Rectify")."""

    __tablename__ = "client_tag"
    __table_args__ = (
        UniqueConstraint("practice_id", "client_id", "tag"),
        ForeignKeyConstraint(["practice_id", "client_id"], ["client.practice_id", "client.id"]),
        Index("ix_client_tag_practice_tag", "practice_id", "tag"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    tag: Mapped[str] = mapped_column(String(40))


class BirthRecord(Base, Timestamps, SoftDelete):
    """Versioned: an edit inserts version n+1 pointing at the previous row;
    old versions are never overwritten (artifacts and reports reference them)."""

    __tablename__ = "birth_record"
    __table_args__ = (
        UniqueConstraint("client_id", "version"),
        UniqueConstraint("practice_id", "id"),
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"]
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_birth_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_birth_lon"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    birth_date: Mapped[date] = mapped_column(Date)
    birth_time: Mapped[time | None] = mapped_column(Time)  # null when time_source=unknown
    time_source: Mapped[TimeSource] = mapped_column(_enum(TimeSource, "birth_time_source"))
    place_label: Mapped[str] = mapped_column(EncryptedText("birth_record.place_label"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone_name: Mapped[str] = mapped_column(String(64))
    tz_source: Mapped[str | None] = mapped_column(String(32))
    rectification_status: Mapped[str | None] = mapped_column(String(32))


class ChartArtifact(Base, Timestamps):
    """Computed chart, immutable. New engine versions add rows; old rows stay
    so reports stay reproducible. Also the idempotency key for chart API."""

    __tablename__ = "chart_artifact"
    __table_args__ = (
        UniqueConstraint("birth_record_id", "settings_hash", "engine_version"),
        UniqueConstraint("practice_id", "id"),
        ForeignKeyConstraint(
            ["practice_id", "birth_record_id"],
            ["birth_record.practice_id", "birth_record.id"],
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    birth_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    settings_hash: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    payload: Mapped[dict] = mapped_column(JSONB)


class Consultation(Base, Timestamps, SoftDelete):
    __tablename__ = "consultation"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"]
        ),
        ForeignKeyConstraint(
            ["practice_id", "member_id"], ["member.practice_id", "member.id"]
        ),
        ForeignKeyConstraint(
            ["practice_id", "chart_artifact_id"],
            ["chart_artifact.practice_id", "chart_artifact.id"],
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    chart_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    consulted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mode: Mapped[str | None] = mapped_column(String(32))
    topic: Mapped[str | None] = mapped_column(EncryptedText("consultation.topic"))
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    # When the visit is booked for; consulted_at stays the time it was recorded or held.
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What the client said they want to ask, captured before or at the visit.
    client_question: Mapped[str | None] = mapped_column(
        EncryptedText("consultation.client_question"))


class ConsultationNote(Base, Timestamps, SoftDelete):
    """Free text, sensitive. Body is field-encrypted (app.privacy)."""

    __tablename__ = "consultation_note"
    __table_args__ = (
        ForeignKeyConstraint(
            ["practice_id", "consultation_id"],
            ["consultation.practice_id", "consultation.id"],
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    body: Mapped[str] = mapped_column(EncryptedText("consultation_note.body"))
    # Chart facts pinned in the body: [{id, type, ref, label}]. The body holds {{fact:<id>}}
    # markers; the facts are structured so a chip can link back to the chart tab.
    facts: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))


class ConsultationSummary(Base, Timestamps):
    """Structured summary of one consultation. topics and remedies_given are JSON lists
    held as encrypted text; the follow-up date also lands on the consultation."""

    __tablename__ = "consultation_summary"
    __table_args__ = (
        UniqueConstraint("consultation_id"),
        ForeignKeyConstraint(
            ["practice_id", "consultation_id"],
            ["consultation.practice_id", "consultation.id"],
        ),
        CheckConstraint("source IN ('manual','ai')", name="ck_consultation_summary_source"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    topics: Mapped[str] = mapped_column(EncryptedText("consultation_summary.topics"))
    remedies_given: Mapped[str] = mapped_column(
        EncryptedText("consultation_summary.remedies_given"))
    source: Mapped[str] = mapped_column(String(8), default="manual", server_default="manual")
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class PredictionStatus(enum.StrEnum):
    pending = "pending"
    came_true = "came_true"
    did_not = "did_not"
    unclear = "unclear"


class ConsultPrediction(Base, Timestamps, SoftDelete):
    """A prediction the practitioner made in a consultation, kept for outcome tracking."""

    __tablename__ = "consult_prediction"
    __table_args__ = (
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"]
        ),
        ForeignKeyConstraint(
            ["practice_id", "consultation_id"],
            ["consultation.practice_id", "consultation.id"],
        ),
        CheckConstraint("status IN ('pending','came_true','did_not','unclear')",
                        name="ck_consult_prediction_status"),
        CheckConstraint("window_end IS NULL OR window_start IS NULL OR window_end >= window_start",
                        name="ck_consult_prediction_window"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    statement: Mapped[str] = mapped_column(EncryptedText("consult_prediction.statement"))
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    outcome_note: Mapped[str | None] = mapped_column(EncryptedText("consult_prediction.outcome_note"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientLifeEvent(Base, Timestamps, SoftDelete):
    """A life event the practitioner records for a client (marriage, job change, move...)."""

    __tablename__ = "client_life_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"]
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    event_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(24), default="other", server_default="other")
    title: Mapped[str] = mapped_column(EncryptedText("client_life_event.title"))
    notes: Mapped[str | None] = mapped_column(EncryptedText("client_life_event.notes"))


class RemedyPlan(Base, Timestamps, SoftDelete):
    """A remedy programme for a client. cycle_days is data (default 43).

    One-active-at-a-time: a partial unique index allows at most one plan with
    status='active' (and not deleted) per (practice, client). Finish or cancel
    the current plan before activating another.
    """

    __tablename__ = "remedy_plan"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"]
        ),
        ForeignKeyConstraint(
            ["practice_id", "consultation_id"],
            ["consultation.practice_id", "consultation.id"],
        ),
        CheckConstraint("cycle_days > 0", name="ck_remedy_cycle_positive"),
        Index(
            "uq_remedy_plan_one_active",
            "practice_id", "client_id",
            unique=True,
            postgresql_where=text("status = 'active' AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[RemedyStatus] = mapped_column(
        _enum(RemedyStatus, "remedy_status"), default=RemedyStatus.draft,
        server_default="draft",
    )
    cycle_days: Mapped[int] = mapped_column(
        Integer, default=REMEDY_CYCLE_DAYS_DEFAULT,
        server_default=str(REMEDY_CYCLE_DAYS_DEFAULT),
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    missed_day_policy: Mapped[str] = mapped_column(
        String(16), default="restart", server_default="restart"
    )
    # Missed-day policy state (see app.notify.policy). `extended_days` is already
    # included in cycle_days; evaluated_through is the last local day judged.
    missed_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    restart_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    extended_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    evaluated_through: Mapped[date | None] = mapped_column(Date)
    last_missed_date: Mapped[date | None] = mapped_column(Date)


class RemedyItem(Base, Timestamps, SoftDelete):
    __tablename__ = "remedy_item"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        ForeignKeyConstraint(
            ["practice_id", "plan_id"], ["remedy_plan.practice_id", "remedy_plan.id"]
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(EncryptedText("remedy_item.instructions"))
    planet: Mapped[str | None] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class RemedyCheckin(Base, Timestamps):
    __tablename__ = "remedy_checkin"
    __table_args__ = (
        UniqueConstraint("item_id", "checkin_date"),
        ForeignKeyConstraint(
            ["practice_id", "item_id"], ["remedy_item.practice_id", "remedy_item.id"]
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    checkin_date: Mapped[date] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    note: Mapped[str | None] = mapped_column(EncryptedText("remedy_checkin.note"))


class Report(Base, Timestamps, SoftDelete):
    """A rendered PDF. Keyed by (chart_artifact_id, template_version,
    options_hash): the same request returns the same row, a re-brand or
    section change is a new row. The PDF lives in object storage under
    storage_key (null until status='done')."""

    __tablename__ = "report"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        ForeignKeyConstraint(
            ["practice_id", "chart_artifact_id"],
            ["chart_artifact.practice_id", "chart_artifact.id"],
        ),
        CheckConstraint(
            "status IN ('queued','rendering','done','failed')", name="ck_report_status"
        ),
        Index(
            "uq_report_key", "practice_id", "chart_artifact_id", "template_version",
            "options_hash", unique=True, postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    chart_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    template: Mapped[str] = mapped_column(String(32), default="standard", server_default="standard")
    template_version: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    # Request snapshot: sections plus the branding at request time (no PII).
    options: Mapped[dict | None] = mapped_column(JSONB)
    options_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    storage_key: Mapped[str | None] = mapped_column(String(512))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    generated_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Job(Base, Timestamps):
    """Postgres-backed queue (see app.jobs). Deliberately NOT under RLS: the
    worker claims across practices, then does all tenant work through
    tenant_session(practice_id). Payloads carry ids only, never PII."""

    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','done','failed')", name="ck_job_status"
        ),
        Index("ix_job_claim", "status", "run_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    kind: Mapped[str] = mapped_column(String(64))
    practice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB)


class AuditEvent(Base):
    """Append-only (RLS allows SELECT and INSERT only). No PII in meta."""

    __tablename__ = "audit_event"

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict | None] = mapped_column(JSONB)


class UsageCounter(Base, Timestamps):
    """Per-practice metering, one row per (metric, month)."""

    __tablename__ = "usage_counter"
    __table_args__ = (UniqueConstraint("practice_id", "metric", "period"),)

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    metric: Mapped[str] = mapped_column(String(64))  # e.g. ai_tokens, reports, charts
    period: Mapped[date] = mapped_column(Date)  # first day of month
    value: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class IdempotencyKey(Base, Timestamps):
    """Replay store for the Idempotency-Key header. Same (key, endpoint) with the
    same request hash returns the stored response; a different hash is a 422."""

    __tablename__ = "idempotency_key"
    __table_args__ = (UniqueConstraint("practice_id", "endpoint", "key"),)

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    key: Mapped[str] = mapped_column(String(128))
    endpoint: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSONB)


# --------------------------------------------------------------------------
# Built-in authentication (see app.auth). Global tables carry no practice_id
# and are reachable only through the API's auth service; practice_invite is
# tenant scoped like everything else.
# --------------------------------------------------------------------------
class UserCredential(Base, Timestamps):
    """Optional password (argon2id hash). One row per user."""

    __tablename__ = "user_credential"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class AuthIdentity(Base, Timestamps):
    """A federated login (generic OIDC) linked to a user by verified email."""

    __tablename__ = "auth_identity"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))


class AuthOtp(Base):
    """One-time code. Only an HMAC of the code is stored."""

    __tablename__ = "auth_otp"

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    channel: Mapped[str] = mapped_column(String(16))  # email | phone
    destination: Mapped[str] = mapped_column(String(320), index=True)
    purpose: Mapped[str] = mapped_column(String(16))  # signin | signup
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict | None] = mapped_column(JSONB)  # signup: name, practice_name


class AuthSession(Base, Timestamps):
    """A refresh-token session. The secret is opaque; only its SHA-256 is kept,
    plus the previous one so a replayed (stolen) token is detected."""

    __tablename__ = "auth_session"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64))
    prev_refresh_hash: Mapped[str | None] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(16))  # otp | password | oidc
    practice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(32))


class AuthOidcState(Base):
    """In-flight authorization-code + PKCE request; single use."""

    __tablename__ = "auth_oidc_state"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64))
    code_verifier: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(64))
    redirect_to: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthEvent(Base):
    """Append-only sign-in log (global: failures have no practice). Holds a
    hash of the email, never the address, plus the IP for abuse limits."""

    __tablename__ = "auth_event"

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    action: Mapped[str] = mapped_column(String(48))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    subject_hash: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_auth_event_action_subject", "action", "subject_hash", "created_at"),
        Index("ix_auth_event_action_ip", "action", "ip", "created_at"),
    )


class PracticeInvite(Base, Timestamps):
    """Invitation to join a practice. Role `client` pins one client record
    (portal access). The token is shown once (emailed); only its hash is kept."""

    __tablename__ = "practice_invite"
    __table_args__ = (
        ForeignKeyConstraint(
            ["practice_id", "client_id"], ["client.practice_id", "client.id"],
            name="fk_invite_client"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[Role] = mapped_column(_enum(Role, "invite_role"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


AI_KINDS: tuple[str, ...] = (
    "anthropic", "claude_code", "ollama_local", "ollama_cloud", "gemini", "gemini_cli",
    "codex", "openai_compatible", "mock",
)
AI_ROLES: tuple[str, ...] = ("classify", "narrate", "synthesise", "report")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")"


class AiConnection(Base, Timestamps):
    """One way of reaching a model for a practice. The API key is Fernet-encrypted
    (ANKANA_SECRET_KEY) and never returned by the API. Local-machine kinds are only
    usable when ANKANA_ALLOW_LOCAL_PROVIDERS=1 (enforced in the app layer)."""

    __tablename__ = "ai_connection"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        UniqueConstraint("practice_id", "label"),
        CheckConstraint(_in_list("kind", AI_KINDS), name="ck_ai_connection_kind"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    kind: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str | None] = mapped_column(Text)
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    model_top: Mapped[str | None] = mapped_column(String(120))
    model_strong: Mapped[str | None] = mapped_column(String(120))
    model_fast: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class AiRouting(Base, Timestamps):
    """role -> connection (+ optional forced model). Deleting a connection drops its routes."""

    __tablename__ = "ai_routing"
    __table_args__ = (
        UniqueConstraint("practice_id", "role"),
        ForeignKeyConstraint(
            ["practice_id", "connection_id"], ["ai_connection.practice_id", "ai_connection.id"],
            ondelete="CASCADE"),
        CheckConstraint(_in_list("role", AI_ROLES), name="ck_ai_routing_role"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    role: Mapped[str] = mapped_column(String(16))
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    model: Mapped[str | None] = mapped_column(String(120))
    preset: Mapped[str | None] = mapped_column(String(32))


# Tables isolated by practice_id via RLS (practice is keyed by its own id).
TENANT_TABLES: tuple[str, ...] = (
    "member", "client", "consent", "birth_record", "chart_artifact",
    "consultation", "consultation_note", "remedy_plan", "remedy_item",
    "remedy_checkin", "report", "audit_event", "usage_counter", "idempotency_key",
    "practice_invite", "ai_connection", "ai_routing", "client_tag",
    "consultation_summary", "consult_prediction", "client_life_event",
)


from app.privacy.blind import register_blind_indexes  # noqa: E402

register_blind_indexes(Client)
