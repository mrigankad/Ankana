"""Request and response models for the tenant /v1 API. Names here become the
component names in openapi.json, so keep them stable (client generation)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from app.tenancy.models import ConsentPurpose, RemedyStatus, TimeSource


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Problem(BaseModel):
    """RFC 9457 problem details (application/problem+json)."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str = Field(description="Stable machine-readable error code")
    errors: list[dict[str, Any]] | None = None
    purpose: str | None = None


def _env(name: str, **fields: Any) -> type[BaseModel]:
    return create_model(name, **fields)


# -------------------------------------------------------------- clients
class ClientIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    preferred_language: str | None = Field(default=None, max_length=16)


class ClientPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    preferred_language: str | None = Field(default=None, max_length=16)


class ClientOut(_Out):
    id: uuid.UUID
    display_name: str
    contact_email: str | None
    contact_phone: str | None
    timezone: str | None
    preferred_language: str | None
    created_at: datetime
    updated_at: datetime


ClientEnvelope = _env("ClientEnvelope", client=(ClientOut, ...))


class DashaNow(BaseModel):
    maha: str = Field(description="Running mahadasha lord, lower case")
    antar: str | None = Field(default=None, description="Running antardasha lord")
    antar_ends: datetime | None = None


class ClientRowOut(ClientOut):
    """A client with what the list needs without opening each chart."""

    tags: list[str] = []
    latest_chart_id: uuid.UUID | None = None
    lagna_sign: str | None = Field(default=None, description="Sidereal lagna sign of the latest chart")
    lagna_degree: float | None = Field(default=None, description="Degrees within the lagna sign")
    current_dasha: DashaNow | None = None
    last_consultation_at: datetime | None = None
    next_consultation_at: datetime | None = Field(
        default=None, description="Booked visit in the future, if any")
    next_follow_up: date | None = Field(
        default=None, description="Earliest follow-up date not yet followed by a consultation")
    needs_rectify: bool = Field(
        default=False, description="Birth time is approximate or unknown, or rectification is open")


class TagCount(BaseModel):
    tag: str
    count: int


class ClientFacets(BaseModel):
    total: int
    needs_rectify: int
    follow_up_due: int = Field(description="Open follow-up due within 7 days, overdue included")
    tags: list[TagCount]


ClientPage = _env("ClientPage", clients=(list[ClientRowOut], ...),
                  next_cursor=(str | None, None), facets=(ClientFacets, ...))


class TagsIn(BaseModel):
    tags: list[str] = Field(max_length=20)


TagsOut = _env("TagsOut", tags=(list[str], ...))
TagCountList = _env("TagCountList", tags=(list[TagCount], ...))


# -------------------------------------------------------------- consents
class ConsentIn(BaseModel):
    purpose: ConsentPurpose
    notice_version: str = Field(min_length=1, max_length=32,
                                description="Version id of the notice shown to the client")
    notice_text: str | None = Field(default=None, max_length=20000,
                                    description="Verbatim notice text, kept as evidence")
    notice_language: str | None = Field(default=None, max_length=16)
    channel: str | None = Field(default=None, max_length=32,
                                description="e.g. in_person, whatsapp, portal")


class ConsentOut(_Out):
    id: uuid.UUID
    client_id: uuid.UUID
    purpose: ConsentPurpose
    notice_version: str
    notice_text: str | None
    notice_language: str | None
    granted_at: datetime
    withdrawn_at: datetime | None
    channel: str | None


ConsentEnvelope = _env("ConsentEnvelope", consent=(ConsentOut, ...))
ConsentList = _env(
    "ConsentList", consents=(list[ConsentOut], ...),
    active=(dict[str, bool], ...))


# --------------------------------------------------------- birth records
class BirthRecordIn(BaseModel):
    birth_date: date
    birth_time: time | None = Field(
        default=None, description="Local clock time; omit when time_source is unknown")
    time_source: TimeSource
    place_label: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone_name: str = Field(description="IANA zone, e.g. Asia/Kolkata")
    tz_source: str | None = Field(default=None, max_length=32)
    rectification_status: str | None = Field(default=None, max_length=32)


class BirthRecordOut(_Out):
    id: uuid.UUID
    client_id: uuid.UUID
    version: int
    supersedes_id: uuid.UUID | None
    birth_date: date
    birth_time: time | None
    time_source: TimeSource
    place_label: str
    latitude: float
    longitude: float
    timezone_name: str
    tz_source: str | None
    rectification_status: str | None
    created_at: datetime


BirthRecordEnvelope = _env("BirthRecordEnvelope", birth_record=(BirthRecordOut, ...))
BirthRecordPage = _env("BirthRecordPage", birth_records=(list[BirthRecordOut], ...),
                       next_cursor=(str | None, None))


# ---------------------------------------------------------------- charts
class ChartSettings(BaseModel):
    ayanamsa: str = Field(default="lahiri", description="Must be supported by the ephemeris provider")
    node_type: Literal["mean", "true"] = "mean"
    chart_style: Literal["north", "south", "east"] = "north"


class ChartCreateIn(ChartSettings):
    birth_record_id: uuid.UUID | None = Field(
        default=None, description="Defaults to the client's latest birth record version")


class ChartOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    birth_record_id: uuid.UUID
    settings_hash: str
    settings: dict[str, Any]
    engine_version: str
    schema_version: int
    created_at: datetime
    created: bool = Field(description="false when an existing artifact was returned")


ChartEnvelope = _env("ChartEnvelope", chart=(ChartOut, ...))
ChartPage = _env("ChartPage", charts=(list[ChartOut], ...), next_cursor=(str | None, None))


class ChartDetail(BaseModel):
    chart: ChartOut
    artifact: dict[str, Any]
    reading: dict[str, Any]
    language: str = "en"


# ---------------------------------------------------------- consultations
class ConsultationIn(BaseModel):
    consulted_at: datetime | None = None
    mode: str | None = Field(default=None, max_length=32)
    topic: str | None = Field(default=None, max_length=200)
    chart_artifact_id: uuid.UUID | None = None
    scheduled_at: datetime | None = Field(
        default=None, description="When the visit is booked for; shows on Today")
    follow_up_date: date | None = Field(
        default=None, description="Practitioner follow-up; drives reminders and Needs you")
    note: str | None = Field(default=None, max_length=20000,
                             description="Optional first note, stored as a ConsultationNote")
    note_facts: list[NoteFact] = Field(default_factory=list, max_length=40)
    client_question: str | None = Field(
        default=None, max_length=2000, description="What the client says they want to ask")


FactType = Literal["planet", "dasha", "yoga", "transit", "lal_kitab"]


class NoteFact(BaseModel):
    """A chart fact pinned in a note. The body carries {{fact:<id>}} where the chip sits."""

    id: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")
    type: FactType
    ref: str = Field(min_length=1, max_length=120,
                     description="Stable reference, e.g. planet:saturn, dasha:moon/mars, "
                                 "yoga:gajakesari, transit:saturn:2027-03-29, lal_kitab:sun_h1")
    label: str = Field(min_length=1, max_length=160, description="Text shown on the chip")


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    facts: list[NoteFact] = Field(default_factory=list, max_length=40)


class NoteOut(_Out):
    id: uuid.UUID
    consultation_id: uuid.UUID
    author_member_id: uuid.UUID | None
    body: str
    facts: list[NoteFact] = []
    created_at: datetime


class ConsultationOut(_Out):
    id: uuid.UUID
    client_id: uuid.UUID
    member_id: uuid.UUID
    chart_artifact_id: uuid.UUID | None
    consulted_at: datetime
    scheduled_at: datetime | None = None
    mode: str | None
    topic: str | None
    follow_up_date: date | None = None
    client_question: str | None = None
    created_at: datetime


class ConsultationDetail(ConsultationOut):
    notes: list[NoteOut] = []


ConsultationEnvelope = _env("ConsultationEnvelope", consultation=(ConsultationDetail, ...))
ConsultationPage = _env("ConsultationPage", consultations=(list[ConsultationOut], ...),
                        next_cursor=(str | None, None))
NoteEnvelope = _env("NoteEnvelope", note=(NoteOut, ...))


# ----------------------------------------------------------- transit timeline
class TransitEventOut(BaseModel):
    date: datetime
    planet: str
    kind: Literal["ingress", "retrograde-station", "direct-station", "aspect", "conjunction",
                  "sade_sati"]
    sign: str
    sign_index: int
    house_from_lagna: int
    house_from_moon: int
    target: Literal["moon", "lagna"] | None = Field(
        default=None, description="Natal point an aspect or conjunction lands on")
    aspect: int | None = Field(default=None, description="Sign count of the drishti (1 = conjunction)")
    phase: Literal["rising", "peak", "setting"] | None = Field(
        default=None, description="Sade sati phase Saturn moves into; null when it ends")


class SadeSatiPhaseOut(BaseModel):
    phase: Literal["rising", "peak", "setting"]
    starts_at: datetime | None = Field(default=None, description="Null when already running")
    ends_at: datetime | None = Field(default=None, description="Null when beyond the window")


class SadeSatiOut(BaseModel):
    active_now: bool
    phase_now: Literal["rising", "peak", "setting"] | None
    phases: list[SadeSatiPhaseOut]


class TransitNatalOut(BaseModel):
    lagna_sign: str
    moon_sign: str


class TransitTimelineOut(BaseModel):
    chart_id: uuid.UUID
    start: datetime
    end: datetime
    months: int
    natal: TransitNatalOut
    sade_sati: SadeSatiOut
    events: list[TransitEventOut]


# ------------------------------------------------------------ transit depth
class SadeSatiPhaseWindowOut(BaseModel):
    phase: Literal["rising", "peak", "setting", "dhaiya"]
    saturn_sign: str
    starts_at: datetime
    ends_at: datetime


class SadeSatiPeriodOut(BaseModel):
    index: int
    kind: Literal["sade_sati", "dhaiya_kantaka", "dhaiya_ashtama"]
    status: Literal["past", "current", "upcoming"]
    starts_at: datetime
    ends_at: datetime
    age_start: float = Field(description="Age in years when it starts (0 if before birth)")
    age_end: float
    started_before_birth: bool
    phases: list[SadeSatiPhaseWindowOut]


class SadeSatiNowOut(BaseModel):
    kind: Literal["sade_sati", "dhaiya_kantaka", "dhaiya_ashtama"] | None
    phase: Literal["rising", "peak", "setting", "dhaiya"] | None
    saturn_sign: str
    house_from_moon: int
    period_index: int | None


class SadeSatiLifetimeOut(BaseModel):
    chart_id: uuid.UUID
    as_of: datetime
    birth: datetime
    moon_sign: str
    current: SadeSatiNowOut
    next_index: int | None = Field(description="Index in `periods` of the next sade sati or dhaiya")
    next_sade_sati_index: int | None
    periods: list[SadeSatiPeriodOut]
    proof: str


class GocharaPlanetOut(BaseModel):
    planet: str
    sign: str
    sign_index: int
    degrees_in_sign: float
    retrograde: bool
    house_from_moon: int
    house_from_lagna: int
    bindus: int | None = Field(description="Bhinna ashtakavarga bindus of this planet in the sign; null for the nodes")
    sav: int = Field(description="Sarvashtakavarga bindus of the sign")
    favourable_houses: list[int]
    favourable: bool | None
    vedha_house: int | None = Field(description="House from the Moon whose occupant obstructs this placement")
    vedha_by: list[str] = Field(description="Planets standing in the vedha house")
    verdict: Literal["favourable", "mixed", "unfavourable", "not_rated"]
    reason_code: Literal["favourable_strong", "favourable_weak_bindus", "vedha_blocked",
                         "unfavourable_softened", "unfavourable", "nodes_not_rated"]
    reason: str


class GocharaSaturnStatusOut(BaseModel):
    kind: Literal["sade_sati", "dhaiya_kantaka", "dhaiya_ashtama"] | None
    phase: Literal["rising", "peak", "setting", "dhaiya"] | None
    house_from_moon: int


class GocharaOut(BaseModel):
    chart_id: uuid.UUID
    date: datetime
    moon_sign: str
    lagna_sign: str
    planets: list[GocharaPlanetOut]
    saturn_status: GocharaSaturnStatusOut
    tally: dict[str, int]
    proof: str


class DoubleTransitWindowOut(BaseModel):
    starts_at: datetime
    ends_at: datetime


class DoubleTransitHouseOut(BaseModel):
    house: int
    sign: str
    active_now: bool
    days: int
    windows: list[DoubleTransitWindowOut]


class DoubleTransitSpanOut(BaseModel):
    starts_at: datetime
    ends_at: datetime
    jupiter_sign: str
    saturn_sign: str
    houses: list[int]


class DoubleTransitOut(BaseModel):
    chart_id: uuid.UUID
    start: datetime
    end: datetime
    months: int
    reference: Literal["lagna", "moon"]
    reference_sign: str
    jupiter_now: str
    saturn_now: str
    spans: list[DoubleTransitSpanOut]
    houses: list[DoubleTransitHouseOut]
    proof: str


# ---------------------------------------------------------------- remedies
class RemedyItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str | None = Field(default=None, max_length=5000)
    planet: str | None = Field(default=None, max_length=16)
    sort_order: int = 0


class RemedyPlanIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    consultation_id: uuid.UUID | None = None
    cycle_days: int = Field(default=43, ge=1, le=366)
    missed_day_policy: Literal["restart", "extend", "ignore", "warn"] = "restart"
    items: list[RemedyItemIn] = Field(default_factory=list, max_length=50)


class RemedyStartIn(BaseModel):
    start_date: date | None = Field(default=None, description="Defaults to today (UTC)")


class CheckinIn(BaseModel):
    checkin_date: date | None = Field(default=None, description="Defaults to today (UTC)")
    done: bool = True
    note: str | None = Field(default=None, max_length=2000)


class RemedyItemOut(_Out):
    id: uuid.UUID
    plan_id: uuid.UUID
    title: str
    instructions: str | None
    planet: str | None
    sort_order: int
    done_days: int = 0
    done_today: bool = False


class CheckinOut(_Out):
    id: uuid.UUID
    item_id: uuid.UUID
    checkin_date: date
    done: bool
    note: str | None


class RemedyPlanOut(_Out):
    id: uuid.UUID
    client_id: uuid.UUID
    consultation_id: uuid.UUID | None
    title: str
    status: RemedyStatus
    cycle_days: int
    start_date: date | None
    end_date: date | None = None
    missed_day_policy: str
    day_number: int | None = Field(default=None, description="1-based day of the cycle today")
    created_at: datetime
    items: list[RemedyItemOut] = []


RemedyPlanEnvelope = _env("RemedyPlanEnvelope", remedy_plan=(RemedyPlanOut, ...))
RemedyPlanPage = _env("RemedyPlanPage", remedy_plans=(list[RemedyPlanOut], ...),
                      next_cursor=(str | None, None))
RemedyItemEnvelope = _env("RemedyItemEnvelope", item=(RemedyItemOut, ...))
CheckinEnvelope = _env("CheckinEnvelope", checkin=(CheckinOut, ...))
