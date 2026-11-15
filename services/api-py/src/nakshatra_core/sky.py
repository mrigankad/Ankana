"""Sky events and a day's panchang for a place: sign ingresses, stations,
amavasya and purnima, a 12 month transit timeline against a natal chart
(house ingresses, graha drishti onto the natal Moon and lagna, sade sati) and
the daily panchang with end times and Rahu kaal.

Everything is computed with the same engine as the chart (Lahiri sidereal,
mean node). Times are UTC datetimes; callers localise them.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from .aspects import _SPECIAL_ASPECTS, sign_count
from .ayanamsa import to_sidereal
from .ephemeris import is_retrograde, mean_lunar_node, normalize_degrees, tropical_longitude
from .panchang import compute_panchang
from .sunrise import last_sunrise_and_next_sunset
from .zodiac import NAKSHATRA_SPAN, SIGN_NAMES, nakshatra_of, sign_of

EVENT_BODIES = ("sun", "mercury", "venus", "mars", "jupiter", "saturn", "rahu", "ketu")
STATION_BODIES = ("mercury", "venus", "mars", "jupiter", "saturn")
_DAY = timedelta(days=1)

# Nodes cast the 5th, 7th and 9th aspects in the Parashari convention used here.
_NODE_ASPECTS = (5, 7, 9)

# Rahu kaal is the n-th eighth of the daytime, counting from sunrise (Sunday = 0).
_RAHU_SEGMENT = {0: 8, 1: 2, 2: 7, 3: 5, 4: 6, 5: 4, 6: 3}


def sidereal(body: str, dt: datetime) -> float:
    """Sidereal longitude of a graha. Rahu is the mean node, Ketu opposite."""
    if body in ("rahu", "ketu"):
        rahu = to_sidereal(mean_lunar_node(dt), dt)
        return rahu if body == "rahu" else normalize_degrees(rahu + 180)
    return to_sidereal(tropical_longitude(body, dt), dt)


def _sign(body: str, dt: datetime) -> int:
    return int(sidereal(body, dt) // 30) % 12


def _retro(body: str, dt: datetime) -> bool:
    if body in ("rahu", "ketu"):
        return True
    return is_retrograde(body, dt)


def _bisect(low: datetime, high: datetime, crossed: Callable[[datetime], bool],
            seconds: int = 600) -> datetime:
    """First instant in (low, high] where crossed() turns true, to `seconds`."""
    lo, hi = low.timestamp(), high.timestamp()
    while hi - lo > seconds:
        mid = (lo + hi) / 2
        if crossed(datetime.fromtimestamp(mid, tz=UTC)):
            hi = mid
        else:
            lo = mid
    return datetime.fromtimestamp(hi, tz=UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------ body scanning
def scan_body(body: str, start: datetime, end: datetime) -> list[dict]:
    """Ingresses and (for the planets that have them) stations in [start, end]."""
    out: list[dict] = []
    cursor = start
    prev_sign = _sign(body, cursor)
    prev_retro = _retro(body, cursor)
    track_stations = body in STATION_BODIES
    while cursor < end:
        step = min(cursor + _DAY, end)
        sign = _sign(body, step)
        if sign != prev_sign:
            old = prev_sign
            at = _bisect(cursor, step, lambda d, b=body, s=old: _sign(b, d) != s)
            out.append({"at": at, "planet": body, "kind": "ingress", "sign_index": sign,
                        "from_sign_index": old})
        if track_stations:
            retro = _retro(body, step)
            if retro != prev_retro:
                was = prev_retro
                at = _bisect(cursor, step, lambda d, b=body, w=was: _retro(b, d) != w,
                             seconds=3600)
                out.append({"at": at, "planet": body,
                            "kind": "retrograde-station" if retro else "direct-station",
                            "sign_index": _sign(body, at)})
            prev_retro = retro
        prev_sign = sign
        cursor = step
    return out


def _elongation(dt: datetime) -> float:
    return normalize_degrees(sidereal("moon", dt) - sidereal("sun", dt))


def scan_lunations(start: datetime, end: datetime) -> list[dict]:
    """Amavasya (new moon) and purnima (full moon) in [start, end]."""
    out: list[dict] = []
    cursor = start
    prev_half = int(_elongation(cursor) // 180)  # 0 waxing, 1 waning
    while cursor < end:
        step = min(cursor + timedelta(hours=12), end)
        half = int(_elongation(step) // 180)
        if half != prev_half:
            new = half == 0  # elongation wrapped through 360: amavasya
            old = prev_half
            at = _bisect(cursor, step, lambda d, o=old: int(_elongation(d) // 180) != o,
                         seconds=120)
            out.append({"at": at, "planet": "moon",
                        "kind": "amavasya" if new else "purnima",
                        "sign_index": _sign("sun" if new else "moon", at)})
        prev_half = half
        cursor = step
    return out


def sky_events(start: datetime, days: int = 7) -> list[dict]:
    """Ingresses, stations and lunations from `start` for `days`, sorted by time.
    Each event has `at` (UTC datetime), `planet`, `kind`, `sign_index`."""
    end = start + timedelta(days=days)
    events: list[dict] = []
    for body in EVENT_BODIES:
        events += scan_body(body, start, end)
    events += scan_lunations(start, end)
    return sorted(events, key=lambda e: e["at"])


# ------------------------------------------------------------ natal timeline
def _casts(planet: str) -> tuple[int, ...]:
    if planet in ("rahu", "ketu"):
        return _NODE_ASPECTS
    return (7, *_SPECIAL_ASPECTS.get(planet, ()))


def _natal_signs(natal: dict) -> tuple[int, int]:
    lagna = int(natal["ascendant"]["signIndex"])
    moon = next(p for p in natal["planets"] if p["planet"] == "moon")["signIndex"]
    return lagna, int(moon)


def _phase(saturn_sign: int, moon_sign: int) -> str | None:
    return {11: "rising", 0: "peak", 1: "setting"}.get((saturn_sign - moon_sign) % 12)


def chart_transit_timeline(natal: dict, start: datetime, months: int = 12) -> dict:
    """Events for the next `months` against one natal chart."""
    months = min(max(months, 1), 24)
    end = start + timedelta(days=round(months * 30.4375))
    lagna, moon = _natal_signs(natal)
    events: list[dict] = []

    def house(sign: int, origin: int) -> int:
        return sign_count(origin, sign)

    def base(raw: dict) -> dict:
        sign = raw["sign_index"]
        return {
            "date": iso(raw["at"]), "planet": raw["planet"], "kind": raw["kind"],
            "sign": SIGN_NAMES[sign], "sign_index": sign,
            "house_from_lagna": house(sign, lagna), "house_from_moon": house(sign, moon),
            "target": None, "aspect": None, "phase": None,
        }

    for body in EVENT_BODIES:
        for raw in scan_body(body, start, end):
            ev = base(raw)
            events.append(ev)
            if raw["kind"] != "ingress":
                continue
            for target, natal_sign in (("moon", moon), ("lagna", lagna)):
                n = sign_count(raw["sign_index"], natal_sign)
                if n == 1:
                    events.append({**ev, "kind": "conjunction", "target": target, "aspect": 1})
                elif n in _casts(body):
                    events.append({**ev, "kind": "aspect", "target": target, "aspect": n})

    # Sade sati: Saturn in the 12th, 1st and 2nd sign from the natal Moon.
    saturn_now = _sign("saturn", start)
    now_phase = _phase(saturn_now, moon)
    phases: list[dict] = []
    open_phase = {"phase": now_phase, "starts_at": None, "ends_at": None} if now_phase else None
    prev = now_phase
    for ev in sorted((e for e in events if e["planet"] == "saturn" and e["kind"] == "ingress"),
                     key=lambda e: e["date"]):
        phase = _phase(ev["sign_index"], moon)
        if phase is not None or prev is not None:
            events.append({**ev, "kind": "sade_sati", "phase": phase})
        if open_phase is not None:
            open_phase["ends_at"] = ev["date"]
            phases.append(open_phase)
            open_phase = None
        if phase is not None:
            open_phase = {"phase": phase, "starts_at": ev["date"], "ends_at": None}
        prev = phase
    if open_phase is not None:
        phases.append(open_phase)

    events.sort(key=lambda e: (e["date"], e["planet"], e["kind"]))
    return {
        "start": iso(start), "end": iso(end), "months": months,
        "natal": {"lagna_sign": SIGN_NAMES[lagna], "moon_sign": SIGN_NAMES[moon]},
        "sade_sati": {"active_now": now_phase is not None, "phase_now": now_phase,
                      "phases": phases},
        "events": events,
    }


# ------------------------------------------------------------ daily panchang
def _tithi_index(dt: datetime) -> int:
    return int(_elongation(dt) // 12)


def _nakshatra_index(dt: datetime) -> int:
    return int(sidereal("moon", dt) // NAKSHATRA_SPAN) % 27


def _end_of(index_fn: Callable[[datetime], int], at: datetime) -> datetime:
    current = index_fn(at)
    cursor = at
    for _ in range(40):  # tithi and nakshatra never last 40 hours
        step = cursor + timedelta(hours=1)
        if index_fn(step) != current:
            return _bisect(cursor, step, lambda d: index_fn(d) != current, seconds=60)
        cursor = step
    return cursor


def daily_panchang(day_start_utc: datetime, latitude: float, longitude: float,
                   local_weekday_sun0: int) -> dict:
    """Panchang for a civil day at a place, read at local sunrise (the traditional
    convention) with the end time of the running tithi and nakshatra and Rahu kaal.
    `day_start_utc` is any instant in that local day near midday."""
    sunrise, sunset = last_sunrise_and_next_sunset(day_start_utc, latitude, longitude)
    sun_l, moon_l = sidereal("sun", sunrise), sidereal("moon", sunrise)
    p = compute_panchang(sun_l, moon_l, local_weekday_sun0)
    nak = nakshatra_of(moon_l)
    segment = (sunset - sunrise) / 8
    rahu_n = _RAHU_SEGMENT[local_weekday_sun0]
    rahu_start = sunrise + segment * (rahu_n - 1)
    return {
        "sunrise": iso(sunrise), "sunset": iso(sunset),
        "vara": p.vara.name, "vara_index": p.vara.index,
        "tithi": {"name": p.tithi.name, "paksha": p.tithi.paksha, "index": p.tithi.index,
                  "ends_at": iso(_end_of(_tithi_index, sunrise))},
        "nakshatra": {"name": nak.name, "pada": nak.pada,
                      "ends_at": iso(_end_of(_nakshatra_index, sunrise))},
        "yoga": p.yoga.name, "karana": p.karana.name,
        "moon_sign": sign_of(moon_l).name, "sun_sign": sign_of(sun_l).name,
        "rahu_kaal": {"start": iso(rahu_start), "end": iso(rahu_start + segment)},
    }


__all__ = ["chart_transit_timeline", "daily_panchang", "sky_events"]
