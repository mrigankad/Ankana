"""Pydantic output models.

Field names are the snake_case form of the TS camelCase keys (planetHouse ->
planet_house, annualChart -> annual_chart, ...). Python keywords keep their TS
name through an alias: ``from_`` -> "from", ``with_`` -> "with". Dump with
``model_dump(by_alias=True)`` (all other keys are unaliased).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Planet = Literal["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]
Origin = Literal["lagna_h1", "aries_h1"]
Num = int | float


class M(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class Cite(BaseModel):
    model_config = ConfigDict(extra="allow")
    vol: str
    printed_page: int | None = None
    pdf_page: int | None = None
    section: str
    ocr_confidence: str
    verified_from_image: bool


class LkPlacement(M):
    planet: Planet
    house: int
    sign_index: int | None  # TS signIndex


class LkChart(M):
    origin: Origin
    lagna_sign_index: int | None  # TS lagnaSignIndex
    placements: list[LkPlacement]
    houses: list[list[Planet]]  # index 0 unused
    planet_house: dict[str, int]  # TS planetHouse


class LkAspectEnd(M):
    planet: Planet
    house: int


class LkAspect(M):
    from_: LkAspectEnd = Field(alias="from")
    to: LkAspectEnd
    strength: Num
    derived: bool
    cite: Cite
    needs_review: bool


class SleepingPlanet(M):
    planet: Planet
    house: int
    status: Literal["awake", "dormant"]
    rule: str
    awakener: Planet
    awakener_present: bool
    self_awakening_age: Num
    needs_review: bool
    cite: Cite


class SleepingHouse(M):
    house: int
    occupied: bool
    status: Literal["active", "dormant"]
    awakener: Planet
    awakener_present: bool
    needs_review: bool
    cite: Cite


class RinFinding(M):
    id: str
    planet: Planet
    kind: str
    basis: Literal["table", "first_degree_father", "indicator"]
    house: int
    with_: list[Planet] = Field(alias="with")
    cause: str
    symptoms: str
    remedy: str
    remedy_cite: Cite
    cite: Cite
    needs_review: bool


class MasnuiFinding(M):
    id: str
    formed_planet: Planet
    variant: str | None
    components: list[Planet]
    house: int
    formed_planet_present: bool
    cite: Cite
    needs_review: bool


class Cycle35Position(M):
    rotation: int
    year_in_cycle: int
    cycle_planet: Planet
    part: Literal["beginning", "middle", "last"]
    part_ruler: Planet
    needs_review: bool


class VarshphalPlanet(M):
    planet: Planet
    natal_house: int
    annual_house: int
    month: str


class VarshphalResult(M):
    age: int
    row: list[int]
    planets: list[VarshphalPlanet]
    annual_chart: LkChart
    cycle35: Cycle35Position
    semantics: str


class Delivery(M):
    house: int
    method: str | None
    cite: Cite


class Upay(M):
    rank: int
    kind: Literal["rin", "rin_polluter", "sleeping_planet", "house_entry", "masnui"]
    planet: Planet
    house: int
    title: str
    action: str
    why: str
    delivery: Delivery | None
    duration_days: Num
    cites: list[Cite]
    needs_review: bool


class OneAtATime(M):
    rule: str
    duration_days: list[Num]
    gap: str
    cite: Cite


class ScheduleItem(M):
    phase: int
    upay_rank: int
    days: Num
    then_pause: str


class RemedyCoverage(M):
    planet_house_entries_done: int
    planet_house_entries_total: int


class UpayPlan(M):
    upay: list[Upay]
    one_at_a_time: OneAtATime
    schedule: list[ScheduleItem]
    coverage: RemedyCoverage


class MatchedCondition(M):
    effect: str
    tone: str
    needs_review: bool


class EntryMatch(M):
    entry: dict[str, Any]
    matched: list[MatchedCondition]


class PlanetHouseMatch(M):
    id: str
    planet: Planet
    house: int
    theme: str | None
    matched: list[MatchedCondition]
    cite: Cite


class ReportCoverage(M):
    planet_house_done: int
    planet_house_total: int


class LalKitabReport(M):
    origin: Origin
    chart: LkChart
    sleeping_planets: list[SleepingPlanet]
    sleeping_houses: list[SleepingHouse]
    aspects: list[LkAspect]
    rin: list[RinFinding]
    masnui: list[MasnuiFinding]
    planet_house: list[PlanetHouseMatch]
    varshphal: VarshphalResult | None
    varshphal_age_requested: int | None
    remedies: UpayPlan
    coverage: ReportCoverage
