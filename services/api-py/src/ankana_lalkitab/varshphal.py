"""Annual chart (varshphal), 35-year cycle and year-of-life (port of varshphal.ts)."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from .chart import lk_chart_from_houses
from .data import PLANET_ORDER, cycle35, varshphal_data
from .models import Cycle35Position, LkChart, VarshphalPlanet, VarshphalResult

VARSHPHAL_MAX_AGE = len(varshphal_data["rows"])


def _month_of(house: int) -> str:
    for r in varshphal_data["months"]["rows"]:
        if r["house"] == house:
            return r["month"]
    return ""


def cycle35_position(age: int) -> Cycle35Position:
    rotation = (age - 1) // 35 + 1
    year_in_cycle = (age - 1) % 35 + 1
    acc = 0
    for row in cycle35:
        if year_in_cycle <= acc + row["years"]:
            within = year_in_cycle - acc
            part_len = row["years"] / 3
            idx = min(2, math.floor((within - 1) / part_len))
            return Cycle35Position(
                rotation=rotation,
                year_in_cycle=year_in_cycle,
                cycle_planet=row["planet"],
                part=row["parts"][idx]["part"],
                part_ruler=row["parts"][idx]["ruler"],
                needs_review=row["needs_review"],
            )
        acc += row["years"]
    raise RuntimeError("unreachable")


def varshphal(chart: LkChart, age: int) -> VarshphalResult:
    if not isinstance(age, int) or isinstance(age, bool) or age < 1 or age > VARSHPHAL_MAX_AGE:
        raise ValueError(
            f"age must be an integer 1..{VARSHPHAL_MAX_AGE} "
            f"(the book's matrix stops at {VARSHPHAL_MAX_AGE})"
        )
    row = varshphal_data["rows"][age - 1]["houses"]
    planets: list[VarshphalPlanet] = []
    mapped: dict[str, int] = {}
    for planet in PLANET_ORDER:
        natal = chart.planet_house.get(planet)
        if not natal:
            continue
        annual = row[natal - 1]
        mapped[planet] = annual
        planets.append(
            VarshphalPlanet(planet=planet, natal_house=natal, annual_house=annual, month=_month_of(annual))
        )
    return VarshphalResult(
        age=age,
        row=row,
        planets=planets,
        annual_chart=lk_chart_from_houses(mapped, chart.origin),
        cycle35=cycle35_position(age),
        semantics=(
            "matrix[age][natal house] = annual house; age 1 is the first year of life "
            "(completed years + 1)"
        ),
    )


def year_of_life(birth_date: str, now: datetime) -> int:
    """Year of life for the matrix from YYYY-MM-DD and a reference instant (UTC calendar date)."""
    y, m, d = (int(x) for x in birth_date.split("-"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)
    completed = now.year - y
    if now.month < m or (now.month == m and now.day < d):
        completed -= 1
    return max(1, completed + 1)
