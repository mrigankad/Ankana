"""Chart depth views: planet detail, ashtakavarga grids and dasha drill-down, each with the
working behind every number. Derived from the stored chart artifact (no ephemeris call)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentMember, tenant_db
from app.auth.deps import current_member
from nakshatra_core.depth import ashtakavarga_depth, dashas_depth, planet_depth

from .charts import load_chart
from .common import ProblemError

router = APIRouter()


class ProofInput(BaseModel):
    key: str
    value: str | int | float | bool | None = None


class Proof(BaseModel):
    rule_id: str
    source: str
    inputs: list[ProofInput]


class CombustOut(BaseModel):
    applicable: bool
    is_combust: bool
    separation: float | None = Field(description="Degrees from the Sun")
    orb: float | None = Field(description="Classical orb in degrees (direct or retrograde)")


class PlanetProofs(BaseModel):
    nakshatra: Proof
    pada: Proof
    nakshatra_lord: Proof
    sign_lord: Proof
    retrograde: Proof
    combust: Proof
    dignity: Proof
    avastha: Proof
    karaka: Proof
    house_lordship: Proof


class PlanetDepthOut(BaseModel):
    planet: str
    sign: str
    sign_index: int
    degrees_in_sign: float
    longitude: float
    house: int
    nakshatra: str
    nakshatra_index: int
    pada: int
    nakshatra_lord: str
    sign_lord: str
    retrograde: bool
    combust: CombustOut
    dignity: str
    avastha: str | None = Field(description="Baladi avastha; null for the nodes")
    karaka: str | None = Field(description="Jaimini chara karaka (seven scheme); null for the nodes")
    karaka_abbr: str | None
    lord_of_houses: list[int]
    proof: PlanetProofs


class LagnaDepthOut(BaseModel):
    sign: str
    sign_index: int
    nakshatra: str
    pada: int


class PlanetsDepthOut(BaseModel):
    chart_id: uuid.UUID
    lagna: LagnaDepthOut
    planets: list[PlanetDepthOut]


class BhinnaOut(BaseModel):
    planet: str
    bindus_by_sign: list[int] = Field(description="12 values, Aries first")
    total: int
    contributors: list[list[str]] = Field(
        description="Per sign, which of the seven planets and the lagna gave a bindu")
    sign_of_planet: int


class AshtakavargaThresholds(BaseModel):
    sarva_high: int
    sarva_low: int
    bhinna_high: int
    bhinna_low: int


class AshtakavargaOut(BaseModel):
    chart_id: uuid.UUID
    lagna_sign_index: int
    sign_names: list[str]
    bhinna: list[BhinnaOut]
    sarva: list[int]
    sarva_total: int
    thresholds: AshtakavargaThresholds
    planets_order: list[str]
    proof: Proof


class DashaNodeOut(BaseModel):
    level: Literal["mahadasha", "antardasha", "pratyantardasha"]
    planet: str
    name: str | None = Field(default=None, description="Yogini name for the Yogini system")
    start: datetime
    end: datetime
    years: float
    state: Literal["past", "current", "future"]
    children: list[DashaNodeOut] | None = None


class DashaPathOut(BaseModel):
    level: str
    planet: str
    name: str | None = None
    start: datetime
    end: datetime


class DashaRuleOut(BaseModel):
    id: Literal["vimshottari", "yogini"]
    source: str
    total_years: int
    years: dict[str, float]
    year_length_days: float
    levels: int


class DashaBirthOut(BaseModel):
    nakshatra: str
    lord: str


class DashasOut(BaseModel):
    chart_id: uuid.UUID
    system: Literal["vimshottari", "yogini"]
    asof: datetime
    birth: DashaBirthOut
    balance_years: float
    rule: DashaRuleOut
    lord_cycle: list[str]
    current: list[DashaPathOut]
    mahadashas: list[DashaNodeOut]


DashaNodeOut.model_rebuild()


@router.get("/charts/{chart_id}/planets", response_model=PlanetsDepthOut, tags=["charts"],
            operation_id="getChartPlanets",
            summary="Planet detail: nakshatra, pada, lords, retrograde, combustion with orb, "
                    "dignity, baladi avastha, chara karaka and house lordships, each with its proof")
def get_planets(chart_id: uuid.UUID, m: CurrentMember = Depends(current_member),
                db: Session = Depends(tenant_db, scope="function")):
    chart, _ = load_chart(db, m, chart_id)
    return {"chart_id": chart.id, **planet_depth(chart.payload)}


@router.get("/charts/{chart_id}/ashtakavarga", response_model=AshtakavargaOut, tags=["charts"],
            operation_id="getChartAshtakavarga",
            summary="Bhinnashtakavarga grids per planet and the Sarvashtakavarga, with the "
                    "contributors behind every bindu")
def get_ashtakavarga(chart_id: uuid.UUID, m: CurrentMember = Depends(current_member),
                     db: Session = Depends(tenant_db, scope="function")):
    chart, _ = load_chart(db, m, chart_id)
    return {"chart_id": chart.id, **ashtakavarga_depth(chart.payload)}


@router.get("/charts/{chart_id}/dashas", response_model=DashasOut, tags=["charts"],
            operation_id="getChartDashas",
            summary="Dasha tree with exact dates and the running period marked: Vimshottari "
                    "(maha, antar, pratyantar) or Yogini (maha, antar)")
def get_dashas(chart_id: uuid.UUID,
               system: Literal["vimshottari", "yogini"] = Query(default="vimshottari"),
               asof: datetime | None = Query(default=None,
                                             description="ISO instant to mark as running; now if omitted"),
               m: CurrentMember = Depends(current_member),
               db: Session = Depends(tenant_db, scope="function")):
    chart, _ = load_chart(db, m, chart_id)
    when = asof
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    try:
        out = dashas_depth(chart.payload, system, when)
    except KeyError as exc:
        raise ProblemError(422, f"chart has no {system} dasha", "dasha_missing") from exc
    return {"chart_id": chart.id, **out}
