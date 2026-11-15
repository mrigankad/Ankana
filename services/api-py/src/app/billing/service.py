"""Billing domain logic (no HTTP): effective plan, entitlement checks, checkout,
cancel, webhook event handling and invoice issue.

Subscription state machine (one row per provider subscription):
  created   checkout link issued, nothing paid yet; grants nothing
  active    paid; grants its plan until current_period_end (+ grace slack, in case a
            renewal webhook is late)
  past_due  a charge failed; keeps its plan until grace_until (default 7 days)
  halted    provider gave up retrying; same grace rule, then the practice is on Free
  cancelled grants its plan only until ended_at (set when the provider reports the
            end of the cycle); 'cancel at period end' keeps status active and sets
            cancel_at_period_end until that event arrives
Downgrades: never immediate and never destructive. To move to a cheaper plan the
owner cancels at period end and subscribes to the lower plan afterwards (checkout
refuses a lower plan while a paid one is granted). Data is never
deleted: after dropping to Free over the client cap, existing clients stay
readable and only new clients are blocked.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.tenancy.models import Client, Practice, UsageCounter
from app.v1.common import ProblemError

from .config import billing_enabled, grace_days, supplier
from .gst import SAC_SAAS, financial_year, split_inclusive
from .models import BillingEvent, Invoice, InvoiceLine, Subscription
from .plans import FREE, GAUGE_METRICS, GST_RATE_BP, get_plan, next_plan_with, rank
from .provider import BillingProvider, ProviderError

log = logging.getLogger(__name__)
UPGRADE_URL = "/settings/billing"
PAID_STATUSES = ("active", "past_due", "halted")


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


# ------------------------------------------------------- effective plan
def grants(sub: Subscription, now: datetime) -> bool:
    if sub.status == "active":
        end = sub.current_period_end
        return end is None or now <= end + timedelta(days=grace_days())
    if sub.status in ("past_due", "halted"):
        return sub.grace_until is not None and now <= sub.grace_until
    if sub.status == "cancelled":
        return sub.ended_at is not None and now < sub.ended_at
    return False


def effective_subscription(db: Session, practice_id: uuid.UUID,
                           now: datetime | None = None) -> Subscription | None:
    now = now or utcnow()
    rows = db.scalars(select(Subscription).where(Subscription.practice_id == practice_id)
                      .order_by(Subscription.created_at.desc())).all()
    live = [s for s in rows if grants(s, now)]
    return max(live, key=lambda s: (rank(s.plan_key), s.created_at), default=None)


def effective_plan_key(db: Session, practice_id: uuid.UUID, now: datetime | None = None) -> str:
    sub = effective_subscription(db, practice_id, now)
    return sub.plan_key if sub else FREE


# ------------------------------------------------------------ usage
def period_start(now: datetime | None = None) -> date:
    d = (now or utcnow()).date()
    return date(d.year, d.month, 1)


def used(db: Session, practice_id: uuid.UUID, metric: str, now: datetime | None = None) -> int:
    if metric in GAUGE_METRICS:  # only "clients" today
        return db.scalar(select(func.count()).select_from(Client).where(
            Client.practice_id == practice_id, Client.deleted_at.is_(None))) or 0
    return int(db.scalar(select(UsageCounter.value).where(
        UsageCounter.practice_id == practice_id, UsageCounter.metric == metric,
        UsageCounter.period == period_start(now))) or 0)


def usage_meter(db: Session, practice_id: uuid.UUID, plan_key: str,
                now: datetime | None = None) -> list[dict]:
    plan = get_plan(plan_key)
    out = []
    for metric, limit in plan.limits.items():
        u = used(db, practice_id, metric, now)
        out.append({"metric": metric, "used": u, "limit": limit,
                    "period": "current" if metric in GAUGE_METRICS else period_start(now).isoformat()})
    return out


def enforce(db: Session, practice_id: uuid.UUID, metric: str,
            now: datetime | None = None) -> None:
    """Raise 402 when the plan's quota is used up, 403 when the plan does not
    include the feature at all. No-op when billing is off (self-hosted)."""
    if not billing_enabled():
        return
    key = effective_plan_key(db, practice_id, now)
    limit = get_plan(key).limits.get(metric)
    if limit is None:
        return
    n = used(db, practice_id, metric, now)
    if limit > 0 and n < limit:
        return
    target = next_plan_with(metric, key)
    extra = {"metric": metric, "plan": key, "limit": limit, "used": n,
             "upgrade_to": target, "upgrade_url": UPGRADE_URL}
    hint = f" Upgrade to {get_plan(target).name} at {UPGRADE_URL}." if target else ""
    if limit == 0:
        raise ProblemError(403, f"Your {get_plan(key).name} plan does not include {metric}."
                           + hint, "plan_feature_unavailable", **extra)
    raise ProblemError(402, f"You have used {n} of {limit} {metric} on the "
                       f"{get_plan(key).name} plan.{hint}", "plan_limit_reached", **extra)


def consume_if_new(db: Session, practice_id: uuid.UUID, metric: str, created_at: datetime) -> None:
    """Count a row against a monthly quota only if this transaction created it
    (created_at defaults to now(), which is constant within a transaction)."""
    if db.scalar(select(func.now())) == created_at:
        stmt = pg_insert(UsageCounter).values(
            practice_id=practice_id, metric=metric, period=period_start(), value=1)
        db.execute(stmt.on_conflict_do_update(
            index_elements=["practice_id", "metric", "period"],
            set_={"value": UsageCounter.value + 1, "updated_at": func.now()}))


# ----------------------------------------------------------- profile
def recipient_snapshot(p: Practice) -> dict:
    return {"name": p.billing_legal_name or p.name, "gstin": p.gstin,
            "state_code": p.billing_state_code or (p.gstin[:2] if p.gstin else None),
            "address": p.billing_address}


# ------------------------------------------------------------ checkout
def start_checkout(db: Session, provider: BillingProvider, practice_id: uuid.UUID,
                   plan_key: str, interval: str, email: str | None) -> Subscription:
    plan = get_plan(plan_key)
    if plan.key == FREE or plan.key != plan_key:
        raise ProblemError(422, "choose a paid plan", "invalid_plan")
    current = effective_subscription(db, practice_id)
    if current is not None and current.status == "active":
        if current.plan_key == plan_key and current.interval == interval:
            raise ProblemError(409, "you are already on this plan", "already_subscribed")
        if rank(plan_key) < rank(current.plan_key):
            raise ProblemError(
                409, "Downgrades apply at the end of the billing period: cancel the current "
                     "plan, then subscribe to the lower plan once it ends.",
                "downgrade_requires_cancel", current_plan=current.plan_key)
    practice = db.get(Practice, practice_id)
    try:
        if not practice.razorpay_customer_id:
            practice.razorpay_customer_id = provider.create_customer(
                name=practice.billing_legal_name or practice.name, email=email,
                gstin=practice.gstin, notes={"practice_id": str(practice_id)})
        ps = provider.create_subscription(
            customer_id=practice.razorpay_customer_id, plan_key=plan_key, interval=interval,
            amount_paise=plan.total_paise(interval),
            notes={"practice_id": str(practice_id), "plan_key": plan_key, "interval": interval})
    except ProviderError as exc:
        raise ProblemError(502, str(exc), "payment_provider_error") from exc
    sub = Subscription(practice_id=practice_id, plan_key=plan_key, interval=interval,
                       status="created", provider=provider.name,
                       provider_customer_id=practice.razorpay_customer_id,
                       provider_subscription_id=ps.id, checkout_url=ps.checkout_url)
    db.add(sub)
    practice.razorpay_subscription_id = ps.id
    db.flush()
    return sub


def cancel(db: Session, provider: BillingProvider, practice_id: uuid.UUID,
           now: datetime | None = None) -> Subscription:
    now = now or utcnow()
    sub = effective_subscription(db, practice_id, now)
    if sub is None or sub.status == "cancelled":
        raise ProblemError(409, "there is no active subscription to cancel", "no_subscription")
    at_end = sub.status == "active"
    try:
        provider.cancel_subscription(sub.provider_subscription_id, at_cycle_end=at_end)
    except ProviderError as exc:
        raise ProblemError(502, str(exc), "payment_provider_error") from exc
    if at_end:
        sub.cancel_at_period_end = True
    else:  # past_due or halted: nothing left to bill, end it now
        sub.status, sub.ended_at = "cancelled", now
    db.flush()
    sync_practice_plan(db, practice_id, now)
    return sub


def sync_practice_plan(db: Session, practice_id: uuid.UUID, now: datetime | None = None) -> None:
    db.get(Practice, practice_id).plan = effective_plan_key(db, practice_id, now)


# ------------------------------------------------------------ invoices
def next_invoice_number(db: Session, at: datetime) -> tuple[str, str]:
    """Sequential per financial year, gapless: the counter row is locked by the
    upsert until this transaction commits, and a rollback releases the number.
    Format AN/<FY>/<6 digits> is 14 characters (GST rule 46 allows 16)."""
    fy = financial_year(at)
    n = db.execute(text(
        "INSERT INTO invoice_sequence (fy, last_value) VALUES (:fy, 1) "
        "ON CONFLICT (fy) DO UPDATE SET last_value = invoice_sequence.last_value + 1 "
        "RETURNING last_value"), {"fy": fy}).scalar_one()
    return fy, f"AN/{fy}/{n:06d}"


def issue_invoice(db: Session, *, practice: Practice, subscription: Subscription | None,
                  payment_id: str, amount_paise: int, plan_key: str, interval: str,
                  issued_at: datetime, period_start_: datetime | None,
                  period_end_: datetime | None) -> Invoice:
    existing = db.scalar(select(Invoice).where(Invoice.provider_payment_id == payment_id))
    if existing is not None:
        return existing
    sup = supplier()
    rec = recipient_snapshot(practice)
    place = rec["state_code"] or sup["state_code"]  # unknown recipient: supplier's state
    split = split_inclusive(amount_paise, GST_RATE_BP, sup["state_code"], place)
    fy, number = next_invoice_number(db, issued_at)
    inv = Invoice(
        practice_id=practice.id, subscription_id=subscription.id if subscription else None,
        number=number, fy=fy, issued_at=issued_at, provider_payment_id=payment_id,
        supplier=sup, recipient=rec, place_of_supply=place, intra_state=split.intra_state,
        taxable_paise=split.taxable, cgst_paise=split.cgst, sgst_paise=split.sgst,
        igst_paise=split.igst, total_paise=split.total, period_start=period_start_,
        period_end=period_end_)
    db.add(inv)
    db.flush()
    cadence = "yearly" if interval == "year" else "monthly"
    desc = f"Ankana {get_plan(plan_key).name} plan, {cadence} subscription"
    if period_start_ and period_end_:
        desc += f", {period_start_:%d %b %Y} to {period_end_:%d %b %Y}"
    db.add(InvoiceLine(
        practice_id=practice.id, invoice_id=inv.id, position=1, description=desc,
        sac=SAC_SAAS, quantity=1, taxable_paise=split.taxable, tax_rate_bp=GST_RATE_BP,
        cgst_paise=split.cgst, sgst_paise=split.sgst, igst_paise=split.igst))
    db.flush()
    return inv


# ------------------------------------------------------------ webhooks
def _ts(v) -> datetime | None:
    return datetime.fromtimestamp(int(v), tz=UTC) if v else None


def _entity(payload: dict, name: str) -> dict:
    return ((payload.get("payload") or {}).get(name) or {}).get("entity") or {}


def resolve_practice(db: Session, event: dict) -> uuid.UUID | None:
    sub_id = _entity(event, "subscription").get("id")
    cust = _entity(event, "payment").get("customer_id") or \
        _entity(event, "subscription").get("customer_id")
    if not sub_id and not cust:
        return None
    return db.execute(text("SELECT billing_find_practice(:s, :c)"),
                      {"s": sub_id, "c": cust}).scalar()


def record_event(db: Session, event_id: str, provider: str, event_type: str,
                 practice_id: uuid.UUID | None) -> bool:
    """Insert the idempotency ledger row. False means this event was already seen."""
    stmt = pg_insert(BillingEvent).values(
        event_id=event_id, provider=provider, event_type=event_type, practice_id=practice_id,
        outcome="applied" if practice_id else "unmatched").on_conflict_do_nothing(
    ).returning(BillingEvent.event_id)
    return db.execute(stmt).first() is not None


def _start_grace(sub: Subscription, now: datetime) -> None:
    if sub.grace_until is None or sub.grace_until < now:
        sub.grace_until = now + timedelta(days=grace_days())


def apply_event(db: Session, provider: BillingProvider, practice_id: uuid.UUID, event: dict,
                now: datetime | None = None) -> str:
    """Apply one verified provider event inside the practice's tenant transaction.
    Returns a short outcome label. Safe against out-of-order delivery: a
    cancelled subscription is never revived, charges are always invoiced once."""
    now = now or utcnow()
    kind = event.get("event", "")
    sub_ent, pay_ent = _entity(event, "subscription"), _entity(event, "payment")
    sub = None
    if sub_ent.get("id"):
        sub = db.scalar(select(Subscription).where(
            Subscription.provider_subscription_id == sub_ent["id"]))
    if sub is None:
        return "ignored_unknown_subscription"
    practice = db.get(Practice, practice_id)

    if kind in ("subscription.activated", "subscription.charged") and sub.status != "cancelled":
        sub.status = "active"
        sub.grace_until = None
        sub.current_period_start = _ts(sub_ent.get("current_start")) or sub.current_period_start
        sub.current_period_end = _ts(sub_ent.get("current_end")) or sub.current_period_end
        _supersede(db, provider, sub, now)
    elif kind == "subscription.pending" and sub.status == "active":
        sub.status = "past_due"
        _start_grace(sub, now)
    elif kind == "subscription.halted" and sub.status != "cancelled":
        sub.status = "halted"
        _start_grace(sub, now)
    elif kind in ("subscription.cancelled", "subscription.completed", "subscription.expired"):
        if sub.status != "cancelled":
            sub.status, sub.ended_at = "cancelled", now
    elif kind == "payment.failed" and sub.status == "active":
        sub.status = "past_due"
        _start_grace(sub, now)

    if kind == "subscription.charged" and pay_ent.get("id") and pay_ent.get("amount"):
        issue_invoice(
            db, practice=practice, subscription=sub, payment_id=pay_ent["id"],
            amount_paise=int(pay_ent["amount"]), plan_key=sub.plan_key, interval=sub.interval,
            issued_at=now, period_start_=_ts(sub_ent.get("current_start")),
            period_end_=_ts(sub_ent.get("current_end")))
    db.flush()
    sync_practice_plan(db, practice_id, now)
    return "applied"


def _supersede(db: Session, provider: BillingProvider, new: Subscription, now: datetime) -> None:
    """A newly active subscription replaces any other paid one (an upgrade).
    No proration: the old plan is cancelled at the provider immediately."""
    others = db.scalars(select(Subscription).where(
        Subscription.practice_id == new.practice_id, Subscription.id != new.id,
        Subscription.status.in_(PAID_STATUSES))).all()
    for old in others:
        try:
            provider.cancel_subscription(old.provider_subscription_id, at_cycle_end=False)
        except ProviderError:
            log.warning("could not cancel superseded subscription %s at provider",
                        old.provider_subscription_id)
        old.status, old.ended_at = "cancelled", now
