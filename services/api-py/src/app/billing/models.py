"""Billing tables. Tenant tables (subscription, invoice, invoice_line) are under
RLS; billing_event and invoice_sequence are global because the webhook arrives
before any practice is known and the invoice series belongs to the supplier,
not to a practice."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
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

BILLING_TENANT_TABLES = ("subscription", "invoice", "invoice_line")

SUB_STATUSES = ("created", "active", "past_due", "halted", "cancelled")


class Subscription(Base, Timestamps):
    """One row per provider subscription. 'created' = checkout started, not paid."""

    __tablename__ = "subscription"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        CheckConstraint(
            "status IN ('created','active','past_due','halted','cancelled')",
            name="ck_subscription_status"),
        CheckConstraint("interval IN ('month','year')", name="ck_subscription_interval"),
        Index("uq_subscription_provider_id", "provider", "provider_subscription_id", unique=True),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    plan_key: Mapped[str] = mapped_column(String(32))
    interval: Mapped[str] = mapped_column(String(8), default="month", server_default="month")
    status: Mapped[str] = mapped_column(String(16), default="created", server_default="created")
    provider: Mapped[str] = mapped_column(String(16))
    provider_customer_id: Mapped[str | None] = mapped_column(String(64))
    provider_subscription_id: Mapped[str] = mapped_column(String(64))
    checkout_url: Mapped[str | None] = mapped_column(Text)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"))
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invoice(Base, Timestamps):
    __tablename__ = "invoice"
    __table_args__ = (
        UniqueConstraint("practice_id", "id"),
        UniqueConstraint("number"),
        UniqueConstraint("provider_payment_id"),
        CheckConstraint("total_paise = taxable_paise + cgst_paise + sgst_paise + igst_paise",
                        name="ck_invoice_total"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    number: Mapped[str] = mapped_column(String(16))  # GST rule 46: at most 16 characters
    fy: Mapped[str] = mapped_column(String(4))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider_payment_id: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    supplier: Mapped[dict] = mapped_column(JSONB)
    recipient: Mapped[dict] = mapped_column(JSONB)
    place_of_supply: Mapped[str] = mapped_column(String(2))
    intra_state: Mapped[bool] = mapped_column(Boolean)
    taxable_paise: Mapped[int] = mapped_column(BigInteger)
    cgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    sgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    igst_paise: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_paise: Mapped[int] = mapped_column(BigInteger)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pdf_storage_key: Mapped[str | None] = mapped_column(String(512))


class InvoiceLine(Base, Timestamps):
    __tablename__ = "invoice_line"
    __table_args__ = (
        ForeignKeyConstraint(["practice_id", "invoice_id"], ["invoice.practice_id", "invoice.id"],
                             ondelete="CASCADE"),
    )

    id: Mapped[uuid.UUID] = _pk()
    practice_id: Mapped[uuid.UUID] = _practice_fk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    position: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(String(300))
    sac: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    taxable_paise: Mapped[int] = mapped_column(BigInteger)
    tax_rate_bp: Mapped[int] = mapped_column(Integer)
    cgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    sgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    igst_paise: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class BillingEvent(Base):
    """Webhook idempotency ledger (global). event_id is the provider event id."""

    __tablename__ = "billing_event"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16))
    event_type: Mapped[str] = mapped_column(String(64))
    practice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(32), default="applied")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoiceSequence(Base):
    """Gapless per-financial-year counter for the supplier's invoice series."""

    __tablename__ = "invoice_sequence"

    fy: Mapped[str] = mapped_column(String(4), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
