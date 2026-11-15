"""The Today feed, plan usage for the sidebar, and the practice location that the
daily panchang reads. All on the caller's RLS session."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.billing import service as billing
from app.billing.config import billing_enabled
from app.billing.plans import get_plan
from app.notify import due
from app.notify.api import needs_you
from app.tenancy.models import (
    Client,
    Consultation,
    Practice,
    Role,
    UserAccount,
)
from nakshatra_core.sky import daily_panchang, sky_events
from nakshatra_core.zodiac import SIGN_NAMES

from . import insight
from .common import STAFF, ProblemError, audit

router = APIRouter()

# Practices that have not set a place fall back to the default city of their zone.
DEFAULT_PLACES = {"Asia/Kolkata": ("New Delhi", 28.6139, 77.2090),
                  "Asia/Calcutta": ("New Delhi", 28.6139, 77.2090)}
SKY_DAYS = 7
NEXT_INGRESS_DAYS = 60


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ models
class TodayConsultation(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    at: datetime = Field(description="Booked time (scheduled_at, else consulted_at)")
    topic: str | None
    mode: str | None
    chart_id: uuid.UUID | None
    lagna_sign: str | None
    lagna_degree: float | None
    maha: str | None = Field(default=None, description="Running mahadasha lord")
    antar: str | None = Field(default=None, description="Running antardasha lord")
    houses: dict[int, list[str]] = Field(
        default_factory=dict, description="House 1..12 to planet abbreviations, for the mini chart")
    status: Literal["prepared", "needs_birth_time", "no_chart"]


class NeedsYouItem(BaseModel):
    kind: Literal["followup", "missed_remedy", "ended_plan", "failed_send"]
    client_id: uuid.UUID | None
    client_name: str | None
    detail: str | None = Field(default=None, description="Topic, plan title or send kind")
    days: int | None = Field(default=None, description="Days overdue, or the cycle day")


class NeedsYouSummary(BaseModel):
    total: int
    followups: int
    missed_remedies: int
    ended_plans: int
    failed_sends: int
    items: list[NeedsYouItem]


class PanchangItem(BaseModel):
    name: str
    ends_at: datetime


class PanchangOut(BaseModel):
    sunrise: datetime
    sunset: datetime
    vara: str
    paksha: str
    tithi: PanchangItem
    nakshatra: PanchangItem
    yoga: str
    karana: str
    moon_sign: str
    sun_sign: str
    rahu_kaal_start: datetime
    rahu_kaal_end: datetime


class PlaceOut(BaseModel):
    label: str | None
    latitude: float | None
    longitude: float | None
    source: Literal["practice", "timezone_default", "unset"]


class SkyEventOut(BaseModel):
    at: datetime
    planet: str
    kind: Literal["ingress", "retrograde-station", "direct-station", "amavasya", "purnima"]
    sign: str
    sign_index: int
    clients_touched: int = Field(
        description="Clients whose latest chart has the lagna or Moon in this sign")
    client_ids: list[uuid.UUID] = Field(description="Up to 25 of them")


class TodayOut(BaseModel):
    date: str = Field(description="Local date in the practice time zone, YYYY-MM-DD")
    timezone: str
    practitioner_name: str | None
    consultations: list[TodayConsultation]
    needs_you: NeedsYouSummary
    place: PlaceOut
    panchang: PanchangOut | None = Field(
        default=None, description="Null when the practice has no place and its zone has no default")
    sky: list[SkyEventOut]
    next_ingress: SkyEventOut | None


# -------------------------------------------------------------------- feed
def _place(practice: Practice) -> PlaceOut:
    if practice.latitude is not None and practice.longitude is not None:
        return PlaceOut(label=practice.place_label, latitude=practice.latitude,
                        longitude=practice.longitude, source="practice")
    d = DEFAULT_PLACES.get(practice.timezone)
    if d:
        return PlaceOut(label=d[0], latitude=d[1], longitude=d[2], source="timezone_default")
    return PlaceOut(label=None, latitude=None, longitude=None, source="unset")


def _needs_you(m: CurrentMember, db: Session) -> NeedsYouSummary:
    raw = needs_you(m, db)
    items: list[NeedsYouItem] = []
    for f in raw["followups"]:
        items.append(NeedsYouItem(kind="followup", client_id=f["client_id"],
                                  client_name=f["client_name"], detail=f.get("topic"),
                                  days=f["days_overdue"]))
    for r in raw["missed_remedies"]:
        items.append(NeedsYouItem(kind="missed_remedy", client_id=r["client_id"],
                                  client_name=r["client_name"], detail=r["title"],
                                  days=r["day_number"]))
    for e in raw["ended_plans"]:
        items.append(NeedsYouItem(kind="ended_plan", client_id=e["client_id"],
                                  client_name=e["client_name"], detail=e["title"]))
    for n in raw["failed_notifications"]:
        items.append(NeedsYouItem(kind="failed_send", client_id=n["client_id"],
                                  client_name=n["client_name"], detail=n["kind"]))
    return NeedsYouSummary(
        total=len(items), followups=len(raw["followups"]),
        missed_remedies=len(raw["missed_remedies"]), ended_plans=len(raw["ended_plans"]),
        failed_sends=len(raw["failed_notifications"]), items=items[:20])


def _sky(db: Session, now: datetime) -> tuple[list[dict], dict | None]:
    """Events in the next 7 days and the next sign ingress (looking up to 60 days ahead),
    each with the clients it touches."""
    window = now + timedelta(days=SKY_DAYS)
    events = sky_events(now, NEXT_INGRESS_DAYS)
    facts = insight.latest_chart_facts(db, None, now)
    names = {cid: n for cid, n, _ in insight.live_clients(db)}

    def decorate(e: dict) -> dict:
        sign = e["sign_index"]
        touched = [cid for cid, f in facts.items()
                   if cid in names and (f.lagna_index == sign or f.moon_index == sign)]
        return {**e, "sign": SIGN_NAMES[sign], "clients_touched": len(touched),
                "client_ids": touched[:25]}

    week = [decorate(e) for e in events if e["at"] <= window]
    nxt = next((decorate(e) for e in events if e["kind"] == "ingress"), None)
    return week, nxt


@router.get("/today", response_model=TodayOut, tags=["today"], operation_id="getToday",
            summary="Today in the practice time zone: booked consultations, what needs you, "
                    "the panchang for the practice place and the sky for the next 7 days")
def get_today(m: CurrentMember = Depends(require_roles(*STAFF)),
              db: Session = Depends(tenant_db, scope="function")):
    now = datetime.now(tz=UTC)
    practice = db.scalar(select(Practice))
    tz = ZoneInfo(practice.timezone)
    local_date = due.local_today(now, practice.timezone)
    day_start = datetime.combine(local_date, time(0), tzinfo=tz).astimezone(UTC)
    day_end = datetime.combine(local_date + timedelta(days=1), time(0), tzinfo=tz).astimezone(UTC)

    # Consultations: booked (scheduled_at) or held (consulted_at) inside the local day.
    at = Consultation.scheduled_at
    rows = db.execute(
        select(Consultation, Client.display_name)
        .join(Client, (Client.id == Consultation.client_id)
              & (Client.practice_id == Consultation.practice_id))
        .where(Consultation.deleted_at.is_(None), Client.deleted_at.is_(None))
        .where(((at.is_not(None)) & (at >= day_start) & (at < day_end))
               | ((at.is_(None)) & (Consultation.consulted_at >= day_start)
                  & (Consultation.consulted_at < day_end)))
        .order_by(Consultation.scheduled_at.nulls_last(), Consultation.consulted_at)).all()
    client_ids = [c.client_id for c, _ in rows]
    facts = insight.latest_chart_facts(db, client_ids, now)
    flags = insight.rectify_flags(db)
    consultations = []
    for c, name in sorted(rows, key=lambda r: r[0].scheduled_at or r[0].consulted_at):
        f = facts.get(c.client_id)
        status = ("no_chart" if f is None
                  else "needs_birth_time" if flags.get(c.client_id, (False, None))[0]
                  else "prepared")
        consultations.append(TodayConsultation(
            id=c.id, client_id=c.client_id, client_name=name,
            at=c.scheduled_at or c.consulted_at, topic=c.topic, mode=c.mode,
            chart_id=f.chart_id if f else None, lagna_sign=f.lagna_sign if f else None,
            lagna_degree=f.lagna_degree if f else None, houses=f.houses if f else {},
            maha=f.maha if f else None, antar=f.antar if f else None,
            status=status))

    place = _place(practice)
    panchang = None
    if place.latitude is not None and place.longitude is not None:
        noon = datetime.combine(local_date, time(12), tzinfo=tz).astimezone(UTC)
        p = daily_panchang(noon, place.latitude, place.longitude, (local_date.weekday() + 1) % 7)
        panchang = PanchangOut(
            sunrise=p["sunrise"], sunset=p["sunset"], vara=p["vara"], paksha=p["tithi"]["paksha"],
            tithi=PanchangItem(name=p["tithi"]["name"], ends_at=p["tithi"]["ends_at"]),
            nakshatra=PanchangItem(name=p["nakshatra"]["name"], ends_at=p["nakshatra"]["ends_at"]),
            yoga=p["yoga"], karana=p["karana"], moon_sign=p["moon_sign"], sun_sign=p["sun_sign"],
            rahu_kaal_start=p["rahu_kaal"]["start"], rahu_kaal_end=p["rahu_kaal"]["end"])

    week, nxt = _sky(db, now)
    user = db.get(UserAccount, m.user_id)
    name = (user.display_name or (user.email or "").split("@")[0] or None) if user else None
    return TodayOut(
        date=local_date.isoformat(), timezone=practice.timezone, practitioner_name=name,
        consultations=consultations, needs_you=_needs_you(m, db), place=place,
        panchang=panchang, sky=[SkyEventOut(**e) for e in week],
        next_ingress=SkyEventOut(**nxt) if nxt else None)


# ------------------------------------------------------------------- usage
class UsageMeter(BaseModel):
    metric: Literal["reports", "charts", "ai_asks", "clients"]
    used: int
    limit: int | None = Field(default=None, description="Null means unlimited")
    period: str = Field(description="'current' for a gauge, else the first day of the month")


class UsageOut(BaseModel):
    billing: bool = Field(description="false on self-hosted servers: nothing is metered against a plan")
    plan: str | None
    plan_name: str | None
    period: str = Field(description="Calendar month, YYYY-MM")
    unlimited: bool
    meters: list[UsageMeter]


@router.get("/usage", response_model=UsageOut, tags=["billing"], operation_id="getUsage",
            summary="This month's usage against the plan (unlimited when billing is off)")
def get_usage(m: CurrentMember = Depends(require_roles(*STAFF)),
              db: Session = Depends(tenant_db, scope="function")):
    now = datetime.now(tz=UTC)
    period = billing.period_start(now)
    if billing_enabled():
        key = billing.effective_plan_key(db, m.practice_id, now)
        plan = get_plan(key)
        limits = dict(plan.limits)
        plan_key, plan_name = key, plan.name
    else:
        limits, plan_key, plan_name = {}, None, None
    meters = []
    for metric in ("reports", "charts", "ai_asks", "clients"):
        if billing_enabled() and metric not in limits:
            continue
        meters.append(UsageMeter(
            metric=metric, used=billing.used(db, m.practice_id, metric, now),
            limit=limits.get(metric),
            period="current" if metric == "clients" else period.isoformat()))
    return UsageOut(billing=billing_enabled(), plan=plan_key, plan_name=plan_name,
                    period=period.strftime("%Y-%m"),
                    unlimited=all(x.limit is None for x in meters), meters=meters)


# ---------------------------------------------------------- practice place
class LocationIn(BaseModel):
    place_label: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@router.get("/practice/location", response_model=PlaceOut, tags=["practice"],
            operation_id="getPracticeLocation",
            summary="Where the practice sits (drives the daily panchang)")
def get_location(m: CurrentMember = Depends(require_roles(*STAFF)),
                 db: Session = Depends(tenant_db, scope="function")):
    return _place(db.scalar(select(Practice)))


@router.put("/practice/location", response_model=PlaceOut, tags=["practice"],
            operation_id="updatePracticeLocation", summary="Set the practice place")
def put_location(body: LocationIn, request: Request,
                 m: CurrentMember = Depends(require_roles(Role.owner)),
                 db: Session = Depends(tenant_db, scope="function")):
    practice = db.scalar(select(Practice))
    if practice is None:
        raise ProblemError(404, "practice not found", "not_found")
    practice.place_label = body.place_label
    practice.latitude = body.latitude
    practice.longitude = body.longitude
    db.flush()
    audit(db, m, "practice.location_updated", "practice", practice.id, request)
    return _place(practice)
