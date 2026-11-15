"""End-to-end core parity gate: recompute every core field from raw birth
input and compare against the TS golden artifacts."""

from datetime import datetime
from zoneinfo import ZoneInfo

from nakshatra_core.ascendant import sidereal_ascendant
from nakshatra_core.ayanamsa import to_sidereal
from nakshatra_core.dignities import dignity_of, is_combust
from nakshatra_core.ephemeris import (
    SEVEN_BODIES,
    is_retrograde,
    mean_lunar_node,
    normalize_degrees,
    tropical_longitude,
)
from nakshatra_core.houses import house_of
from nakshatra_core.panchang import compute_panchang
from nakshatra_core.time import to_utc_datetime
from nakshatra_core.zodiac import nakshatra_of, sign_of


def angular_gap(a: float, b: float) -> float:
    gap = abs(normalize_degrees(a) - normalize_degrees(b)) % 360
    return min(gap, 360 - gap)


def test_full_core_parity(golden_charts: list[dict]) -> None:
    failures: list[str] = []
    for chart in golden_charts:
        label = chart["label"]
        inp = chart["input"]
        artifact = chart["artifact"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])

        # Planets: longitudes from scratch, then discrete fields.
        tropical = {body: tropical_longitude(body, dt) for body in SEVEN_BODIES}
        sidereal = {b: to_sidereal(lon, dt) for b, lon in tropical.items()}
        rahu = to_sidereal(mean_lunar_node(dt), dt)
        sidereal["rahu"] = rahu
        sidereal["ketu"] = normalize_degrees(rahu + 180)

        asc = sidereal_ascendant(dt, inp["latitude"], inp["longitude"])
        asc_golden = artifact["ascendant"]
        if angular_gap(asc, asc_golden["siderealLongitude"]) > 0.05:
            failures.append(f"{label}: ascendant longitude")
        if sign_of(asc).name != asc_golden["signName"]:
            failures.append(f"{label}: ascendant sign")

        for planet in artifact["planets"]:
            name = planet["planet"]
            lon = sidereal[name]
            tol = 0.01 if name in ("rahu", "ketu") else 0.05
            if angular_gap(lon, planet["siderealLongitude"]) > tol:
                failures.append(f"{label}: {name} longitude")
            if sign_of(lon).name != planet["signName"]:
                failures.append(f"{label}: {name} sign")
            if nakshatra_of(lon).name != planet["nakshatra"]:
                failures.append(f"{label}: {name} nakshatra")
            if nakshatra_of(lon).pada != planet["pada"]:
                failures.append(f"{label}: {name} pada")
            if house_of(lon, asc) != planet["house"]:
                failures.append(f"{label}: {name} house")
            if dignity_of(name, lon) != planet["dignity"]:
                failures.append(f"{label}: {name} dignity")
            if name in SEVEN_BODIES:
                if is_retrograde(name, dt) != planet["retrograde"]:
                    failures.append(f"{label}: {name} retrograde")
                if name != "sun":
                    combust = is_combust(
                        name, tropical[name], tropical["sun"], planet["retrograde"]
                    )
                    if combust != planet["combust"]:
                        failures.append(f"{label}: {name} combust")

        panchang = compute_panchang(
            sidereal["sun"], sidereal["moon"], _js_weekday(dt, inp["timezoneName"])
        )
        golden_panchang = artifact["panchang"]
        if panchang.tithi.name != golden_panchang["tithi"]["name"]:
            failures.append(f"{label}: tithi")
        if panchang.karana.name != golden_panchang["karana"]["name"]:
            failures.append(f"{label}: karana")
        if panchang.yoga.name != golden_panchang["yoga"]["name"]:
            failures.append(f"{label}: panchang yoga")
        if panchang.vara.name != golden_panchang["vara"]["name"]:
            failures.append(f"{label}: vara")

    assert not failures, "core parity failures:\n" + "\n".join(failures)


def _js_weekday(dt: datetime, timezone_name: str) -> int:
    local = dt.astimezone(ZoneInfo(timezone_name))
    return (local.weekday() + 1) % 7
