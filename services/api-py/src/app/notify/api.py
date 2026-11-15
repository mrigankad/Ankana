"""/v1 routes for reminders: outbox, resend, template preview and editing, practice
settings, per-client preferences, and the "Needs you" feed."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.jobs import enqueue
from app.tenancy.models import (
    Client,
    ConsentPurpose,
    Consultation,
    Practice,
    RemedyItem,
    RemedyPlan,
    RemedyStatus,
    Role,
)
from app.v1.common import CLINICAL, STAFF, ProblemError, audit, load_client, paginate

from . import due
from .models import KINDS, LANGUAGES, Notification, NotificationPref, NotificationTemplate
from .service import (
    SEND_JOB,
    client_language,
    eligible_recipients,
    get_pref,
    has_active_consent,
    quiet_hours,
    recipient_for,
    template_overrides,
)
from .templates import (
    ALLOWED_VARIABLES,
    DEFAULTS,
    SAMPLE_CONTEXT,
    TemplateError,
    render_message,
    validate_template,
)

router = APIRouter()
Kind = Literal["remedy_due", "remedy_missed", "ending_soon", "plan_complete", "followup_due"]
ChannelName = Literal["email", "whatsapp", "sms"]
Lang = Literal["en", "hi"]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(_Out):
    id: uuid.UUID
    client_id: uuid.UUID
    plan_id: uuid.UUID | None
    kind: str
    channel: str
    language: str
    local_date: date
    status: str
    skip_reason: str | None
    subject: str | None
    body: str
    scheduled_for: datetime
    sent_at: datetime | None
    attempts: int
    resend_count: int
    last_error: str | None
    provider: str | None
    delivery_status: str | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    delivery_error: str | None = None
    created_at: datetime


class NotificationPage(BaseModel):
    notifications: list[NotificationOut]
    next_cursor: str | None = None


class NotificationEnvelope(BaseModel):
    notification: NotificationOut


# ------------------------------------------------------------------- outbox
@router.get("/notifications", response_model=NotificationPage, tags=["notifications"],
            operation_id="listNotifications",
            summary="Outbox: reminders sent, pending, failed or skipped (newest first)")
def list_notifications(
        status: Literal["pending", "sent", "failed", "skipped", "cancelled"] | None = None,
        client_id: uuid.UUID | None = None, kind: Kind | None = None,
        limit: int = Query(default=50, ge=1, le=200), cursor: str | None = None,
        m: CurrentMember = Depends(require_roles(*STAFF)), db: Session = Depends(tenant_db, scope="function")):
    stmt = select(Notification)
    if status:
        stmt = stmt.where(Notification.status == status)
    if client_id:
        stmt = stmt.where(Notification.client_id == client_id)
    if kind:
        stmt = stmt.where(Notification.kind == kind)
    rows, nxt = paginate(db, stmt, Notification, limit, cursor)
    return {"notifications": rows, "next_cursor": nxt}


@router.post("/notifications/{notification_id}/resend", response_model=NotificationEnvelope,
             tags=["notifications"], operation_id="resendNotification",
             summary="Send an outbox row again now (needs current consent and opt-in)")
def resend_notification(notification_id: uuid.UUID, request: Request,
                        m: CurrentMember = Depends(require_roles(*STAFF)),
                        db: Session = Depends(tenant_db, scope="function")):
    n = db.get(Notification, notification_id)
    if n is None:
        raise ProblemError(404, "notification not found", "not_found")
    if n.status == "pending":
        raise ProblemError(409, "notification is already queued", "invalid_state")
    client = db.scalar(select(Client).where(Client.id == n.client_id))
    if client is None or recipient_for(db, client, n.kind, n.channel) is None:
        raise ProblemError(409, "client has not consented to, or opted in for, this channel",
                           "consent_required")
    n.status, n.skip_reason, n.last_error = "pending", None, None
    n.resend_count += 1
    n.scheduled_for = datetime.now(tz=UTC)
    db.flush()
    enqueue(db, SEND_JOB, {"notification_id": str(n.id)}, practice_id=n.practice_id,
            max_attempts=5)
    audit(db, m, "notification.resent", "notification", n.id, request)
    db.refresh(n)
    return {"notification": n}


# ------------------------------------------------------------------ templates
class TemplateIn(BaseModel):
    kind: Kind
    channel: Literal["*", "email", "whatsapp", "sms"] = "*"
    language: Lang
    subject: str | None = Field(default=None, max_length=300)
    body: str = Field(min_length=1, max_length=3000)


class TemplateOut(BaseModel):
    kind: str
    channel: str
    language: str
    subject: str | None
    body: str
    source: Literal["default", "practice"]


class TemplateList(BaseModel):
    templates: list[TemplateOut]
    variables: dict[str, str]


def _templates(db: Session) -> list[dict]:
    custom = {(t.kind, t.channel, t.language): t for t in db.scalars(select(NotificationTemplate))}
    out = []
    for kind in KINDS:
        for lang in LANGUAGES:
            subject, body = DEFAULTS[(kind, lang)]
            out.append({"kind": kind, "channel": "*", "language": lang, "subject": subject,
                        "body": body, "source": "default"})
    keys = {(t["kind"], t["channel"], t["language"]) for t in out}
    for (kind, channel, lang), t in sorted(custom.items()):
        row = {"kind": kind, "channel": channel, "language": lang, "subject": t.subject,
               "body": t.body, "source": "practice"}
        if (kind, channel, lang) in keys:
            out = [row if (o["kind"], o["channel"], o["language"]) == (kind, channel, lang)
                   else o for o in out]
        else:
            out.append(row)
    return out


@router.get("/notification-templates", response_model=TemplateList, tags=["notifications"],
            operation_id="listNotificationTemplates",
            summary="Templates in effect (defaults plus this practice's edits) and the "
                    "variables a template may use")
def list_templates(m: CurrentMember = Depends(require_roles(*STAFF)),
                   db: Session = Depends(tenant_db, scope="function")):
    return {"templates": _templates(db), "variables": ALLOWED_VARIABLES}


@router.put("/notification-templates", response_model=TemplateOut, tags=["notifications"],
            operation_id="upsertNotificationTemplate",
            summary="Create or replace a practice template (validated in a Jinja2 sandbox)")
def upsert_template(body: TemplateIn, request: Request,
                    m: CurrentMember = Depends(require_roles(*CLINICAL)),
                    db: Session = Depends(tenant_db, scope="function")):
    try:
        validate_template(body.subject, body.body)
    except TemplateError as exc:
        raise ProblemError(422, str(exc), "invalid_template") from None
    row = db.scalar(select(NotificationTemplate).where(
        NotificationTemplate.kind == body.kind, NotificationTemplate.channel == body.channel,
        NotificationTemplate.language == body.language))
    if row is None:
        row = NotificationTemplate(practice_id=m.practice_id, kind=body.kind,
                                   channel=body.channel, language=body.language, body=body.body)
        db.add(row)
    row.subject, row.body, row.updated_by_member_id = body.subject, body.body, m.member_id
    db.flush()
    audit(db, m, "notification_template.saved", "notification_template", row.id, request,
          meta={"kind": body.kind, "channel": body.channel, "language": body.language})
    return {"kind": row.kind, "channel": row.channel, "language": row.language,
            "subject": row.subject, "body": row.body, "source": "practice"}


@router.delete("/notification-templates", status_code=204, tags=["notifications"],
               operation_id="resetNotificationTemplate",
               summary="Delete a practice template so the default applies again")
def reset_template(kind: Kind, language: Lang, request: Request,
                   channel: Literal["*", "email", "whatsapp", "sms"] = "*",
                   m: CurrentMember = Depends(require_roles(*CLINICAL)),
                   db: Session = Depends(tenant_db, scope="function")):
    row = db.scalar(select(NotificationTemplate).where(
        NotificationTemplate.kind == kind, NotificationTemplate.channel == channel,
        NotificationTemplate.language == language))
    if row is None:
        raise ProblemError(404, "no practice template to reset", "not_found")
    db.delete(row)
    audit(db, m, "notification_template.reset", "notification_template", row.id, request)


class PreviewIn(BaseModel):
    kind: Kind
    channel: ChannelName = "email"
    language: Lang = "en"
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=3000,
                             description="Draft body to preview instead of the saved template")
    client_id: uuid.UUID | None = Field(
        default=None, description="Use this client's first name; otherwise a sample name")


class PreviewOut(BaseModel):
    subject: str | None
    body: str
    source: Literal["default", "practice", "draft"]


@router.post("/notification-preview", response_model=PreviewOut, tags=["notifications"],
             operation_id="previewNotificationTemplate",
             summary="Render a template with sample data (nothing is sent or stored)")
def preview_template(body: PreviewIn, m: CurrentMember = Depends(require_roles(*STAFF)),
                     db: Session = Depends(tenant_db, scope="function")):
    ctx: dict[str, Any] = {**SAMPLE_CONTEXT, "practice": db.scalar(select(Practice.name)) or ""}
    if body.client_id:
        ctx["name"] = (load_client(db, m, body.client_id).display_name or "").split(" ")[0]
    overrides = template_overrides(db)
    if body.body is not None:
        overrides = {(body.kind, body.channel, body.language): (body.subject, body.body)}
    try:
        r = render_message(body.kind, body.channel, body.language, ctx,
                           "https://example.test/v1/public/stop/SAMPLE", overrides)
    except TemplateError as exc:
        raise ProblemError(422, str(exc), "invalid_template") from None
    return {"subject": r.subject, "body": r.body,
            "source": "draft" if body.body is not None else r.source}


# ------------------------------------------------------------------ settings
class SettingsIn(BaseModel):
    timezone: str | None = Field(default=None, max_length=64, description="IANA zone")
    notify_hour: int | None = Field(default=None, ge=0, le=23,
                                    description="Local hour for daily reminders")
    notify_enabled: bool | None = None


class SettingsOut(_Out):
    timezone: str
    notify_hour: int
    notify_enabled: bool


@router.get("/notification-settings", response_model=SettingsOut, tags=["notifications"],
            operation_id="getNotificationSettings", summary="Practice reminder settings")
def get_settings(m: CurrentMember = Depends(require_roles(*STAFF)),
                 db: Session = Depends(tenant_db, scope="function")):
    return db.scalar(select(Practice))


@router.put("/notification-settings", response_model=SettingsOut, tags=["notifications"],
            operation_id="updateNotificationSettings",
            summary="Set the practice time zone, daily reminder hour, or pause reminders")
def update_settings(body: SettingsIn, request: Request,
                    m: CurrentMember = Depends(require_roles(Role.owner)),
                    db: Session = Depends(tenant_db, scope="function")):
    practice = db.scalar(select(Practice))
    if body.timezone is not None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ProblemError(422, "unknown IANA time zone", "validation_error") from None
        practice.timezone = body.timezone
    if body.notify_hour is not None:
        practice.notify_hour = body.notify_hour
    if body.notify_enabled is not None:
        practice.notify_enabled = body.notify_enabled
    db.flush()
    audit(db, m, "notification_settings.updated", "practice", practice.id, request)
    return practice


# --------------------------------------------------------------- preferences
class PrefIn(BaseModel):
    email_opt_in: bool | None = None
    whatsapp_opt_in: bool | None = None
    sms_opt_in: bool | None = None
    quiet_start: time | None = None
    quiet_end: time | None = None
    language: Lang | None = None


class PrefOut(BaseModel):
    email_opt_in: bool
    whatsapp_opt_in: bool
    sms_opt_in: bool
    quiet_start: time
    quiet_end: time
    language: str
    reminders_consent: bool = Field(
        description="Active 'reminders' consent; without it nothing is sent")
    eligible_channels: list[str]


def _pref_out(db: Session, client: Client) -> dict:
    pref = get_pref(db, client.id)
    qs, qe = quiet_hours(pref)
    return {
        "email_opt_in": bool(pref and pref.email_opt_in),
        "whatsapp_opt_in": bool(pref and pref.whatsapp_opt_in),
        "sms_opt_in": bool(pref and pref.sms_opt_in),
        "quiet_start": qs, "quiet_end": qe, "language": client_language(client, pref),
        "reminders_consent": has_active_consent(db, client.id, ConsentPurpose.reminders),
        "eligible_channels": [r.channel for r in eligible_recipients(db, client, "remedy_due")],
    }


@router.get("/clients/{client_id}/notification-prefs", response_model=PrefOut,
            tags=["notifications"], operation_id="getNotificationPrefs",
            summary="Reminder channels, quiet hours and language for a client")
def get_prefs(client_id: uuid.UUID, m: CurrentMember = Depends(require_roles(*STAFF)),
              db: Session = Depends(tenant_db, scope="function")):
    return _pref_out(db, load_client(db, m, client_id))


@router.put("/clients/{client_id}/notification-prefs", response_model=PrefOut,
            tags=["notifications"], operation_id="updateNotificationPrefs",
            summary="Set per-channel opt-in, quiet hours and language. Sending also needs an "
                    "active 'reminders' consent")
def update_prefs(client_id: uuid.UUID, body: PrefIn, request: Request,
                 m: CurrentMember = Depends(require_roles(*STAFF)),
                 db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    pref = get_pref(db, client.id)
    if pref is None:
        pref = NotificationPref(practice_id=m.practice_id, client_id=client.id,
                                email_opt_in=False, whatsapp_opt_in=False, sms_opt_in=False,
                                quiet_start=time(21, 0), quiet_end=time(7, 0))
        db.add(pref)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(pref, k, v)
    db.flush()
    audit(db, m, "notification_prefs.updated", "client", client.id, request,
          meta={"client_id": str(client.id)})
    return _pref_out(db, client)


# ----------------------------------------------------------------- needs you
class NeedsYouOut(BaseModel):
    today: date
    followups: list[dict]
    missed_remedies: list[dict]
    ended_plans: list[dict]
    failed_notifications: list[dict]


@router.get("/needs-you", response_model=NeedsYouOut, tags=["notifications"],
            operation_id="getNeedsYou",
            summary="What waits on the practitioner: due follow-ups, missed remedies, plans "
                    "past their last day, failed sends")
def needs_you(m: CurrentMember = Depends(require_roles(*STAFF)),
              db: Session = Depends(tenant_db, scope="function")):
    practice = db.scalar(select(Practice))
    today = due.local_today(datetime.now(tz=UTC), practice.timezone)
    names = {c.id: c.display_name for c in db.scalars(select(Client).where(
        Client.deleted_at.is_(None)))}

    followups = []
    for c in db.scalars(select(Consultation).where(
            Consultation.deleted_at.is_(None), Consultation.follow_up_date.is_not(None),
            Consultation.follow_up_date <= today + timedelta(days=3),
            Consultation.follow_up_date >= today - timedelta(days=30))
            .order_by(Consultation.follow_up_date)):
        if c.client_id not in names:
            continue
        seen = db.scalar(select(func.count()).select_from(Consultation).where(
            Consultation.client_id == c.client_id, Consultation.deleted_at.is_(None),
            Consultation.id != c.id, func.date(Consultation.consulted_at) >= c.follow_up_date))
        if seen:
            continue  # the follow-up already happened
        followups.append({
            "consultation_id": str(c.id), "client_id": str(c.client_id),
            "client_name": names[c.client_id], "follow_up_date": c.follow_up_date.isoformat(),
            "days_overdue": max(0, (today - c.follow_up_date).days), "topic": c.topic})

    missed, ended = [], []
    for p in db.scalars(select(RemedyPlan).where(
            RemedyPlan.status == RemedyStatus.active, RemedyPlan.deleted_at.is_(None),
            RemedyPlan.start_date.is_not(None))):
        if p.client_id not in names:
            continue
        base = {"plan_id": str(p.id), "client_id": str(p.client_id),
                "client_name": names[p.client_id], "title": p.title}
        end = due.cycle_end(p.start_date, p.cycle_days)
        if today > end:
            ended.append({**base, "end_date": end.isoformat()})
        elif p.last_missed_date and p.last_missed_date >= today - timedelta(days=2):
            items = db.scalar(select(func.count()).select_from(RemedyItem).where(
                RemedyItem.plan_id == p.id, RemedyItem.deleted_at.is_(None)))
            missed.append({
                **base, "last_missed_date": p.last_missed_date.isoformat(),
                "missed_days": p.missed_days, "policy": p.missed_day_policy,
                "restart_count": p.restart_count, "extended_days": p.extended_days,
                "day_number": max(1, due.day_number(p.start_date, today)),
                "total_days": p.cycle_days, "item_count": items})

    failed = [{
        "id": str(n.id), "client_id": str(n.client_id), "client_name": names.get(n.client_id),
        "kind": n.kind, "channel": n.channel, "last_error": n.last_error,
        "created_at": n.created_at.isoformat()}
        for n in db.scalars(select(Notification).where(Notification.status == "failed")
                            .order_by(Notification.created_at.desc()).limit(50))]
    return {"today": today, "followups": followups, "missed_remedies": missed,
            "ended_plans": ended, "failed_notifications": failed}


__all__ = ["router"]
