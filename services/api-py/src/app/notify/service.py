"""Preferences, eligibility and outbox creation (all inside a tenant session)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.jobs import enqueue
from app.tenancy.models import Client, Consent, ConsentPurpose, Practice

from . import links
from .channels import CHANNEL_KINDS
from .models import LANGUAGES, Notification, NotificationPref, NotificationTemplate
from .templates import Rendered, render_message

SEND_JOB = "notify_send"

# Which consent purpose gates which notification kind. Remedy and follow-up reminders
# are service messages gated by `reminders`. `report_sharing` is reserved for report
# delivery notices and `marketing` for promotional messages; nothing sends the latter.
PURPOSE_FOR_KIND = {
    "remedy_due": ConsentPurpose.reminders, "remedy_missed": ConsentPurpose.reminders,
    "ending_soon": ConsentPurpose.reminders, "plan_complete": ConsentPurpose.reminders,
    "followup_due": ConsentPurpose.reminders, "report_ready": ConsentPurpose.report_sharing,
    "promotion": ConsentPurpose.marketing,
}
DEFAULT_QUIET = (time(21, 0), time(7, 0))


@dataclass(frozen=True)
class Recipient:
    channel: str
    address: str


def get_pref(db: Session, client_id: uuid.UUID) -> NotificationPref | None:
    return db.scalar(select(NotificationPref).where(NotificationPref.client_id == client_id))


def quiet_hours(pref: NotificationPref | None) -> tuple[time, time]:
    return (pref.quiet_start, pref.quiet_end) if pref else DEFAULT_QUIET


def client_language(client: Client, pref: NotificationPref | None) -> str:
    if pref and pref.language in LANGUAGES:
        return pref.language
    lang = (client.preferred_language or "en").lower()[:2]
    return lang if lang in LANGUAGES else "en"


def has_active_consent(db: Session, client_id: uuid.UUID, purpose: ConsentPurpose) -> bool:
    return db.scalar(select(Consent.id).where(
        Consent.client_id == client_id, Consent.purpose == purpose,
        Consent.withdrawn_at.is_(None)).limit(1)) is not None


def eligible_recipients(db: Session, client: Client, kind: str) -> list[Recipient]:
    """Channels this client may be sent `kind` on right now: consent for the purpose,
    per-channel opt-in, and a contact address. No pref row means nothing is sent."""
    if client.deleted_at is not None or client.erased_at is not None:
        return []
    pref = get_pref(db, client.id)
    purpose = PURPOSE_FOR_KIND.get(kind, ConsentPurpose.reminders)
    if pref is None or not has_active_consent(db, client.id, purpose):
        return []
    out: list[Recipient] = []
    if pref.email_opt_in and client.contact_email:
        out.append(Recipient("email", client.contact_email))
    if pref.whatsapp_opt_in and client.contact_phone:
        out.append(Recipient("whatsapp", client.contact_phone))
    if pref.sms_opt_in and client.contact_phone:
        out.append(Recipient("sms", client.contact_phone))
    return out


def recipient_for(db: Session, client: Client, kind: str, channel: str) -> Recipient | None:
    return next((r for r in eligible_recipients(db, client, kind) if r.channel == channel),
                None)


def template_overrides(db: Session) -> dict[tuple[str, str, str], tuple[str | None, str]]:
    return {(t.kind, t.channel, t.language): (t.subject, t.body)
            for t in db.scalars(select(NotificationTemplate))}


def first_name(client: Client) -> str:
    return (client.display_name or "").split(" ")[0] or "there"


def practice_name(db: Session) -> str:
    return db.scalar(select(Practice.name)) or "Your practitioner"


def render_for(db: Session, client: Client, kind: str, channel: str, context: dict,
               pref: NotificationPref | None = None) -> tuple[Rendered, str]:
    """Returns (rendered, language)."""
    language = client_language(client, pref)
    ctx = {"name": first_name(client), "practice": practice_name(db), **context}
    stop = links.stop_url(client.practice_id, client.id, language)
    return render_message(kind, channel, language, ctx, stop, template_overrides(db)), language


def create_notification(db: Session, *, client: Client, kind: str, channel: str,
                        dedupe_key: str, local_date: date, rendered: Rendered, language: str,
                        run_at: datetime, now: datetime, plan_id: uuid.UUID | None = None,
                        skip_reason: str | None = None) -> uuid.UUID | None:
    """Insert one outbox row idempotently and enqueue its send job. Returns the new id,
    or None when this dedupe_key already exists (nothing is enqueued twice)."""
    exists = db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key))
    if exists is not None:
        return None
    nid = uuid.uuid4()
    stmt = pg_insert(Notification).values(
        id=nid, practice_id=client.practice_id, client_id=client.id, plan_id=plan_id,
        kind=kind, channel=channel, language=language, local_date=local_date,
        dedupe_key=dedupe_key, status="skipped" if skip_reason else "pending",
        skip_reason=skip_reason, subject=rendered.subject, body=rendered.body,
        scheduled_for=run_at,
    ).on_conflict_do_nothing(constraint="uq_notification_dedupe").returning(Notification.id)
    if db.execute(stmt).scalar() is None:
        return None
    if not skip_reason:
        delay = max(0.0, (run_at - now).total_seconds())
        enqueue(db, SEND_JOB, {"notification_id": str(nid)}, practice_id=client.practice_id,
                max_attempts=5, delay_seconds=delay)
    return nid


__all__ = ["CHANNEL_KINDS", "SEND_JOB", "Recipient", "create_notification",
           "eligible_recipients", "recipient_for", "render_for"]
