"""Worker jobs: the periodic tick that creates notifications, and the sender.

`notify_tick` (enqueued every NOTIFY_TICK_SECONDS by the worker, default 300) walks
every practice in its own transaction and, for each active remedy plan:

1. applies the missed-day policy (app.notify.policy), then
2. creates outbox rows for what is due on the practice's local date:
   remedy_due (not yet done today), remedy_missed (yesterday missed; replaces the due
   message that day), ending_soon (3 days left, i.e. day 40 of 43), plan_complete
   (cycle ended; the plan itself stays active until the practitioner completes it), and
   followup_due (consultation follow_up_date is today or tomorrow).

Idempotency: every row has a dedupe_key unique per practice, e.g.
`remedy_due:<plan>:<local date>:<channel>`. Remedy reminders are one message per plan per
day (listing the items) rather than one per item, so a client with three items gets one
message and one check-in link; the key is therefore plan-level, not item-level.
Re-running the tick any number of times creates nothing new.

`notify_send` sends one outbox row. Delivery is at-least-once: a crash between the
provider accepting the message and our commit can repeat a send on retry.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app import metrics
from app.jobs import Job, enqueue
from app.tenancy.models import (
    Client,
    Consultation,
    Practice,
    RemedyCheckin,
    RemedyItem,
    RemedyPlan,
    RemedyStatus,
)
from app.tenancy.session import tenant_session

from . import links
from .channels import ChannelError, Message, get_channel
from .due import (
    ENDING_SOON_DAYS_LEFT,
    apply_quiet_hours,
    cycle_end,
    day_number,
    local_today,
    schedule_time,
)
from .models import Notification
from .policy import ACTIONS, evaluate_plan
from .service import (
    SEND_JOB,
    client_language,
    create_notification,
    eligible_recipients,
    get_pref,
    quiet_hours,
    recipient_for,
    render_for,
)
from .templates import policy_note

log = logging.getLogger("app.notify")

TICK_JOB = "notify_tick"


@dataclass
class TickStats:
    practices: int = 0
    created: int = 0
    skipped: int = 0
    errors: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)

    def add(self, kind: str, n: int) -> None:
        self.created += n
        self.by_kind[kind] = self.by_kind.get(kind, 0) + n


def _fanout(db: Session, client: Client, kind: str, key: str, local_date: date,
            context: dict, now: datetime, tz: str, hour: int,
            plan_id: uuid.UUID | None = None, day_for_schedule: date | None = None) -> int:
    """One outbox row per eligible channel. `key` is the dedupe prefix."""
    pref = get_pref(db, client.id)
    language = client_language(client, pref)
    qs, qe = quiet_hours(pref)
    made = 0
    for r in eligible_recipients(db, client, kind):
        dedupe = f"{key}:{r.channel}"
        ctx = dict(context)
        if "link_factory" in ctx:
            ctx["link"] = ctx.pop("link_factory")(language)
        rendered, language = render_for(db, client, kind, r.channel, ctx, pref)
        run_at, skip = schedule_time(now, day_for_schedule or local_date, tz, hour, qs, qe)
        if create_notification(db, client=client, kind=kind, channel=r.channel,
                               dedupe_key=dedupe, local_date=local_date, rendered=rendered,
                               language=language, run_at=run_at, now=now, plan_id=plan_id,
                               skip_reason=skip):
            made += 1
    return made


def _done_today(db: Session, plan: RemedyPlan, item_ids: list[uuid.UUID], today: date) -> bool:
    if not item_ids:
        return True
    done = set(db.scalars(select(RemedyCheckin.item_id).where(
        RemedyCheckin.item_id.in_(item_ids), RemedyCheckin.checkin_date == today,
        RemedyCheckin.done.is_(True))))
    return set(item_ids) <= done


def process_practice(db: Session, tz: str, hour: int, now: datetime,
                     stats: TickStats | None = None) -> TickStats:
    """Run the policy and create notifications for the practice bound to `db`."""
    stats = stats or TickStats()
    today = local_today(now, tz)
    yesterday = today - timedelta(days=1)
    plans = list(db.scalars(select(RemedyPlan).where(
        RemedyPlan.status == RemedyStatus.active, RemedyPlan.deleted_at.is_(None),
        RemedyPlan.start_date.is_not(None))))
    for plan in plans:
        client = db.scalar(select(Client).where(Client.id == plan.client_id))
        if client is None or client.erased_at is not None or client.deleted_at is not None:
            continue
        evaluate_plan(db, plan, today)
        end = cycle_end(plan.start_date, plan.cycle_days)
        items = list(db.execute(select(RemedyItem.id, RemedyItem.title).where(
            RemedyItem.plan_id == plan.id, RemedyItem.deleted_at.is_(None))
            .order_by(RemedyItem.sort_order, RemedyItem.created_at)))
        item_ids = [i[0] for i in items]
        base = {"plan_title": plan.title, "total": plan.cycle_days,
                "items": [i[1] for i in items]}

        def link(language: str, plan=plan, client=client) -> str:
            return links.checkin_url(plan.practice_id, client.id, plan.id, today, language, now)

        if today > end:
            n = _fanout(db, client, "plan_complete", f"plan_complete:{plan.id}", today,
                        {**base}, now, tz, hour, plan.id)
            stats.add("plan_complete", n)
            continue
        if today < plan.start_date:
            continue
        day = day_number(plan.start_date, today)
        ctx = {**base, "day": day, "days_left": (end - today).days}
        if (end - today).days == ENDING_SOON_DAYS_LEFT:
            stats.add("ending_soon", _fanout(
                db, client, "ending_soon", f"ending_soon:{plan.id}:{today}", today, ctx, now,
                tz, hour, plan.id))
        if plan.last_missed_date == yesterday:
            action = ACTIONS.get(plan.missed_day_policy, "warn")
            language = client_language(client, get_pref(db, client.id))
            mctx = {**ctx, "link_factory": link, "missed_date": yesterday.isoformat(),
                    "policy_note": policy_note(action, language, plan.cycle_days)}
            stats.add("remedy_missed", _fanout(
                db, client, "remedy_missed", f"remedy_missed:{plan.id}:{yesterday}", today,
                mctx, now, tz, hour, plan.id, day_for_schedule=today))
        elif not _done_today(db, plan, item_ids, today):
            stats.add("remedy_due", _fanout(
                db, client, "remedy_due", f"remedy_due:{plan.id}:{today}", today,
                {**ctx, "link_factory": link}, now, tz, hour, plan.id))

    consultations = db.scalars(select(Consultation).where(
        Consultation.deleted_at.is_(None), Consultation.follow_up_date.is_not(None),
        Consultation.follow_up_date >= today,
        Consultation.follow_up_date <= today + timedelta(days=1)))
    for c in list(consultations):
        client = db.scalar(select(Client).where(Client.id == c.client_id))
        if client is None:
            continue
        stats.add("followup_due", _fanout(
            db, client, "followup_due", f"followup_due:{c.id}", today,
            {"followup_date": c.follow_up_date.strftime("%d %b %Y")}, now, tz, hour))
    return stats


def list_practices(engine: Engine) -> list[tuple[uuid.UUID, str, int]]:
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, timezone, notify_hour FROM app_notify_practices()"))
        return [(r[0], r[1], r[2]) for r in rows]


def run_tick(engine: Engine, now: datetime | None = None) -> TickStats:
    now = now or datetime.now(tz=UTC)
    stats = TickStats()
    for practice_id, tz, hour in list_practices(engine):
        stats.practices += 1
        try:
            with tenant_session(engine, practice_id) as db:
                process_practice(db, tz, hour, now, stats)
        except Exception:
            stats.errors += 1
            log.exception("notify tick failed for practice %s", practice_id)
    return stats


def tick_job(job: Job, engine: Engine) -> dict:
    s = run_tick(engine)
    return {"practices": s.practices, "created": s.created, "errors": s.errors,
            "by_kind": s.by_kind}


def ensure_tick_job(engine: Engine) -> bool:
    """Enqueue a tick unless one is already queued or running (no pile-up)."""
    with engine.begin() as conn:
        res = conn.execute(text(
            "INSERT INTO job (kind, payload, max_attempts) SELECT CAST(:k AS text), '{}'::jsonb, 1 "
            "WHERE NOT EXISTS (SELECT 1 FROM job WHERE kind = :k "
            "AND status IN ('queued','running'))"), {"k": TICK_JOB})
        return res.rowcount == 1


# -------------------------------------------------------------------- sending
def send_job(job: Job, engine: Engine) -> dict:
    nid = uuid.UUID(job.payload["notification_id"])
    with tenant_session(engine, job.practice_id) as db:
        n = db.get(Notification, nid)
        if n is None or n.status != "pending":
            return {"skipped": "not pending"}
        client = db.scalar(select(Client).where(Client.id == n.client_id))
        rcpt = recipient_for(db, client, n.kind, n.channel) if client else None
        if rcpt is None:  # consent withdrawn or opted out since scheduling
            n.status, n.skip_reason = "skipped", "not_eligible"
            return {"skipped": "not eligible"}
        channel = get_channel(n.channel)
        if n.channel != "email" and channel.name != "console":
            # Retries and backlog can land a send inside quiet hours: push it to the end
            # of the window instead of messaging someone at night.
            pref = get_pref(db, client.id)
            qs, qe = quiet_hours(pref)
            now = datetime.now(tz=UTC)
            tz = db.scalar(select(Practice.timezone))
            later = apply_quiet_hours(now, tz, qs, qe)
            if later > now:
                enqueue(db, SEND_JOB, job.payload, practice_id=job.practice_id,
                        max_attempts=5, delay_seconds=(later - now).total_seconds())
                return {"deferred": "quiet_hours"}
        stop = links.stop_url(n.practice_id, n.client_id, n.language)
        try:
            result = channel.send(Message(
                to=rcpt.address, body=n.body, subject=n.subject, language=n.language,
                unsubscribe_url=stop, kind=n.kind))
        except ChannelError as exc:
            if exc.retryable:
                raise
            n.status, n.attempts = "failed", job.attempts
            n.last_error, n.provider = str(exc)[:500], channel.name
            return {"failed": n.channel}
        n.status, n.sent_at, n.attempts = "sent", datetime.now(tz=UTC), job.attempts
        n.provider, n.provider_message_id, n.last_error = (
            result.provider, result.message_id, None)
        n.delivery_status = "sent" if n.provider != "console" else None
    return {"sent": n.channel}


def send_failed(job: Job, engine: Engine, err: str, final: bool) -> None:
    if job.practice_id is None:
        return
    with tenant_session(engine, job.practice_id) as db:
        n = db.get(Notification, uuid.UUID(job.payload["notification_id"]))
        if n is None or n.status != "pending":
            return
        metrics.notification_failures.add(1, {"channel": n.channel, "final": str(final).lower()})
        n.attempts = job.attempts
        n.last_error = err.split(":")[0][:200] + (" (will retry)" if not final else "")
        if final:
            n.status = "failed"


__all__ = ["SEND_JOB", "TICK_JOB", "ensure_tick_job", "process_practice", "run_tick",
           "send_failed", "send_job", "tick_job"]
