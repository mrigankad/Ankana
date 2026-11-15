"""Aspects, sleeping planets/houses, debts (rin) and artificial planets (masnui)."""

from __future__ import annotations

from .chart import planets_in
from .data import PLANET_ORDER, aspect_rows, dormant_data, masnui_data, pakka_ghar, rin_data
from .models import LkAspect, LkChart, MasnuiFinding, RinFinding, SleepingHouse, SleepingPlanet

# ---- aspects -------------------------------------------------------------


def lk_aspects(chart: LkChart) -> list[LkAspect]:
    out: list[LkAspect] = []
    for row in aspect_rows:
        for src in planets_in(chart, row["from"]):
            for target in row["to"]:
                for dst in planets_in(chart, target):
                    out.append(
                        LkAspect(
                            **{
                                "from": {"planet": src, "house": row["from"]},
                                "to": {"planet": dst, "house": target},
                                "strength": row["strength"],
                                "derived": row["derived"],
                                "cite": row["cite"],
                                "needs_review": row["needs_review"],
                            }
                        )
                    )
    return out


def aspected_houses(chart: LkChart) -> dict[int, float]:
    best: dict[int, float] = {}
    for row in aspect_rows:
        if not planets_in(chart, row["from"]):
            continue
        for t in row["to"]:
            best[t] = max(best.get(t, 0), row["strength"])
    return best


# ---- sleeping ------------------------------------------------------------


def _rule_of(rule_id: str) -> dict:
    for r in dormant_data["rules"]:
        if r["id"] == rule_id:
            return r
    raise KeyError(f"unknown dormant rule {rule_id}")


def _awakener_of(house: int) -> str:
    for a in dormant_data["awakeners"]:
        if a["house"] == house:
            return a["planet"]
    raise KeyError(f"no awakener for house {house}")


def _age_of(planet: str) -> int | float:
    for x in dormant_data["self_awakening"]:
        if x["planet"] == planet:
            return x["age"]
    return 0


def _side_empty(chart: LkChart, start: int, end: int) -> bool:
    return all(not planets_in(chart, h) for h in range(start, end + 1))


def sleeping_planets(chart: LkChart) -> list[SleepingPlanet]:
    aspected = aspected_houses(chart)
    prior_empty = _side_empty(chart, 1, 6)
    latter_empty = _side_empty(chart, 7, 12)
    h2_empty = not planets_in(chart, 2)
    h10_empty = not planets_in(chart, 10)
    out: list[SleepingPlanet] = []

    for planet in PLANET_ORDER:
        house = chart.planet_house.get(planet)
        if not house:
            continue
        own = next((house in r["houses"] for r in pakka_ghar if r["planet"] == planet), False)

        dormant = False
        rule_id = "active_default"
        if own:
            rule_id = "own_pakka_ghar"
        elif house >= 7 and prior_empty:
            dormant, rule_id = True, "prior_side_empty"
        elif house <= 6 and latter_empty:
            dormant, rule_id = True, "latter_side_empty"
        elif house == 2 and h10_empty:
            dormant, rule_id = True, "h10_empty_h2"
        elif house == 10 and h2_empty:
            dormant, rule_id = True, "h2_empty_h10"
        elif house == 9 and h2_empty:
            dormant, rule_id = True, "h2_empty_h9"
        elif house <= 6 and not planets_in(chart, house + 6):
            dormant, rule_id = True, "no_opposite_planet"
        elif house >= 7 and house not in aspected:
            dormant, rule_id = True, "unaspected"

        rule = _rule_of("own_pakka_ghar") if rule_id == "active_default" else _rule_of(rule_id)
        awakener = _awakener_of(house)
        out.append(
            SleepingPlanet(
                planet=planet,
                house=house,
                status="dormant" if dormant else "awake",
                rule=rule_id,
                awakener=awakener,
                awakener_present=awakener in chart.planet_house,
                self_awakening_age=_age_of(planet),
                needs_review=False if rule_id == "active_default" else rule["needs_review"],
                cite=rule["cite"],
            )
        )
    return out


def sleeping_houses(chart: LkChart) -> list[SleepingHouse]:
    aspected = aspected_houses(chart)
    rule = _rule_of("empty_unaspected_house")
    out: list[SleepingHouse] = []
    for house in range(1, 13):
        occupied = bool(planets_in(chart, house))
        dormant = not occupied and house not in aspected
        awakener = _awakener_of(house)
        out.append(
            SleepingHouse(
                house=house,
                occupied=occupied,
                status="dormant" if dormant else "active",
                awakener=awakener,
                awakener_present=awakener in chart.planet_house,
                needs_review=rule["needs_review"],
                cite=rule["cite"],
            )
        )
    return out


# ---- rin -----------------------------------------------------------------


def detect_rin(chart: LkChart) -> list[RinFinding]:
    out: list[RinFinding] = []

    for row in rin_data["rows"]:
        house = chart.planet_house.get(row["planet"])
        if not house or house not in row["placement_houses"]:
            continue
        present = [p for p in planets_in(chart, house) if p in row["enemy_planets_with"]]
        if not present:
            continue
        out.append(
            RinFinding(
                id=row["id"],
                planet=row["planet"],
                kind=row["kind"],
                basis="table",
                house=house,
                **{"with": present},
                cause=row["cause"],
                symptoms=row["symptoms"],
                remedy=row["remedy"],
                remedy_cite=row["remedy_cite"],
                cite=row["cite"],
                needs_review=row["needs_review"],
            )
        )

    father = next(r for r in rin_data["rows"] if r["id"] == "pitri_rin")
    fd = rin_data["first_degree_father"]
    mercury_house = chart.planet_house.get("mercury")
    for row in fd["rows"]:
        if chart.planet_house.get(row["planet"]) != 9:
            continue
        if not mercury_house or mercury_house not in row["mercury_house"]:
            continue
        if row["planet"] == "mercury":
            continue
        out.append(
            RinFinding(
                id="pitri_rin_first_degree",
                planet=row["planet"],
                kind="Debt to father (first degree)",
                basis="first_degree_father",
                house=9,
                **{"with": ["mercury"]},
                cause=father["cause"],
                symptoms=father["symptoms"],
                remedy=father["remedy"],
                remedy_cite=father["remedy_cite"],
                cite=fd["cite"],
                needs_review=True,
            )
        )

    gi = rin_data["general_indicator"]
    for planet in gi["planets"]:
        house = chart.planet_house.get(planet)
        if not house or house not in gi["houses"]:
            continue
        out.append(
            RinFinding(
                id="pitri_rin_indicator",
                planet=planet,
                kind="Possible debt to father (indicator)",
                basis="indicator",
                house=house,
                **{"with": []},
                cause=father["cause"],
                symptoms=father["symptoms"],
                remedy=father["remedy"],
                remedy_cite=father["remedy_cite"],
                cite=gi["cite"],
                needs_review=True,
            )
        )
    return out


# ---- masnui --------------------------------------------------------------


def detect_masnui(chart: LkChart) -> list[MasnuiFinding]:
    out: list[MasnuiFinding] = []
    for row in masnui_data["rows"]:
        a, b = row["components"]
        ha = chart.planet_house.get(a)
        hb = chart.planet_house.get(b)
        if not ha or ha != hb:
            continue
        out.append(
            MasnuiFinding(
                id=row["id"],
                formed_planet=row["formed_planet"],
                variant=row["variant"],
                components=row["components"],
                house=ha,
                formed_planet_present=row["formed_planet"] in chart.planet_house,
                cite=row["cite"],
                needs_review=row["needs_review"],
            )
        )
    return out
