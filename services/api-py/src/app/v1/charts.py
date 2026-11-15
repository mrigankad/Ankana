"""Chart generation (idempotent), chart views, Lal Kitab and the AI assistant,
all on the tenant (RLS) session."""

from __future__ import annotations

import hashlib
import json
import queue
import threading
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ankana_ai.assistant import ask
from ankana_ai.providers import provider_from_env
from ankana_lalkitab import VARSHPHAL_MAX_AGE, lal_kitab_report
from ankana_lalkitab.i18n import localize_report
from app.ai_connections import chain_for_role, record_usage
from app.auth import CurrentMember, require_roles, tenant_db
from app.auth.deps import current_member
from app.billing.entitlements import require_entitlement
from app.tenancy.models import BirthRecord, ChartArtifact, Client, ConsentPurpose, Member, Role
from nakshatra_core.chart import ENGINE_VERSION, compute_vedic_chart_artifact
from nakshatra_core.providers import NotSupportedError, get_provider
from nakshatra_core.sky import chart_transit_timeline
from nakshatra_core.transit_depth import double_transit, gochara_snapshot, sade_sati_lifetime
from nakshatra_core.transits import compute_transit_snapshot
from nakshatra_i18n import normalize_lang
from nakshatra_interpret import build_reading
from nakshatra_rules import evaluate_predictions_enriched, evaluate_remedies

from . import schemas as sc
from .clients import latest_birth_record
from .common import (
    CLINICAL,
    ProblemError,
    audit,
    bump_usage,
    idempotent,
    load_client,
    paginate,
    require_consent,
)

router = APIRouter()

SCHEMA_VERSION = 1


def settings_hash(settings: dict) -> str:
    return hashlib.sha256(
        json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _chart_out(chart: ChartArtifact, client_id: uuid.UUID, created: bool) -> dict:
    return {
        "id": chart.id, "client_id": client_id, "birth_record_id": chart.birth_record_id,
        "settings_hash": chart.settings_hash, "settings": chart.payload.get("settings", {}),
        "engine_version": chart.engine_version, "schema_version": chart.schema_version,
        "created_at": chart.created_at, "created": created,
    }


def _compute(record: BirthRecord, settings: dict) -> dict:
    unknown_time = record.birth_time is None
    inp = {
        "birthDate": record.birth_date.isoformat(),
        "birthTime": "12:00" if unknown_time else record.birth_time.strftime("%H:%M"),
        "timezoneName": record.timezone_name,
        "latitude": record.latitude, "longitude": record.longitude,
        "placeLabel": record.place_label,
        "ayanamsa": settings["ayanamsa"], "nodeType": settings["node_type"],
        "chartStyle": settings["chart_style"],
    }
    if unknown_time:
        inp["timeUnknown"] = True
    try:
        artifact = compute_vedic_chart_artifact(inp)
    except NotSupportedError as exc:
        raise ProblemError(422, str(exc), "unsupported_setting") from exc
    except (KeyError, ValueError) as exc:
        raise ProblemError(422, f"cannot compute chart: {exc}", "chart_compute_failed") from exc
    artifact["settings"] = settings
    return artifact


def _owned_by_client_role(db: Session, m: CurrentMember, client_id: uuid.UUID) -> None:
    if m.role == Role.client:
        own = db.scalar(select(Member.client_id).where(Member.id == m.member_id))
        if own != client_id:
            raise ProblemError(404, "chart not found", "not_found")


def load_chart(db: Session, m: CurrentMember, chart_id: uuid.UUID
               ) -> tuple[ChartArtifact, BirthRecord]:
    """A chart in the caller's practice whose client is live; client role: own only."""
    row = db.execute(
        select(ChartArtifact, BirthRecord)
        .join(BirthRecord, (BirthRecord.id == ChartArtifact.birth_record_id)
              & (BirthRecord.practice_id == ChartArtifact.practice_id))
        .join(Client, (Client.id == BirthRecord.client_id)
              & (Client.practice_id == BirthRecord.practice_id))
        .where(ChartArtifact.id == chart_id, Client.deleted_at.is_(None))
    ).first()
    if row is None:
        raise ProblemError(404, "chart not found", "not_found")
    _owned_by_client_role(db, m, row[1].client_id)
    return row[0], row[1]


# ------------------------------------------------------------ generation
@router.post("/clients/{client_id}/charts", response_model=sc.ChartEnvelope, status_code=201,
             tags=["charts"], operation_id="generateChart",
             summary="Generate a chart (idempotent on birth record, settings and engine "
                     "version; 200 when an existing artifact is returned)")
def generate_chart(client_id: uuid.UUID, body: sc.ChartCreateIn, request: Request,
                   response: Response,
                   idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                   m: CurrentMember = Depends(require_roles(*CLINICAL)),
                   db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    require_consent(db, client.id, ConsentPurpose.chart_compute)
    if body.birth_record_id:
        record = db.scalar(select(BirthRecord).where(
            BirthRecord.id == body.birth_record_id, BirthRecord.client_id == client.id,
            BirthRecord.deleted_at.is_(None)))
    else:
        record = latest_birth_record(db, client.id)
    if record is None:
        raise ProblemError(404, "birth record not found", "not_found")
    try:
        provider_name = get_provider().name
    except ValueError as exc:
        raise ProblemError(422, str(exc), "unsupported_setting") from exc
    settings = {"ayanamsa": body.ayanamsa, "node_type": body.node_type,
                "chart_style": body.chart_style, "ephemeris": provider_name}
    digest = settings_hash(settings)

    def run() -> tuple[int, dict]:
        existing = db.scalar(select(ChartArtifact).where(
            ChartArtifact.birth_record_id == record.id,
            ChartArtifact.settings_hash == digest,
            ChartArtifact.engine_version == ENGINE_VERSION))
        if existing is not None:
            return 200, _chart_out(existing, client.id, False)
        payload = _compute(record, settings)
        chart = ChartArtifact(
            practice_id=m.practice_id, birth_record_id=record.id, settings_hash=digest,
            engine_version=ENGINE_VERSION, schema_version=SCHEMA_VERSION, payload=payload)
        try:
            with db.begin_nested():  # lost a race with a concurrent identical request
                db.add(chart)
                db.flush()
        except IntegrityError:
            existing = db.scalar(select(ChartArtifact).where(
                ChartArtifact.birth_record_id == record.id,
                ChartArtifact.settings_hash == digest,
                ChartArtifact.engine_version == ENGINE_VERSION))
            return 200, _chart_out(existing, client.id, False)
        db.refresh(chart)
        audit(db, m, "chart.generated", "chart_artifact", chart.id, request,
              meta={"client_id": str(client.id), "birth_record_id": str(record.id),
                    "settings_hash": digest, "engine_version": ENGINE_VERSION})
        bump_usage(db, m.practice_id, "charts")
        return 201, _chart_out(chart, client.id, True)

    status, out, _replayed = idempotent(
        db, m, f"POST /v1/clients/{client.id}/charts", idempotency_key,
        {"record": str(record.id), "settings": settings}, run)
    response.status_code = status
    return {"chart": out}


@router.get("/clients/{client_id}/charts", response_model=sc.ChartPage, tags=["charts"],
            operation_id="listCharts", summary="Chart artifacts for a client (newest first)")
def list_charts(client_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200),
                cursor: str | None = None, m: CurrentMember = Depends(current_member),
                db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    stmt = select(ChartArtifact).where(ChartArtifact.birth_record_id.in_(
        select(BirthRecord.id).where(BirthRecord.client_id == client.id)))
    rows, nxt = paginate(db, stmt, ChartArtifact, limit, cursor)
    return {"charts": [_chart_out(c, client.id, False) for c in rows], "next_cursor": nxt}


# ----------------------------------------------------------------- views
@router.get("/charts/{chart_id}", response_model=sc.ChartDetail, tags=["charts"],
            operation_id="getChart", summary="Chart artifact with the interpretive reading")
def get_chart(chart_id: uuid.UUID, lang: str | None = Query(default=None, description="en or hi"),
              m: CurrentMember = Depends(current_member),
              db: Session = Depends(tenant_db, scope="function")):
    chart, record = load_chart(db, m, chart_id)
    code = normalize_lang(lang)
    return {"chart": _chart_out(chart, record.client_id, False), "language": code,
            "artifact": chart.payload, "reading": build_reading(chart.payload, lang=code)}


@router.get("/charts/{chart_id}/predictions", tags=["charts"], operation_id="getChartPredictions",
            summary="Rule-based predictions over a horizon")
def get_predictions(chart_id: uuid.UUID,
                    horizon_years: float = Query(default=5, gt=0, le=30),
                    lang: str | None = Query(default=None, description="en or hi"),
                    m: CurrentMember = Depends(current_member),
                    db: Session = Depends(tenant_db, scope="function")) -> dict:
    chart, _ = load_chart(db, m, chart_id)
    code = normalize_lang(lang)
    return {"language": code, "predictions": evaluate_predictions_enriched(
        chart.payload, horizon_years=horizon_years, lang=code)}


@router.get("/charts/{chart_id}/remedies", tags=["charts"], operation_id="getChartRemedies",
            summary="Rule-based remedy suggestions")
def get_remedies(chart_id: uuid.UUID, lang: str | None = Query(default=None, description="en or hi"),
                 m: CurrentMember = Depends(current_member),
                 db: Session = Depends(tenant_db, scope="function")) -> dict:
    chart, _ = load_chart(db, m, chart_id)
    code = normalize_lang(lang)
    return {"language": code, "remedies": evaluate_remedies(chart.payload, code)}


@router.get("/charts/{chart_id}/transits", tags=["charts"], operation_id="getChartTransits",
            summary="Transit snapshot against the natal chart")
def get_transits(chart_id: uuid.UUID,
                 date: datetime | None = Query(default=None, description="ISO instant; now if omitted"),
                 m: CurrentMember = Depends(current_member),
                 db: Session = Depends(tenant_db, scope="function")) -> dict:
    chart, _ = load_chart(db, m, chart_id)
    when = date or datetime.now(tz=UTC).replace(second=0, microsecond=0)  # one snapshot a minute
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return {"transits": compute_transit_snapshot(chart.payload, when)}


@router.get("/charts/{chart_id}/transits/timeline", response_model=sc.TransitTimelineOut,
            tags=["charts"], operation_id="getChartTransitTimeline",
            summary="Upcoming transits against the natal chart: sign and house ingresses, "
                    "stations, drishti onto the natal Moon and lagna, sade sati phases")
def get_transit_timeline(chart_id: uuid.UUID,
                         months: int = Query(default=12, ge=1, le=24,
                                             description="Months ahead of `start`"),
                         start: datetime | None = Query(
                             default=None, description="ISO instant; now if omitted"),
                         m: CurrentMember = Depends(current_member),
                         db: Session = Depends(tenant_db, scope="function")):
    chart, _ = load_chart(db, m, chart_id)
    begin = start or datetime.now(tz=UTC)
    if begin.tzinfo is None:
        begin = begin.replace(tzinfo=UTC)
    return {"chart_id": chart.id, **chart_transit_timeline(chart.payload, begin, months)}


def _utc_or_now(value: datetime | None) -> datetime:
    when = value or datetime.now(tz=UTC)
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when


@router.get("/charts/{chart_id}/transits/sade-sati", response_model=sc.SadeSatiLifetimeOut,
            tags=["charts"], operation_id="getChartSadeSati",
            summary="Lifetime Sade Sati and dhaiya periods with phase dates, status and the next one")
def get_sade_sati(chart_id: uuid.UUID,
                  as_of: datetime | None = Query(default=None, description="ISO instant; now if omitted"),
                  m: CurrentMember = Depends(current_member),
                  db: Session = Depends(tenant_db, scope="function")):
    chart, _ = load_chart(db, m, chart_id)
    return {"chart_id": chart.id, **sade_sati_lifetime(chart.payload, _utc_or_now(as_of))}


@router.get("/charts/{chart_id}/transits/gochara", response_model=sc.GocharaOut,
            tags=["charts"], operation_id="getChartGochara",
            summary="Gochara on a date: sign, ashtakavarga bindus, vedha and a verdict per planet "
                    "(pass `date` for a what-if)")
def get_gochara(chart_id: uuid.UUID,
                date: datetime | None = Query(default=None, description="ISO instant; now if omitted"),
                m: CurrentMember = Depends(current_member),
                db: Session = Depends(tenant_db, scope="function")):
    chart, _ = load_chart(db, m, chart_id)
    when = _utc_or_now(date)
    if not 1900 <= when.year <= 2200:
        raise ProblemError(400, "date must fall between the years 1900 and 2200.", "invalid_date")
    return {"chart_id": chart.id, **gochara_snapshot(chart.payload, when.replace(second=0, microsecond=0))}


@router.get("/charts/{chart_id}/transits/double", response_model=sc.DoubleTransitOut,
            tags=["charts"], operation_id="getChartDoubleTransit",
            summary="Houses that Jupiter and Saturn both occupy or aspect, by window")
def get_double_transit(chart_id: uuid.UUID,
                       months: int = Query(default=24, ge=1, le=36),
                       start: datetime | None = Query(default=None, description="ISO instant; now if omitted"),
                       reference: Literal["lagna", "moon"] = "lagna",
                       m: CurrentMember = Depends(current_member),
                       db: Session = Depends(tenant_db, scope="function")):
    chart, _ = load_chart(db, m, chart_id)
    return {"chart_id": chart.id, **double_transit(chart.payload, _utc_or_now(start), months, reference)}


@router.get("/charts/{chart_id}/lal-kitab", tags=["lal-kitab"], operation_id="getLalKitab",
            summary="Lal Kitab report (origin lagna_h1|aries_h1, optional Varshphal age)")
def get_lal_kitab(chart_id: uuid.UUID, origin: str | None = None,
                  age: int | None = Query(default=None),
                  lang: str | None = Query(default=None, description="en or hi"),
                  m: CurrentMember = Depends(current_member),
                  db: Session = Depends(tenant_db, scope="function")) -> dict:
    chart, _ = load_chart(db, m, chart_id)
    if origin is not None and origin not in ("lagna_h1", "aries_h1"):
        raise ProblemError(400, "origin must be lagna_h1 or aries_h1.", "invalid_origin")
    if age is not None and not 1 <= age <= VARSHPHAL_MAX_AGE:
        raise ProblemError(
            400, f"age must be an integer from 1 to {VARSHPHAL_MAX_AGE}.", "invalid_age")
    report = lal_kitab_report(chart.payload, origin=origin, age=age)
    out = {"chartId": str(chart_id),
           "lalKitab": report.model_dump(by_alias=True, mode="json")}
    if normalize_lang(lang) == "hi":
        out = localize_report(out, "hi")
        out["language"] = "hi"
        out["needsReviewHi"] = True
    return out


# ------------------------------------------------------------- assistant
class HistoryTurn(BaseModel):
    role: str
    content: str


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list)
    deep: bool = False
    stream: bool = False


@lru_cache(maxsize=1)
def _lalkitab_provider():
    from ankana_ai.tools import load_lalkitab

    return load_lalkitab()


def _provider_error_text(exc: Exception) -> str:
    """What a caller may see: our own curated provider messages, never raw SDK or library
    exception text (which can carry URLs, headers or response bodies)."""
    from ankana_ai.llm_providers import ProviderError

    return str(exc)[:300] if isinstance(exc, ProviderError) else type(exc).__name__


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/charts/{chart_id}/ask", tags=["assistant"], operation_id="askChart",
             dependencies=[Depends(require_entitlement("ai_asks"))],
             summary="Ask the assistant about a chart (needs ai_assistant consent). JSON, or "
                     "SSE when stream=true or Accept: text/event-stream",
             responses={503: {"description": "AI provider not configured"},
                        502: {"description": "AI provider failed"}})
def ask_chart(chart_id: uuid.UUID, body: AskIn, request: Request,
              m: CurrentMember = Depends(current_member),
              db: Session = Depends(tenant_db, scope="function")):
    chart, record = load_chart(db, m, chart_id)
    require_consent(db, record.client_id, ConsentPurpose.ai_assistant)
    # A practice's own connections (routed role "synthesise", with fallback) win over the
    # server default provider.
    chain = chain_for_role(db, "synthesise")
    factory = getattr(request.app.state, "ai_provider_factory", provider_from_env)
    provider = chain or factory()
    if provider is None:
        raise ProblemError(
            503, "AI provider not configured (set ANTHROPIC_API_KEY, OLLAMA_BASE_URL "
                 "or ANKANA_AI_PROVIDER)", "ai_unavailable")
    artifact = chart.payload
    wants_stream = body.stream or "text/event-stream" in request.headers.get("accept", "")
    history = [t.model_dump() for t in body.history]

    def run(on_status=None):
        return ask(provider, artifact, body.question, now=datetime.now(tz=UTC),
                   history=history, lalkitab=_lalkitab_provider(), deep=body.deep,
                   on_status=on_status)

    # Count the call up front: the metering row commits with this request even
    # when the answer streams after the DB transaction has closed.
    bump_usage(db, m.practice_id, "ai_asks")
    engine = request.app.state.pg_engine

    def meter() -> None:
        if chain is not None:
            try:
                record_usage(engine, m.practice_id, chain)
            except Exception:  # metering must never fail an answer
                pass

    if not wants_stream:
        try:
            result = run()
        except Exception as exc:  # provider/network failure
            meter()
            raise ProblemError(502, f"AI provider error: {_provider_error_text(exc)}",
                               "ai_provider_error") from exc
        meter()
        tokens = sum(int(v) for k, v in (result.usage or {}).items()
                     if k in ("input_tokens", "output_tokens") and isinstance(v, int | float))
        if tokens:
            bump_usage(db, m.practice_id, "ai_tokens", tokens)
        return jsonable_encoder(result.as_dict())

    events: queue.Queue = queue.Queue()

    def worker() -> None:
        try:
            result = run(lambda msg: events.put(("status", {"message": msg})))
            events.put(("answer", result.as_dict()))
        except Exception as exc:
            events.put(("error", {"message": f"AI provider error: {_provider_error_text(exc)}"}))
        finally:
            meter()
            events.put(("done", {}))

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            event, data = events.get()
            yield _sse(event, data)
            if event == "done":
                return

    return StreamingResponse(stream(), media_type="text/event-stream")
