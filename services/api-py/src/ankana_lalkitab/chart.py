"""Lal Kitab chart construction (port of chart.ts)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .data import PLANET_ORDER
from .models import LkChart, LkPlacement


def _build(origin: str, lagna: int | None, placements: list[LkPlacement]) -> LkChart:
    houses: list[list[str]] = [[] for _ in range(13)]
    planet_house: dict[str, int] = {}
    for planet in PLANET_ORDER:
        p = next((x for x in placements if x.planet == planet), None)
        if p is None:
            continue
        houses[p.house].append(planet)
        planet_house[planet] = p.house
    return LkChart(
        origin=origin,
        lagna_sign_index=lagna,
        placements=placements,
        houses=houses,
        planet_house=planet_house,
    )


def lk_chart(artifact: Mapping[str, Any], origin: str | None = None) -> LkChart:
    """Build the chart from a chart artifact dict (camelCase keys as in the TS artifact).

    Default origin ``lagna_h1``: ascendant sign is house 1 (book Vol I Ch.4, p.91).
    ``aries_h1`` numbers houses by sign (Aries = 1).
    """
    origin = origin or "lagna_h1"
    lagna = artifact["ascendant"]["signIndex"]
    placements = [
        LkPlacement(
            planet=p["planet"],
            sign_index=p["signIndex"],
            house=p["signIndex"] + 1 if origin == "aries_h1" else (p["signIndex"] - lagna) % 12 + 1,
        )
        for p in artifact["planets"]
    ]
    return _build(origin, lagna, placements)


def lk_chart_from_houses(planet_house: Mapping[str, int], origin: str = "lagna_h1") -> LkChart:
    placements: list[LkPlacement] = []
    for planet in PLANET_ORDER:
        house = planet_house.get(planet)
        if house is None:
            continue
        if not isinstance(house, int) or house < 1 or house > 12:
            raise ValueError(f"house for {planet} must be 1..12, got {house}")
        placements.append(LkPlacement(planet=planet, house=house, sign_index=None))
    return _build(origin, None, placements)


def planets_in(chart: LkChart, house: int) -> list[str]:
    return chart.houses[house] if 0 <= house < len(chart.houses) else []
