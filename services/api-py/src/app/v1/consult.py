"""Consultation workflow: the pre-consult brief, the chart fact catalog for pinned note
chips, structured session summaries with predictions kept for outcome tracking, life
events and the client timeline. All clinical (owner and astrologer) except where noted."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ankana_ai.prompt import chart_digest
from ankana_ai.providers import ProviderRequest, provider_from_env
from ankana_ai.verifier import Verifier, scan_unstructured
from app.ai_connections import chain_for_role, record_usage
from app.auth import CurrentMember, require_roles, tenant_db
from app.billing.entitlements import require_entitlement
from app.tenancy.models import (
    BirthRecord,
    ChartArtifact,
    ClientLifeEvent,
    ConsentPurpose,
    Consultation,
    ConsultationNote,
    ConsultationSummary,
    ConsultPrediction,
    RemedyCheckin,
    RemedyItem,
    RemedyPlan,
    RemedyStatus,
    Report,
)
from nakshatra_core.sky import chart_transit_timeline

from . import schemas as sc
from .common import (
    CLINICAL,
    STAFF,
    ProblemError,
    audit,
    bump_usage,
    load_client,
    require_consent,
)
from .insight import parse_iso

router = APIRouter()

PredictionStatusT = Literal["pending", "came_true", "did_not", "unclear"]
LIFE_KINDS = ("marriage", "child", "job", "business", "move", "education", "health", "loss",
              "travel", "other")
SLOW = {"saturn", "jupiter", "rahu", "ketu"}


# ------------------------------------------------------------------ helpers
def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def latest_chart(db: Session, client_id: uuid.UUID) -> ChartArtifact | None:
    """The newest chart of the client's newest birth record that has one."""
    return db.scalar(
        select(ChartArtifact)
        .join(BirthRecord, (ChartArtifact.birth_record_id == BirthRecord.id)
              & (ChartArtifact.practice_id == BirthRecord.practice_id))
        .where(BirthRecord.client_id == client_id, BirthRecord.deleted_at.is_(None))
        .order_by(BirthRecord.version.desc(), ChartArtifact.created_at.desc()).limit(1))


def _consultation(db: Session, consultation_id: uuid.UUID) -> Consultation:
    c = db.scalar(select(Consultation).where(
        Consultation.id == consultation_id, Consultation.deleted_at.is_(None)))
    if c is None:
        raise ProblemError(404, "consultation not found", "not_found")
    return c


def _json_list(raw: str | None) -> list[str]:
    try:
        v = json.loads(raw or "[]")
    except ValueError:
        return []
    return [str(x) for x in v] if isinstance(v, list) else []


def _day(dt: datetime | None) -> date | None:
    return dt.astimezone(UTC).date() if dt else None


# ---------------------------------------------------------- dasha and transits
def dasha_now(vimshottari: dict | None, now: datetime) -> dict | None:
    for maha in (vimshottari or {}).get("mahadashas", []):
        if parse_iso(maha["start"]) <= now < parse_iso(maha["end"]):
            out = {"maha": maha["planet"], "maha_ends": parse_iso(maha["end"]),
                   "antar": None, "antar_ends": None}
            for sub in maha.get("children", []):
                if parse_iso(sub["start"]) <= now < parse_iso(sub["end"]):
                    out.update(antar=sub["planet"], antar_ends=parse_iso(sub["end"]))
                    break
            return out
    return None


_TRANSIT_CACHE: dict[tuple[str, str], dict] = {}


def upcoming_timeline(chart: ChartArtifact, now: datetime, months: int = 6) -> dict:
    """The natal transit timeline, cached for the day: it scans the sky and is not cheap."""
    key = (str(chart.id), now.date().isoformat())
    hit = _TRANSIT_CACHE.get(key)
    if hit is None:
        if len(_TRANSIT_CACHE) > 64:
            _TRANSIT_CACHE.clear()
        hit = _TRANSIT_CACHE[key] = chart_transit_timeline(chart.payload, now, months)
    return hit


def notable_transits(timeline: dict, limit: int = 3) -> list[dict]:
    """The next few events a practitioner would raise: slow-planet ingresses and stations,
    anything landing on the natal Moon or lagna, and sade sati phase changes."""
    picks = []
    for e in timeline["events"]:
        slow = e["planet"] in SLOW
        if e["kind"] == "sade_sati":
            ok = True
        elif e["kind"] in ("aspect", "conjunction"):
            ok = slow or e["planet"] in ("mars", "sun")
        elif e["kind"] == "ingress":
            ok = slow
        else:  # stations
            ok = e["planet"] in ("saturn", "jupiter")
        if ok:
            picks.append(e)
    picks.sort(key=lambda e: (e["date"], e["planet"]))
    return picks[:limit]


# ------------------------------------------------------------------ schemas
class FactOut(BaseModel):
    type: sc.FactType
    ref: str
    label: str
    group: str


class ChartFactsOut(BaseModel):
    chart_id: uuid.UUID | None
    facts: list[FactOut]


class DashaBrief(BaseModel):
    maha: str
    maha_ends: datetime
    antar: str | None
    antar_ends: datetime | None


class TransitBrief(BaseModel):
    date: datetime
    planet: str
    kind: str
    sign: str
    house_from_moon: int
    house_from_lagna: int
    target: str | None = None
    aspect: int | None = None
    phase: str | None = None


class SadeSatiBrief(BaseModel):
    active: bool
    phase: str | None
    ends_at: datetime | None = None


class RemedyBrief(BaseModel):
    plan_id: uuid.UUID
    title: str
    status: str
    day_number: int | None
    cycle_days: int
    end_date: date | None
    adherence_pct: int | None = Field(
        description="Share of expected check-ins done since the start; null before day 1")


class LastConsultBrief(BaseModel):
    id: uuid.UUID
    at: datetime
    topic: str | None
    excerpt: str | None = Field(description="Summary topics, else the start of the latest note")


class FollowUpBrief(BaseModel):
    consultation_id: uuid.UUID
    date: date
    overdue: bool


class PredictionBrief(BaseModel):
    id: uuid.UUID
    statement: str
    window_start: date | None
    window_end: date | None
    due: bool = Field(description="The window has ended and no outcome is recorded")


class BriefOut(BaseModel):
    client_id: uuid.UUID
    chart_id: uuid.UUID | None
    consultation_id: uuid.UUID | None
    generated_at: datetime
    dasha: DashaBrief | None
    transits: list[TransitBrief]
    sade_sati: SadeSatiBrief | None
    remedies: list[RemedyBrief]
    last_consultation: LastConsultBrief | None
    follow_ups: list[FollowUpBrief]
    open_predictions: list[PredictionBrief]
    stated_question: str | None


class PredictionIn(BaseModel):
    id: uuid.UUID | None = Field(default=None, description="Existing prediction to update")
    statement: str = Field(min_length=1, max_length=1000)
    window_start: date | None = None
    window_end: date | None = None


class SummaryIn(BaseModel):
    topics: list[str] = Field(default_factory=list, max_length=20)
    remedies_given: list[str] = Field(default_factory=list, max_length=20)
    follow_up_date: date | None = None
    predictions: list[PredictionIn] = Field(default_factory=list, max_length=20)
    source: Literal["manual", "ai"] = "manual"


class PredictionOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    consultation_id: uuid.UUID
    statement: str
    window_start: date | None
    window_end: date | None
    status: PredictionStatusT
    outcome_note: str | None
    resolved_at: datetime | None
    created_at: datetime


class SummaryOut(BaseModel):
    consultation_id: uuid.UUID
    topics: list[str]
    remedies_given: list[str]
    follow_up_date: date | None
    source: Literal["manual", "ai"]
    updated_at: datetime
    predictions: list[PredictionOut]


class SummaryEnvelope(BaseModel):
    summary: SummaryOut | None
    predictions: list[PredictionOut]


class PredictionPatch(BaseModel):
    statement: str | None = Field(default=None, min_length=1, max_length=1000)
    window_start: date | None = None
    window_end: date | None = None
    status: PredictionStatusT | None = None
    outcome_note: str | None = Field(default=None, max_length=2000)


class LifeEventIn(BaseModel):
    event_date: date
    kind: Literal["marriage", "child", "job", "business", "move", "education", "health",
                  "loss", "travel", "other"] = "other"
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class LifeEventPatch(BaseModel):
    event_date: date | None = None
    kind: Literal["marriage", "child", "job", "business", "move", "education", "health",
                  "loss", "travel", "other"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class LifeEventOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    event_date: date
    kind: str
    title: str
    notes: str | None


class TimelineEvent(BaseModel):
    id: str
    kind: Literal["consultation", "prediction", "remedy", "report", "life_event"]
    at: datetime
    title: str
    detail: str | None = None
    status: str | None = None
    ref_id: uuid.UUID | None = Field(
        default=None, description="Consultation, prediction, plan, report or event id")


class DraftOut(BaseModel):
    summary: SummaryIn
    verification: dict[str, Any]
    model: str | None = None


# ------------------------------------------------------------- fact catalog
def fact_catalog(chart: ChartArtifact, now: datetime) -> list[dict]:
    a = chart.payload
    out: list[dict] = []
    for p in a.get("planets", []):
        name = p["planet"]
        retro = ", retrograde" if p.get("retrograde") else ""
        out.append({"type": "planet", "ref": f"planet:{name}", "group": "Planets",
                    "label": f"{_cap(name)} in {p['signName']}, house {p['house']}{retro}"})
    for maha in a.get("vimshottari", {}).get("mahadashas", []):
        out.append({"type": "dasha", "ref": f"dasha:{maha['planet']}", "group": "Dashas",
                    "label": f"{_cap(maha['planet'])} dasha, {maha['start'][:4]} to {maha['end'][:4]}"})
    running = dasha_now(a.get("vimshottari"), now)
    if running:
        for maha in a["vimshottari"]["mahadashas"]:
            if maha["planet"] == running["maha"] and parse_iso(maha["start"]) <= now < parse_iso(maha["end"]):
                for sub in maha.get("children", []):
                    out.append({
                        "type": "dasha", "ref": f"dasha:{maha['planet']}/{sub['planet']}",
                        "group": "Dashas",
                        "label": f"{_cap(maha['planet'])} / {_cap(sub['planet'])}, "
                                 f"until {sub['end'][:7]}"})
    for y in a.get("yogas", []):
        if y.get("present"):
            out.append({"type": "yoga", "ref": f"yoga:{y['key']}", "group": "Yogas",
                        "label": y["name"]})
    try:
        for e in notable_transits(upcoming_timeline(chart, now), limit=8):
            label = (f"{_cap(e['planet'])} {e['kind'].replace('-', ' ').replace('_', ' ')}, "
                     f"{e['sign']} on {e['date'][:10]}")
            out.append({"type": "transit", "ref": f"transit:{e['planet']}:{e['date'][:10]}",
                        "group": "Transits", "label": label})
    except Exception:  # transits are optional here
        pass
    try:
        from ankana_lalkitab import lal_kitab_report

        rep = lal_kitab_report(a).model_dump(by_alias=True, mode="json")
        for pl in rep["chart"]["placements"]:
            out.append({"type": "lal_kitab", "ref": f"lal_kitab:{pl['planet']}_h{pl['house']}",
                        "group": "Lal Kitab",
                        "label": f"{_cap(pl['planet'])} in Lal Kitab house {pl['house']}"})
    except Exception:
        pass
    return out


@router.get("/clients/{client_id}/chart-facts", response_model=ChartFactsOut,
            tags=["consultations"], operation_id="listClientChartFacts",
            summary="Chart facts a note can pin as chips: placements, dashas, yogas, "
                    "upcoming transits and Lal Kitab houses")
def chart_facts(client_id: uuid.UUID, m: CurrentMember = Depends(require_roles(*CLINICAL)),
                db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    chart = latest_chart(db, client.id)
    if chart is None:
        return {"chart_id": None, "facts": []}
    return {"chart_id": chart.id, "facts": fact_catalog(chart, datetime.now(tz=UTC))}


# -------------------------------------------------------------------- brief
def _remedy_brief(db: Session, plan: RemedyPlan, today: date) -> dict:
    items = list(db.scalars(select(RemedyItem).where(
        RemedyItem.plan_id == plan.id, RemedyItem.deleted_at.is_(None))))
    day = None
    pct = None
    if plan.start_date and plan.status == RemedyStatus.active:
        d = (today - plan.start_date).days + 1
        day = d if d >= 1 else None
        if day and items:
            done = db.scalar(select(func.count()).select_from(RemedyCheckin).where(
                RemedyCheckin.item_id.in_([i.id for i in items]), RemedyCheckin.done.is_(True),
                RemedyCheckin.checkin_date >= plan.start_date,
                RemedyCheckin.checkin_date <= today)) or 0
            pct = min(100, round(100 * done / (len(items) * min(day, plan.cycle_days))))
    end = plan.start_date + timedelta(days=plan.cycle_days - 1) if plan.start_date else None
    return {"plan_id": plan.id, "title": plan.title, "status": plan.status.value,
            "day_number": day, "cycle_days": plan.cycle_days, "end_date": end,
            "adherence_pct": pct}


def _excerpt(text: str, n: int = 220) -> str:
    text = re.sub(r"\{\{fact:[^}]*\}\}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "..."


@router.get("/clients/{client_id}/brief", response_model=BriefOut, tags=["consultations"],
            operation_id="getClientBrief",
            summary="Pre-consult brief: running dasha, next notable transits, sade sati, open "
                    "remedies with adherence, last consultation, follow-ups and the client's question")
def client_brief(client_id: uuid.UUID,
                 consultation_id: uuid.UUID | None = Query(
                     default=None, description="The visit to prepare for; else the next booked "
                                               "or latest one"),
                 m: CurrentMember = Depends(require_roles(*CLINICAL)),
                 db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    now = datetime.now(tz=UTC)
    today = now.date()
    chart = latest_chart(db, client.id)

    dasha = sade = None
    transits = []
    if chart is not None:
        dasha = dasha_now(chart.payload.get("vimshottari"), now)
        tl = upcoming_timeline(chart, now)
        transits = notable_transits(tl)
        ss = tl["sade_sati"]
        phase_now = ss.get("phase_now")
        ends = None
        if ss.get("active_now"):
            last = ss["phases"][-1] if ss["phases"] else None
            ends = parse_iso(last["ends_at"]) if last and last.get("ends_at") else None
        sade = {"active": bool(ss.get("active_now")), "phase": phase_now, "ends_at": ends}

    visits = list(db.scalars(select(Consultation).where(
        Consultation.client_id == client.id, Consultation.deleted_at.is_(None))))
    visits.sort(key=lambda c: c.scheduled_at or c.consulted_at)
    target = next((c for c in visits if c.id == consultation_id), None)
    if consultation_id and target is None:
        raise ProblemError(404, "consultation not found", "not_found")
    upcoming = [c for c in visits if (c.scheduled_at or c.consulted_at) >= now - timedelta(hours=12)]
    if target is None and upcoming:
        target = upcoming[0]
    past = [c for c in visits if (c.scheduled_at or c.consulted_at) <= now
            and (target is None or c.id != target.id)]
    last = past[-1] if past else None

    last_out = None
    if last is not None:
        summ = db.scalar(select(ConsultationSummary).where(
            ConsultationSummary.consultation_id == last.id))
        excerpt = None
        if summ is not None and _json_list(summ.topics):
            excerpt = "; ".join(_json_list(summ.topics))
        else:
            note = db.scalar(select(ConsultationNote).where(
                ConsultationNote.consultation_id == last.id,
                ConsultationNote.deleted_at.is_(None))
                .order_by(ConsultationNote.created_at.desc()).limit(1))
            excerpt = _excerpt(note.body) if note else None
        last_out = {"id": last.id, "at": last.scheduled_at or last.consulted_at,
                    "topic": last.topic, "excerpt": excerpt}

    follow_ups = []
    for c in visits:
        if c.follow_up_date is None:
            continue
        followed = any(o.id != c.id and (o.scheduled_at or o.consulted_at).date() >= c.follow_up_date
                       and (o.scheduled_at or o.consulted_at) <= now for o in visits)
        if not followed:
            follow_ups.append({"consultation_id": c.id, "date": c.follow_up_date,
                               "overdue": c.follow_up_date < today})
    follow_ups.sort(key=lambda f: f["date"])

    plans = list(db.scalars(select(RemedyPlan).where(
        RemedyPlan.client_id == client.id, RemedyPlan.deleted_at.is_(None),
        RemedyPlan.status.in_([RemedyStatus.active, RemedyStatus.draft]))
        .order_by(RemedyPlan.created_at)))

    preds = list(db.scalars(select(ConsultPrediction).where(
        ConsultPrediction.client_id == client.id, ConsultPrediction.deleted_at.is_(None),
        ConsultPrediction.status == "pending").order_by(
        ConsultPrediction.window_end.nulls_last(), ConsultPrediction.created_at).limit(5)))

    return {
        "client_id": client.id, "chart_id": chart.id if chart else None,
        "consultation_id": target.id if target else None, "generated_at": now,
        "dasha": dasha, "transits": transits, "sade_sati": sade,
        "remedies": [_remedy_brief(db, p, today) for p in plans],
        "last_consultation": last_out, "follow_ups": follow_ups[:3],
        "open_predictions": [
            {"id": p.id, "statement": p.statement, "window_start": p.window_start,
             "window_end": p.window_end, "due": bool(p.window_end and p.window_end < today)}
            for p in preds],
        "stated_question": target.client_question if target else None,
    }


# --------------------------------------------------------- summary and predictions
def _pred_out(p: ConsultPrediction) -> dict:
    return {"id": p.id, "client_id": p.client_id, "consultation_id": p.consultation_id,
            "statement": p.statement, "window_start": p.window_start,
            "window_end": p.window_end, "status": p.status, "outcome_note": p.outcome_note,
            "resolved_at": p.resolved_at, "created_at": p.created_at}


def _predictions(db: Session, consultation_id: uuid.UUID) -> list[ConsultPrediction]:
    return list(db.scalars(select(ConsultPrediction).where(
        ConsultPrediction.consultation_id == consultation_id,
        ConsultPrediction.deleted_at.is_(None)).order_by(ConsultPrediction.created_at)))


def _summary_out(c: Consultation, s: ConsultationSummary, preds: list[ConsultPrediction]) -> dict:
    return {"consultation_id": c.id, "topics": _json_list(s.topics),
            "remedies_given": _json_list(s.remedies_given), "follow_up_date": c.follow_up_date,
            "source": s.source, "updated_at": s.updated_at,
            "predictions": [_pred_out(p) for p in preds]}


def _clean(items: list[str]) -> list[str]:
    seen: list[str] = []
    for i in items:
        t = re.sub(r"\s+", " ", i).strip()
        if t and t not in seen:
            seen.append(t[:300])
    return seen


@router.get("/consultations/{consultation_id}/summary", response_model=SummaryEnvelope,
            tags=["consultations"], operation_id="getConsultationSummary",
            summary="The structured session summary and its predictions (summary null if none)")
def get_summary(consultation_id: uuid.UUID,
                m: CurrentMember = Depends(require_roles(*CLINICAL)),
                db: Session = Depends(tenant_db, scope="function")):
    c = _consultation(db, consultation_id)
    load_client(db, m, c.client_id)
    s = db.scalar(select(ConsultationSummary).where(
        ConsultationSummary.consultation_id == c.id))
    preds = _predictions(db, c.id)
    return {"summary": _summary_out(c, s, preds) if s else None,
            "predictions": [_pred_out(p) for p in preds]}


@router.put("/consultations/{consultation_id}/summary", response_model=SummaryOut,
            tags=["consultations"], operation_id="saveConsultationSummary",
            summary="Save the session summary: topics, remedies given, follow-up date and "
                    "predictions with a time window")
def put_summary(consultation_id: uuid.UUID, body: SummaryIn, request: Request,
                m: CurrentMember = Depends(require_roles(*CLINICAL)),
                db: Session = Depends(tenant_db, scope="function")):
    c = _consultation(db, consultation_id)
    load_client(db, m, c.client_id)
    for p in body.predictions:
        if p.window_start and p.window_end and p.window_end < p.window_start:
            raise ProblemError(422, "prediction window ends before it starts", "validation_error")
    s = db.scalar(select(ConsultationSummary).where(
        ConsultationSummary.consultation_id == c.id))
    topics = json.dumps(_clean(body.topics), ensure_ascii=False)
    remedies = json.dumps(_clean(body.remedies_given), ensure_ascii=False)
    if s is None:
        s = ConsultationSummary(practice_id=m.practice_id, consultation_id=c.id,
                                topics=topics, remedies_given=remedies, source=body.source,
                                author_member_id=m.member_id)
        db.add(s)
    else:
        s.topics, s.remedies_given, s.source = topics, remedies, body.source
    c.follow_up_date = body.follow_up_date

    existing = {p.id: p for p in _predictions(db, c.id)}
    keep: set[uuid.UUID] = set()
    for p in body.predictions:
        row = existing.get(p.id) if p.id else None
        if p.id and row is None:
            raise ProblemError(404, "prediction not found", "not_found")
        if row is None:
            row = ConsultPrediction(
                practice_id=m.practice_id, client_id=c.client_id, consultation_id=c.id,
                statement=p.statement.strip(), window_start=p.window_start,
                window_end=p.window_end)
            db.add(row)
        else:
            row.statement, row.window_start, row.window_end = (
                p.statement.strip(), p.window_start, p.window_end)
            keep.add(row.id)
    now = datetime.now(tz=UTC)
    for pid, row in existing.items():
        if pid not in keep and row.status == "pending":
            row.deleted_at = now  # a pending prediction removed from the summary
    db.flush()
    audit(db, m, "consultation_summary.saved", "consultation", c.id, request,
          meta={"source": body.source, "predictions": len(body.predictions)})
    db.refresh(s)
    return _summary_out(c, s, _predictions(db, c.id))


@router.get("/clients/{client_id}/predictions", tags=["consultations"],
            response_model=list[PredictionOut], operation_id="listClientPredictions",
            summary="Predictions made for a client, newest first, for outcome tracking")
def list_predictions(client_id: uuid.UUID,
                     status: PredictionStatusT | None = None,
                     m: CurrentMember = Depends(require_roles(*CLINICAL)),
                     db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    stmt = select(ConsultPrediction).where(
        ConsultPrediction.client_id == client.id, ConsultPrediction.deleted_at.is_(None))
    if status:
        stmt = stmt.where(ConsultPrediction.status == status)
    rows = db.scalars(stmt.order_by(ConsultPrediction.created_at.desc()).limit(200))
    return [_pred_out(p) for p in rows]


@router.patch("/predictions/{prediction_id}", response_model=PredictionOut,
              tags=["consultations"], operation_id="updatePrediction",
              summary="Record or change a prediction's outcome (pending, came true, did not, "
                      "unclear), editable at any time")
def patch_prediction(prediction_id: uuid.UUID, body: PredictionPatch, request: Request,
                     m: CurrentMember = Depends(require_roles(*CLINICAL)),
                     db: Session = Depends(tenant_db, scope="function")):
    p = db.scalar(select(ConsultPrediction).where(
        ConsultPrediction.id == prediction_id, ConsultPrediction.deleted_at.is_(None)))
    if p is None:
        raise ProblemError(404, "prediction not found", "not_found")
    load_client(db, m, p.client_id)
    fields = body.model_fields_set
    if "statement" in fields and body.statement:
        p.statement = body.statement.strip()
    if "window_start" in fields:
        p.window_start = body.window_start
    if "window_end" in fields:
        p.window_end = body.window_end
    if p.window_start and p.window_end and p.window_end < p.window_start:
        raise ProblemError(422, "prediction window ends before it starts", "validation_error")
    if "outcome_note" in fields:
        p.outcome_note = (body.outcome_note or "").strip() or None
    if body.status is not None and body.status != p.status:
        p.status = body.status
        p.resolved_at = None if body.status == "pending" else datetime.now(tz=UTC)
    db.flush()
    audit(db, m, "prediction.updated", "consult_prediction", p.id, request,
          meta={"status": p.status})
    db.refresh(p)
    return _pred_out(p)


# --------------------------------------------------------------- AI draft
DRAFT_SYSTEM = """You turn a Jyotish practitioner's consultation notes into a structured
summary. Use only what the notes say. Never add predictions, remedies or dates that are not in
the notes. Reply with one JSON object and nothing else:
{"topics": [string], "predictions": [{"statement": string, "window_start": "YYYY-MM-DD"|null,
"window_end": "YYYY-MM-DD"|null}], "remedies_given": [string], "follow_up_date": "YYYY-MM-DD"|null}
Keep every string short and in the language of the notes."""


def _parse_draft(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no json")
    return json.loads(m.group(0))


def _iso_date(v: object) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


@router.post("/consultations/{consultation_id}/summary/draft", response_model=DraftOut,
             tags=["assistant"], operation_id="draftConsultationSummary",
             dependencies=[Depends(require_entitlement("ai_asks"))],
             summary="Optional: draft a summary from the notes with the AI assistant. Needs "
                     "ai_assistant consent. The draft is checked against the chart and "
                     "never saved until you save it",
             responses={503: {"description": "AI provider not configured"},
                        502: {"description": "AI provider failed"}})
def draft_summary(consultation_id: uuid.UUID, request: Request,
                  m: CurrentMember = Depends(require_roles(*CLINICAL)),
                  db: Session = Depends(tenant_db, scope="function")):
    c = _consultation(db, consultation_id)
    client = load_client(db, m, c.client_id)
    require_consent(db, client.id, ConsentPurpose.ai_assistant)
    notes = list(db.scalars(select(ConsultationNote).where(
        ConsultationNote.consultation_id == c.id, ConsultationNote.deleted_at.is_(None))
        .order_by(ConsultationNote.created_at)))
    if not notes:
        raise ProblemError(422, "add a note before drafting a summary", "no_notes")
    chain = chain_for_role(db, "synthesise")
    factory = getattr(request.app.state, "ai_provider_factory", provider_from_env)
    provider = chain or factory()
    if provider is None:
        raise ProblemError(503, "AI provider not configured", "ai_unavailable")
    chart = latest_chart(db, client.id)
    artifact = chart.payload if chart else None

    def pinned(n: ConsultationNote) -> str:
        labels = {f["id"]: f["label"] for f in (n.facts or [])}
        return re.sub(r"\{\{fact:([^}]*)\}\}", lambda g: f"[{labels.get(g.group(1), 'chart fact')}]",
                      n.body)

    material = "\n".join(f"- {pinned(n)}" for n in notes)
    now = datetime.now(tz=UTC)
    prompt = (f"Consultation on {(c.scheduled_at or c.consulted_at).date().isoformat()}, "
              f"topic: {c.topic or 'not set'}.\nReference date: {now.date().isoformat()}\n"
              f"Notes:\n{material}")
    bump_usage(db, m.practice_id, "ai_asks")
    model = "claude-sonnet-5-5"
    try:
        resp = provider.complete(ProviderRequest(
            model=model, system=DRAFT_SYSTEM,
            chart_context=chart_digest(artifact) if artifact else "", messages=[
                {"role": "user", "content": prompt}], tools=[], max_tokens=1200))
    except Exception as exc:
        raise ProblemError(502, f"AI provider error: {type(exc).__name__}",
                           "ai_provider_error") from exc
    finally:
        if chain is not None:
            try:
                record_usage(request.app.state.pg_engine, m.practice_id, chain)
            except Exception:
                pass
    try:
        raw = _parse_draft(resp.text)
    except ValueError:
        raise ProblemError(502, "the assistant did not return a usable draft",
                           "ai_provider_error") from None

    preds = []
    for p in (raw.get("predictions") or [])[:20]:
        if isinstance(p, dict) and str(p.get("statement") or "").strip():
            preds.append(PredictionIn(
                statement=str(p["statement"]).strip()[:1000],
                window_start=_iso_date(p.get("window_start")),
                window_end=_iso_date(p.get("window_end"))))
    for p in preds:
        if p.window_start and p.window_end and p.window_end < p.window_start:
            p.window_start = p.window_end = None
    draft = SummaryIn(
        topics=_clean([str(x) for x in (raw.get("topics") or [])])[:20],
        remedies_given=_clean([str(x) for x in (raw.get("remedies_given") or [])])[:20],
        follow_up_date=_iso_date(raw.get("follow_up_date")), predictions=preds, source="ai")

    # Claim verifier: any "<planet> in <sign>" in the draft must match the chart.
    mismatches: list[dict] = []
    if artifact is not None:
        v = Verifier(artifact, now=now)
        texts = [*draft.topics, *draft.remedies_given, *(p.statement for p in draft.predictions)]
        for t in texts:
            for mm in scan_unstructured(t, v):
                mismatches.append({"text": t, "reason": mm.reason, "correct": mm.correct_fact})
    verification = {"status": "mismatch" if mismatches else "ok" if artifact else "no_chart",
                    "mismatches": mismatches}
    audit(db, m, "consultation_summary.drafted", "consultation", c.id, request,
          meta={"mismatches": len(mismatches)})
    return {"summary": draft, "verification": verification, "model": getattr(resp, "model", None)}


# --------------------------------------------------------------- life events
def _life_out(e: ClientLifeEvent) -> dict:
    return {"id": e.id, "client_id": e.client_id, "event_date": e.event_date, "kind": e.kind,
            "title": e.title, "notes": e.notes}


@router.get("/clients/{client_id}/life-events", response_model=list[LifeEventOut],
            tags=["consultations"], operation_id="listLifeEvents",
            summary="Life events recorded for a client, newest first")
def list_life_events(client_id: uuid.UUID, m: CurrentMember = Depends(require_roles(*CLINICAL)),
                     db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    rows = db.scalars(select(ClientLifeEvent).where(
        ClientLifeEvent.client_id == client.id, ClientLifeEvent.deleted_at.is_(None))
        .order_by(ClientLifeEvent.event_date.desc(), ClientLifeEvent.created_at.desc()))
    return [_life_out(e) for e in rows]


@router.post("/clients/{client_id}/life-events", status_code=201, response_model=LifeEventOut,
             tags=["consultations"], operation_id="createLifeEvent",
             summary="Record a life event (marriage, job change, move...)")
def create_life_event(client_id: uuid.UUID, body: LifeEventIn, request: Request,
                      m: CurrentMember = Depends(require_roles(*CLINICAL)),
                      db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    e = ClientLifeEvent(practice_id=m.practice_id, client_id=client.id,
                        event_date=body.event_date, kind=body.kind, title=body.title.strip(),
                        notes=(body.notes or "").strip() or None)
    db.add(e)
    db.flush()
    audit(db, m, "life_event.created", "client_life_event", e.id, request,
          meta={"client_id": str(client.id), "kind": e.kind})
    db.refresh(e)
    return _life_out(e)


def _life_event(db: Session, m: CurrentMember, event_id: uuid.UUID) -> ClientLifeEvent:
    e = db.scalar(select(ClientLifeEvent).where(
        ClientLifeEvent.id == event_id, ClientLifeEvent.deleted_at.is_(None)))
    if e is None:
        raise ProblemError(404, "life event not found", "not_found")
    load_client(db, m, e.client_id)
    return e


@router.patch("/life-events/{event_id}", response_model=LifeEventOut, tags=["consultations"],
              operation_id="updateLifeEvent", summary="Edit a life event")
def patch_life_event(event_id: uuid.UUID, body: LifeEventPatch, request: Request,
                     m: CurrentMember = Depends(require_roles(*CLINICAL)),
                     db: Session = Depends(tenant_db, scope="function")):
    e = _life_event(db, m, event_id)
    for f in body.model_fields_set:
        v = getattr(body, f)
        if f in ("event_date", "kind", "title") and v is None:
            continue
        setattr(e, f, v.strip() if isinstance(v, str) else v)
    if not e.notes:
        e.notes = None
    db.flush()
    audit(db, m, "life_event.updated", "client_life_event", e.id, request)
    db.refresh(e)
    return _life_out(e)


@router.delete("/life-events/{event_id}", status_code=204, tags=["consultations"],
               operation_id="deleteLifeEvent", summary="Remove a life event")
def delete_life_event(event_id: uuid.UUID, request: Request,
                      m: CurrentMember = Depends(require_roles(*CLINICAL)),
                      db: Session = Depends(tenant_db, scope="function")) -> None:
    e = _life_event(db, m, event_id)
    e.deleted_at = datetime.now(tz=UTC)
    audit(db, m, "life_event.deleted", "client_life_event", e.id, request)


# ------------------------------------------------------------------ timeline
@router.get("/clients/{client_id}/timeline", response_model=list[TimelineEvent],
            tags=["consultations"], operation_id="getClientTimeline",
            summary="One timeline of consultations, predictions, remedies, reports and life "
                    "events, newest first. Assistants see consultations, remedies and reports only")
def client_timeline(client_id: uuid.UUID, limit: int = Query(default=200, ge=1, le=500),
                    m: CurrentMember = Depends(require_roles(*STAFF)),
                    db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    clinical = m.role in CLINICAL
    events: list[dict] = []

    visits = list(db.scalars(select(Consultation).where(
        Consultation.client_id == client.id, Consultation.deleted_at.is_(None))))
    summaries = {s.consultation_id: s for s in db.scalars(select(ConsultationSummary).where(
        ConsultationSummary.consultation_id.in_([c.id for c in visits] or [uuid.uuid4()])))} \
        if clinical else {}
    for c in visits:
        s = summaries.get(c.id)
        detail = "; ".join(_json_list(s.topics)) if s else None
        events.append({"id": f"consultation:{c.id}", "kind": "consultation",
                       "at": c.scheduled_at or c.consulted_at, "title": c.topic or "Consultation",
                       "detail": detail or None, "status": None, "ref_id": c.id})

    plans = db.scalars(select(RemedyPlan).where(
        RemedyPlan.client_id == client.id, RemedyPlan.deleted_at.is_(None)))
    for p in plans:
        at = (datetime.combine(p.start_date, datetime.min.time(), tzinfo=UTC)
              if p.start_date else p.created_at)
        events.append({"id": f"remedy:{p.id}", "kind": "remedy", "at": at, "title": p.title,
                       "detail": f"{p.cycle_days} days", "status": p.status.value, "ref_id": p.id})

    reports = db.scalars(select(Report).where(
        Report.deleted_at.is_(None), Report.chart_artifact_id.in_(
            select(ChartArtifact.id).join(
                BirthRecord, (BirthRecord.id == ChartArtifact.birth_record_id)
                & (BirthRecord.practice_id == ChartArtifact.practice_id))
            .where(BirthRecord.client_id == client.id))))
    for r in reports:
        events.append({"id": f"report:{r.id}", "kind": "report", "at": r.created_at,
                       "title": f"{_cap(r.template)} report", "detail": r.language.upper(),
                       "status": r.status, "ref_id": r.id})

    if clinical:
        for p in db.scalars(select(ConsultPrediction).where(
                ConsultPrediction.client_id == client.id, ConsultPrediction.deleted_at.is_(None))):
            win = (f"{p.window_start.isoformat() if p.window_start else '...'} to "
                   f"{p.window_end.isoformat() if p.window_end else '...'}")
            events.append({"id": f"prediction:{p.id}", "kind": "prediction", "at": p.created_at,
                           "title": p.statement, "detail": win, "status": p.status,
                           "ref_id": p.id})
        for e in db.scalars(select(ClientLifeEvent).where(
                ClientLifeEvent.client_id == client.id, ClientLifeEvent.deleted_at.is_(None))):
            events.append({"id": f"life_event:{e.id}", "kind": "life_event",
                           "at": datetime.combine(e.event_date, datetime.min.time(), tzinfo=UTC),
                           "title": e.title, "detail": e.notes, "status": e.kind, "ref_id": e.id})
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]
