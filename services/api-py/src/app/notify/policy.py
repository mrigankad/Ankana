"""Missed-day policy enforcement for active remedy plans.

A day is missed when it falls inside the cycle, is before today (practice-local), and
not every live item has a done check-in for it. Days are judged once, in order:
`evaluated_through` records the last judged day, so repeated ticks and catch-up after
downtime are idempotent.

Policies (RemedyPlan.missed_day_policy)
- restart: the cycle starts again the day after the missed day (start_date moves, so
  the client resumes at day 1; older check-ins no longer count).
- extend: the cycle gets one more day (cycle_days and extended_days +1).
- warn / ignore: nothing changes on the plan; the miss is recorded and surfaced.
Every outcome writes an audit_event (no actor) and stamps missed_days / last_missed_date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tenancy.models import AuditEvent, RemedyCheckin, RemedyItem, RemedyPlan, RemedyStatus

from .due import cycle_end

ACTIONS = {"restart": "restart", "extend": "extend", "warn": "warn", "ignore": "warn"}


@dataclass
class PolicyResult:
    missed_dates: list[date] = field(default_factory=list)
    action: str | None = None  # restart | extend | warn (of the most recent miss)
    missed_last_day: bool = False  # yesterday was missed in this evaluation


def evaluate_plan(db: Session, plan: RemedyPlan, today: date) -> PolicyResult:
    result = PolicyResult()
    if plan.status != RemedyStatus.active or plan.start_date is None:
        return result
    last_day = today - timedelta(days=1)
    first = plan.start_date
    if plan.evaluated_through is not None:
        first = max(first, plan.evaluated_through + timedelta(days=1))
    if first > last_day:
        return result

    item_ids = set(db.scalars(select(RemedyItem.id).where(
        RemedyItem.plan_id == plan.id, RemedyItem.deleted_at.is_(None))))
    done: dict[date, set] = {}
    if item_ids:
        for item_id, day in db.execute(select(RemedyCheckin.item_id, RemedyCheckin.checkin_date)
                                       .where(RemedyCheckin.item_id.in_(item_ids),
                                              RemedyCheckin.done.is_(True),
                                              RemedyCheckin.checkin_date >= plan.start_date,
                                              RemedyCheckin.checkin_date <= last_day)):
            done.setdefault(day, set()).add(item_id)

    policy = ACTIONS.get(plan.missed_day_policy, "warn")
    d = first
    while d <= last_day:
        if d < plan.start_date:  # a restart moved the start past this day
            d += timedelta(days=1)
            continue
        if d > cycle_end(plan.start_date, plan.cycle_days):
            break
        if not item_ids or item_ids <= done.get(d, set()):
            d += timedelta(days=1)
            continue
        result.missed_dates.append(d)
        result.action = policy
        plan.missed_days += 1
        plan.last_missed_date = d
        meta = {"plan_id": str(plan.id), "date": d.isoformat(), "policy": policy}
        if policy == "restart":
            plan.start_date = d + timedelta(days=1)
            plan.restart_count += 1
            meta["new_start_date"] = plan.start_date.isoformat()
        elif policy == "extend":
            plan.cycle_days += 1
            plan.extended_days += 1
            meta["cycle_days"] = plan.cycle_days
        db.add(AuditEvent(practice_id=plan.practice_id, action=f"remedy_plan.missed_{policy}",
                          entity_type="remedy_plan", entity_id=str(plan.id), meta=meta))
        d += timedelta(days=1)

    plan.evaluated_through = last_day
    result.missed_last_day = bool(result.missed_dates) and result.missed_dates[-1] == last_day
    db.flush()
    return result
