"""Public, login-free pages reached from a reminder: one-tap "done today" and "stop".

The signed token is the credential. GET only renders a confirmation page (link
prefetchers and mail scanners must not change state); the button POSTs. Both are rate
limited per IP and per token with the shared Postgres limiter (app.ratelimit), so the
limit holds across API replicas.
"""

from __future__ import annotations

import html
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.ratelimit import MemoryWindow as RateLimiter  # noqa: F401  (kept for importers)
from app.ratelimit import SharedRateLimiter, client_ip
from app.tenancy.models import (
    AuditEvent,
    Consent,
    ConsentPurpose,
    RemedyCheckin,
    RemedyItem,
    RemedyPlan,
    RemedyStatus,
)
from app.tenancy.session import tenant_session

from . import links
from .due import cycle_end
from .links import LinkError
from .models import Notification, NotificationPref

router = APIRouter()


IP_LIMIT = SharedRateLimiter("public_link_ip", 30, 60)
TOKEN_LIMIT = SharedRateLimiter("public_link_token", 6, 60)

_T = {
    "en": {
        "done_title": "Mark today as done", "button": "I did it today",
        "thanks": "Noted. Thank you.", "again": "Today is already marked done.",
        "expired": "This link has expired. Please ask your practitioner for a new reminder.",
        "invalid": "This link is not valid.", "inactive": "This remedy plan is not active.",
        "slow": "Too many attempts. Please wait a minute and try again.",
        "stop_title": "Stop reminders", "stop_btn": "Stop all reminders",
        "stopped": "Reminders stopped. You will not receive more.",
        "stop_text": "You will no longer get reminders from this practice.",
        "advice": ("This is traditional guidance, not medical, legal or financial advice."),
    },
    "hi": {
        "done_title": "आज का दिन चिह्नित करें", "button": "मैंने आज कर लिया",
        "thanks": "दर्ज हो गया। धन्यवाद।", "again": "आज का दिन पहले ही चिह्नित है।",
        "expired": "यह लिंक समाप्त हो गया है। कृपया अपने प्रैक्टिशनर से नया संदेश माँगें।",
        "invalid": "यह लिंक मान्य नहीं है।", "inactive": "यह उपाय योजना सक्रिय नहीं है।",
        "slow": "बहुत अधिक प्रयास। कृपया एक मिनट रुककर फिर प्रयास करें।",
        "stop_title": "संदेश बंद करें", "stop_btn": "सभी संदेश बंद करें",
        "stopped": "संदेश बंद कर दिए गए। अब आपको नहीं मिलेंगे।",
        "stop_text": "आपको इस प्रैक्टिस से अब संदेश नहीं मिलेंगे।",
        "advice": "यह पारंपरिक मार्गदर्शन है, चिकित्सा, कानूनी या वित्तीय सलाह नहीं।",
    },
}

_PAGE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{title}</title>
<style>body{{margin:0;background:#FEF9F7;color:#221E1D;font:17px/1.5 system-ui,sans-serif;
display:flex;min-height:100vh;align-items:center;justify-content:center}}
main{{background:#fff;border:1px solid #EAE5E3;border-radius:14px;padding:28px;max-width:420px;
margin:16px;box-shadow:0 6px 18px rgba(34,30,29,.06)}}h1{{font-size:22px;margin:0 0 12px}}
ul{{padding-left:20px}}button{{width:100%;background:#D32704;color:#fff;border:0;border-radius:10px;
padding:16px;font:700 18px system-ui;cursor:pointer}}small{{display:block;margin-top:18px;
color:#6C6866}}</style></head><body><main><h1>{title}</h1>{body}<small>{advice}</small>
</main></body></html>"""


def _page(lang: str, title: str, body: str, status: int = 200) -> HTMLResponse:
    t = _T.get(lang, _T["en"])
    return HTMLResponse(
        _PAGE.format(lang=lang, title=html.escape(title), body=body, advice=t["advice"]),
        status_code=status,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


def _msg(lang: str, key: str, status: int = 200, title_key: str | None = None) -> HTMLResponse:
    t = _T.get(lang, _T["en"])
    return _page(lang, t[title_key or key] if (title_key or key) in t else t["invalid"],
                 f"<p>{html.escape(t[key])}</p>", status)


def _guard(request: Request, token: str, mutate: bool) -> bool:
    engine = getattr(request.app.state, "pg_engine", None)
    ok = IP_LIMIT.allow(engine, client_ip(request))
    if mutate:
        ok = TOKEN_LIMIT.allow(engine, token[:64]) and ok
    return ok


def _open(token: str, purpose: str) -> tuple[dict | None, HTMLResponse | None]:
    try:
        return links.verify(token, purpose), None
    except LinkError as exc:
        return None, _msg("en", "expired" if exc.code == "expired" else "invalid", 410
                          if exc.code == "expired" else 400, "invalid")


def _plan_state(db, data: dict) -> tuple[RemedyPlan | None, list[RemedyItem], date]:
    day = date.fromisoformat(data["d"])
    plan = db.scalar(select(RemedyPlan).where(
        RemedyPlan.id == uuid.UUID(data["pl"]), RemedyPlan.client_id == uuid.UUID(data["c"]),
        RemedyPlan.deleted_at.is_(None)))
    ok = (plan is not None and plan.status == RemedyStatus.active and plan.start_date
          and plan.start_date <= day <= cycle_end(plan.start_date, plan.cycle_days))
    items = list(db.scalars(select(RemedyItem).where(
        RemedyItem.plan_id == plan.id, RemedyItem.deleted_at.is_(None))
        .order_by(RemedyItem.sort_order))) if ok else []
    return (plan if ok else None), items, day


@router.get("/public/checkin/{token}", response_class=HTMLResponse, tags=["public-links"],
            operation_id="showCheckinPage", summary="One-tap 'done today' page (signed link)")
def checkin_page(token: str, request: Request):
    if not _guard(request, token, False):
        return _msg("en", "slow", 429, "invalid")
    data, err = _open(token, "checkin")
    if err:
        return err
    lang = data.get("l", "en")
    with tenant_session(request.app.state.pg_engine, data["p"]) as db:
        plan, items, day = _plan_state(db, data)
        if plan is None:
            return _msg(lang, "inactive", 410, "invalid")
        done = set(db.scalars(select(RemedyCheckin.item_id).where(
            RemedyCheckin.item_id.in_([i.id for i in items]),
            RemedyCheckin.checkin_date == day, RemedyCheckin.done.is_(True))))
        t = _T.get(lang, _T["en"])
        lis = "".join(f"<li>{html.escape(i.title)}</li>" for i in items)
        if items and {i.id for i in items} <= done:
            return _page(lang, t["done_title"], f"<p>{html.escape(t['again'])}</p>")
        body = (f"<p>{html.escape(plan.title)}</p><ul>{lis}</ul>"
                f"<form method='post'><button type='submit'>{html.escape(t['button'])}"
                "</button></form>")
        return _page(lang, t["done_title"], body)


@router.post("/public/checkin/{token}", response_class=HTMLResponse, tags=["public-links"],
             operation_id="submitCheckin",
             summary="Record every item of the plan as done for the link's day")
def checkin_submit(token: str, request: Request):
    if not _guard(request, token, True):
        return _msg("en", "slow", 429, "invalid")
    data, err = _open(token, "checkin")
    if err:
        return err
    lang = data.get("l", "en")
    with tenant_session(request.app.state.pg_engine, data["p"]) as db:
        plan, items, day = _plan_state(db, data)
        if plan is None:
            return _msg(lang, "inactive", 410, "invalid")
        for item in items:
            db.execute(pg_insert(RemedyCheckin).values(
                practice_id=plan.practice_id, item_id=item.id, checkin_date=day, done=True,
            ).on_conflict_do_update(index_elements=["item_id", "checkin_date"],
                                    set_={"done": True}))
        db.add(AuditEvent(practice_id=plan.practice_id, action="remedy_checkin.link",
                          entity_type="remedy_plan", entity_id=str(plan.id),
                          ip=request.client.host if request.client else None,
                          meta={"date": day.isoformat(), "items": len(items)}))
    return _msg(lang, "thanks", 200, "done_title")


@router.get("/public/stop/{token}", response_class=HTMLResponse, tags=["public-links"],
            operation_id="showStopPage", summary="Confirm page to stop reminders (signed link)")
def stop_page(token: str, request: Request):
    if not _guard(request, token, False):
        return _msg("en", "slow", 429, "invalid")
    data, err = _open(token, "stop")
    if err:
        return err
    lang = data.get("l", "en")
    t = _T.get(lang, _T["en"])
    body = (f"<p>{html.escape(t['stop_text'])}</p><form method='post'><button type='submit'>"
            f"{html.escape(t['stop_btn'])}</button></form>")
    return _page(lang, t["stop_title"], body)


@router.post("/public/stop/{token}", response_class=HTMLResponse, tags=["public-links"],
             operation_id="submitStop",
             summary="Withdraw reminders consent, switch every channel off, cancel pending sends")
def stop_submit(token: str, request: Request):
    if not _guard(request, token, True):
        return _msg("en", "slow", 429, "invalid")
    data, err = _open(token, "stop")
    if err:
        return err
    lang = data.get("l", "en")
    client_id = uuid.UUID(data["c"])
    now = datetime.now(tz=UTC)
    with tenant_session(request.app.state.pg_engine, data["p"]) as db:
        db.execute(update(NotificationPref).where(NotificationPref.client_id == client_id)
                   .values(email_opt_in=False, whatsapp_opt_in=False, sms_opt_in=False))
        db.execute(update(Consent).where(
            Consent.client_id == client_id, Consent.purpose == ConsentPurpose.reminders,
            Consent.withdrawn_at.is_(None)).values(withdrawn_at=now))
        db.execute(update(Notification).where(
            Notification.client_id == client_id, Notification.status == "pending")
            .values(status="cancelled", skip_reason="client_stopped"))
        db.add(AuditEvent(practice_id=uuid.UUID(data["p"]), action="notification.stopped",
                          entity_type="client", entity_id=str(client_id),
                          ip=request.client.host if request.client else None))
    return _msg(lang, "stopped", 200, "stop_title")
