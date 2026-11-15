"""Applying webhook events to the database: delivery status and STOP replies.

Webhooks carry no tenant, so two lookups cross tenants: the outbox row by
(provider, provider_message_id) through the SECURITY DEFINER function
app_notification_by_provider, and clients by phone by walking the practices (the phone
blind index is keyed per practice, so it cannot be searched globally).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime

from sqlalchemy import text, update
from sqlalchemy.engine import Engine

from app.tenancy.models import AuditEvent, Consent, ConsentPurpose
from app.tenancy.session import global_session, tenant_session

from .base import InboundEvent, StatusEvent, should_apply

# Case-insensitive, whole-message match after trimming punctuation. TRAI and Meta both
# expect STOP; the Hindi word is what a Hindi-speaking client is likely to type.
OPT_OUT_KEYWORDS = frozenset({"stop", "stopall", "unsubscribe", "cancel", "end", "quit",
                              "optout", "opt out", "बंद", "बंद करें", "रोकें"})
_CHANNEL_FIELD = {"sms": "sms_opt_in", "whatsapp": "whatsapp_opt_in"}
_PROVIDER_CHANNEL = {"meta": "whatsapp", "gupshup": "whatsapp", "msg91": "sms", "twilio": "sms"}


def is_opt_out(text_: str) -> bool:
    # drop punctuation and symbols only: Devanagari vowel signs are marks, not letters
    cleaned = "".join(c for c in text_ if unicodedata.category(c)[0] not in "PS").strip().lower()
    return re.sub(r"\s+", " ", cleaned) in OPT_OUT_KEYWORDS


def apply_status(engine: Engine, ev: StatusEvent, now: datetime | None = None) -> bool:
    """Record a delivery receipt on the outbox row. True when a row changed."""
    from app.notify.models import Notification

    with global_session(engine) as db:
        row = db.execute(text("SELECT practice_id, id FROM app_notification_by_provider(:p, :m)"),
                         {"p": ev.provider, "m": ev.message_id}).first()
    if row is None:
        return False
    now = now or datetime.now(tz=UTC)
    with tenant_session(engine, row.practice_id) as db:
        n = db.get(Notification, row.id)
        if n is None or not should_apply(n.delivery_status, ev.status):
            return False
        n.delivery_status = ev.status
        if ev.status == "delivered":
            n.delivered_at = n.delivered_at or now
        elif ev.status == "read":
            n.delivered_at = n.delivered_at or now
            n.read_at = now
        elif ev.status == "failed":
            n.delivery_error = (ev.error or "failed")[:200]
    return True


def apply_opt_out(engine: Engine, ev: InboundEvent) -> int:
    """STOP reply: switch the channel off for every client with this phone, in every
    practice, cancel its pending sends and withdraw `reminders` consent once no channel is
    left. Returns the number of clients changed."""
    from app.notify.models import Notification, NotificationPref
    from app.privacy.blind import find_clients

    channel = _PROVIDER_CHANNEL.get(ev.provider)
    if channel is None or not is_opt_out(ev.text):
        return 0
    with global_session(engine) as db:
        practices = [r[0] for r in db.execute(text("SELECT practice_id FROM privacy_practices()"))]
    now = datetime.now(tz=UTC)
    changed = 0
    for pid in practices:
        with tenant_session(engine, pid) as db:
            clients = find_clients(db, phone=ev.sender)
            for client in clients:
                pref = db.query(NotificationPref).filter_by(client_id=client.id).one_or_none()
                if pref is not None:
                    setattr(pref, _CHANNEL_FIELD[channel], False)
                    left = pref.email_opt_in or pref.whatsapp_opt_in or pref.sms_opt_in
                else:
                    left = False
                if not left:
                    db.execute(update(Consent).where(
                        Consent.client_id == client.id,
                        Consent.purpose == ConsentPurpose.reminders,
                        Consent.withdrawn_at.is_(None)).values(withdrawn_at=now))
                db.execute(update(Notification).where(
                    Notification.client_id == client.id, Notification.status == "pending",
                    Notification.channel == channel)
                    .values(status="cancelled", skip_reason="client_stopped"))
                db.add(AuditEvent(practice_id=uuid.UUID(str(pid)),
                                  action="notification.stopped_by_reply",
                                  entity_type="client", entity_id=str(client.id),
                                  meta={"channel": channel, "provider": ev.provider}))
                changed += 1
    return changed
