"""Transit snapshot and event timeline - exact port of transits.ts."""

from datetime import datetime, timedelta

from .ayanamsa import to_sidereal
from .dasha_vimshottari import iso_from_ms
from .ephemeris import (
    is_retrograde,
    mean_lunar_node,
    normalize_degrees,
    tropical_longitude,
)
from .zodiac import NAKSHATRA_NAMES, SIGN_NAMES, sign_of

_TRANSIT_BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")

# Slow bodies worth tracking in a multi-year event timeline.
_TIMELINE_BODIES = ("sun", "mercury", "venus", "mars", "jupiter", "saturn")

_DAY = timedelta(days=1)


def _inclusive_count(from_sign: int, to_sign: int) -> int:
    return ((to_sign - from_sign + 12) % 12) + 1


def _sidereal_of(body: str, date: datetime) -> float:
    return to_sidereal(tropical_longitude(body, date), date)


def _iso(dt: datetime) -> str:
    return iso_from_ms(dt.timestamp() * 1000)


def sade_sati_active(natal: dict, date: datetime) -> bool:
    """Same answer as compute_transit_snapshot(natal, date)["sadeSati"]["active"], from
    Saturn alone (one body instead of nine plus their retrograde checks): predictions ask
    this once per dasha window, so the full snapshot dominated their cost."""
    natal_moon_sign = next(p for p in natal["planets"] if p["planet"] == "moon")["signIndex"]
    saturn_sign = sign_of(_sidereal_of("saturn", date)).index
    return _inclusive_count(natal_moon_sign, saturn_sign) in (12, 1, 2)


def compute_transit_snapshot(natal: dict, date: datetime) -> dict:
    natal_asc_sign = int(natal["ascendant"]["siderealLongitude"] // 30) % 12
    natal_moon_sign = next(
        p for p in natal["planets"] if p["planet"] == "moon"
    )["signIndex"]

    def state(planet: str, lon: float, retrograde: bool) -> dict:
        sign = sign_of(lon)
        return {
            "planet": planet,
            "siderealLongitude": lon,
            "signIndex": sign.index,
            "signName": sign.name,
            "retrograde": retrograde,
            "houseFromLagna": _inclusive_count(natal_asc_sign, sign.index),
            "houseFromMoon": _inclusive_count(natal_moon_sign, sign.index),
            "nakshatra": NAKSHATRA_NAMES[int(lon // (360 / 27)) % 27],
        }

    states = [
        state(body, _sidereal_of(body, date), is_retrograde(body, date))
        for body in _TRANSIT_BODIES
    ]

    rahu_lon = to_sidereal(mean_lunar_node(date), date)
    ketu_lon = normalize_degrees(rahu_lon + 180)
    states.append(state("rahu", rahu_lon, True))
    states.append(state("ketu", ketu_lon, True))

    saturn = next(s for s in states if s["planet"] == "saturn")
    phase_map = {12: "rising", 1: "peak", 2: "setting"}
    sade_sati_phase = phase_map.get(saturn["houseFromMoon"])

    jupiter = next(s for s in states if s["planet"] == "jupiter")
    rahu_sign = sign_of(rahu_lon)
    ketu_sign = sign_of(ketu_lon)

    return {
        "date": _iso(date),
        "planets": states,
        "sadeSati": {
            "active": sade_sati_phase is not None,
            "phase": sade_sati_phase,
            "evidence": [
                f"Natal Moon in {SIGN_NAMES[natal_moon_sign]}.",
                f"Transit Saturn in {saturn['signName']}, house "
                f"{saturn['houseFromMoon']} from the natal Moon.",
                (
                    f"Saturn within the 12th-1st-2nd band from the Moon: "
                    f"sade sati {sade_sati_phase} phase."
                    if sade_sati_phase
                    else "Saturn outside the 12th-1st-2nd band from the Moon: "
                    "no sade sati."
                ),
            ],
        },
        "jupiterSummary": {
            "signName": jupiter["signName"],
            "houseFromMoon": jupiter["houseFromMoon"],
            "evidence": [
                f"Transit Jupiter in {jupiter['signName']}, house "
                f"{jupiter['houseFromMoon']} from the natal Moon."
            ],
        },
        "nodesSummary": {
            "rahuSign": rahu_sign.name,
            "ketuSign": ketu_sign.name,
            "rahuHouseFromLagna": _inclusive_count(natal_asc_sign, rahu_sign.index),
            "evidence": [
                f"Transit Rahu in {rahu_sign.name}, Ketu in {ketu_sign.name}.",
                f"Rahu occupies house "
                f"{_inclusive_count(natal_asc_sign, rahu_sign.index)} from the "
                f"natal lagna.",
            ],
        },
    }


def _bisect(low: datetime, high: datetime, crossed) -> datetime:
    """Bisect a boundary crossing between two dates down to under an hour."""
    low_ms = low.timestamp() * 1000
    high_ms = high.timestamp() * 1000
    from datetime import UTC

    while high_ms - low_ms > 3_600_000:
        mid = (low_ms + high_ms) / 2
        if crossed(datetime.fromtimestamp(mid / 1000, tz=UTC)):
            high_ms = mid
        else:
            low_ms = mid
    return datetime.fromtimestamp(high_ms / 1000, tz=UTC)


def compute_transit_timeline(from_date: datetime, years: float) -> list[dict]:
    clamped = min(max(years, 0.1), 5)
    end = from_date + timedelta(days=clamped * 365.2425)
    events: list[dict] = []

    for body in _TIMELINE_BODIES:
        cursor = from_date
        previous_sign = int(_sidereal_of(body, cursor) // 30) % 12
        previous_retro = is_retrograde(body, cursor)

        while cursor < end:
            step = min(cursor + _DAY, end)
            sign = int(_sidereal_of(body, step) // 30) % 12
            retro = is_retrograde(body, step)

            if sign != previous_sign:
                boundary = previous_sign
                at = _bisect(
                    cursor,
                    step,
                    lambda d, b=body, s=boundary: int(_sidereal_of(b, d) // 30) % 12
                    != s,
                )
                events.append(
                    {
                        "date": _iso(at),
                        "planet": body,
                        "kind": "ingress",
                        "detail": f"{body} enters {SIGN_NAMES[sign]}",
                    }
                )

            if retro != previous_retro:
                events.append(
                    {
                        "date": _iso(step),
                        "planet": body,
                        "kind": "retrograde-station" if retro else "direct-station",
                        "detail": (
                            f"{body} turns retrograde in {SIGN_NAMES[sign]}"
                            if retro
                            else f"{body} turns direct in {SIGN_NAMES[sign]}"
                        ),
                    }
                )

            previous_sign = sign
            previous_retro = retro
            cursor = step

    return sorted(events, key=lambda e: e["date"])
