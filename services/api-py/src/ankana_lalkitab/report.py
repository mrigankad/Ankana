"""One-call Lal Kitab report (port of report.ts)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .chart import lk_chart
from .data import planet_house_entries
from .models import LalKitabReport, PlanetHouseMatch
from .remedies import match_planet_house_entries, remedies
from .rules import detect_masnui, detect_rin, lk_aspects, sleeping_houses, sleeping_planets
from .varshphal import VARSHPHAL_MAX_AGE, varshphal, year_of_life


def lal_kitab_report(
    artifact: Mapping[str, Any],
    origin: str | None = None,
    age: int | None = None,
    now: datetime | None = None,
) -> LalKitabReport:
    chart = lk_chart(artifact, origin)
    birth = ((artifact.get("calculationMetadata") or {}).get("input") or {}).get("birthDate")
    now = now or datetime.now(UTC)
    derived = year_of_life(birth, now) if birth else None
    requested = age if age is not None else derived
    use_age = requested if requested is not None and 1 <= requested <= VARSHPHAL_MAX_AGE else None

    return LalKitabReport(
        origin=chart.origin,
        chart=chart,
        sleeping_planets=sleeping_planets(chart),
        sleeping_houses=sleeping_houses(chart),
        aspects=lk_aspects(chart),
        rin=detect_rin(chart),
        masnui=detect_masnui(chart),
        planet_house=[
            PlanetHouseMatch(
                id=m.entry["id"],
                planet=m.entry["planet"],
                house=m.entry["house"],
                theme=m.entry["theme"],
                matched=m.matched,
                cite=m.entry["cite"],
            )
            for m in match_planet_house_entries(chart)
        ],
        varshphal=varshphal(chart, use_age) if use_age is not None else None,
        varshphal_age_requested=requested,
        remedies=remedies(chart),
        coverage=dict(
            planet_house_done=sum(1 for e in planet_house_entries if e["status"] == "done"),
            planet_house_total=len(planet_house_entries),
        ),
    )
