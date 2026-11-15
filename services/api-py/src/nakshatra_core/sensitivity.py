"""Birth-time sensitivity: how many minutes of error flip a chart's discrete facts.

For the lagna and each planet we find the smallest shift of the birth instant
(earlier or later) that changes its sign, its nakshatra pada, its house, and
(for the Moon) the Vimshottari dasha lord. Anything under FLAG_MINUTES is
flagged: a birth time known only to the nearest 10 minutes cannot settle it.

Method: scan outward in 1-minute steps (a lagna sign flip needs at most about
2 hours; the Moon about 3 hours per sign), then bisect the first flip to
about 0.001 min. Slow bodies that do not flip inside the window get a linear
extrapolation from their speed, marked `estimated`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from .dasha_vimshottari import compute_vimshottari
from .ephemeris import SEVEN_BODIES, normalize_degrees
from .providers import get_provider
from .time import to_utc_datetime
from .zodiac import NAKSHATRA_LORD_CYCLE, NAKSHATRA_SPAN

FLAG_MINUTES = 10.0
DEFAULT_WINDOW_MINUTES = 240
_PADA_SPAN = NAKSHATRA_SPAN / 4
_NODE_SPEED = -0.05295  # mean node, degrees/day
_ENTITIES = ("lagna", *SEVEN_BODIES, "rahu", "ketu")


def utc_of(inp: dict) -> datetime:
    """UTC instant of a chart or case input.

    An explicit `utcOffset` ("+05:53:28") overrides the zone name; it is for
    historical local mean time births that no IANA zone reproduces.
    """
    if inp.get("utcOffset"):
        text = inp["utcOffset"]
        sign = -1 if text.startswith("-") else 1
        parts = [int(x) for x in text.lstrip("+-").split(":")]
        off = timedelta(hours=parts[0], minutes=parts[1],
                        seconds=parts[2] if len(parts) > 2 else 0) * sign
        y, mo, d = (int(x) for x in inp["birthDate"].split("-"))
        hh, mm = (int(x) for x in inp["birthTime"].split(":"))
        return datetime(y, mo, d, hh, mm, tzinfo=timezone(off)).astimezone(UTC)
    return to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])


def state_at(provider, utc: datetime, inp: dict) -> tuple[dict[str, float], dict]:
    """Sidereal longitudes (lagna, planets, nodes) and the discrete facts at `utc`."""
    aya = provider.ayanamsa(utc, inp.get("ayanamsa", "lahiri"))
    lon = {b: normalize_degrees(provider.planet(b, utc).longitude - aya) for b in SEVEN_BODIES}
    lon["rahu"] = normalize_degrees(provider.lunar_node(utc, inp.get("nodeType", "mean")) - aya)
    lon["ketu"] = normalize_degrees(lon["rahu"] + 180)
    lon["lagna"] = normalize_degrees(
        provider.angles(utc, inp["latitude"], inp["longitude"]).ascendant - aya)
    asc_sign = int(lon["lagna"] // 30)
    facts: dict = {}
    for name in _ENTITIES:
        facts[f"{name}.sign"] = int(lon[name] // 30)
        facts[f"{name}.pada"] = int(lon[name] // _PADA_SPAN)
        if name != "lagna":
            facts[f"{name}.house"] = (int(lon[name] // 30) - asc_sign) % 12 + 1
    facts["dashaLord"] = NAKSHATRA_LORD_CYCLE[int(lon["moon"] // NAKSHATRA_SPAN) % 9]
    return lon, facts


def _first_flip(provider, utc0: datetime, inp: dict, base: dict, sign: int, window: int
                ) -> dict[str, float]:
    """Minutes (> 0) of shift in direction `sign` at which each fact first differs."""
    found: dict[str, float] = {}
    prev = 0.0
    pending = set(base)
    for minute in range(1, window + 1):
        _, now = state_at(provider, utc0 + timedelta(minutes=sign * minute), inp)
        for key in [k for k in pending if now[k] != base[k]]:
            lo, hi = prev, float(minute)
            for _ in range(10):
                mid = (lo + hi) / 2
                _, at = state_at(provider, utc0 + timedelta(minutes=sign * mid), inp)
                if at[key] == base[key]:
                    lo = mid
                else:
                    hi = mid
            found[key] = round(hi, 2)
            pending.discard(key)
        prev = float(minute)
        if not pending:
            break
    return found


def _estimate(lon: float, speed_deg_per_day: float, span: float, sign: int) -> float | None:
    """Minutes until `lon` crosses a multiple of `span`, at constant speed."""
    if abs(speed_deg_per_day) < 1e-9:
        return None
    moving = speed_deg_per_day * sign
    pos = lon % span
    dist = (span - pos) if moving > 0 else pos
    return round(dist / abs(speed_deg_per_day) * 1440, 1)


def _entry(earlier: float | None, later: float | None, estimated: bool) -> dict:
    vals = [v for v in (earlier, later) if v is not None]
    low = min(vals) if vals else None
    return {
        "earlierMinutes": earlier,
        "laterMinutes": later,
        "minMinutes": low,
        "estimated": estimated,
        "flagged": low is not None and low < FLAG_MINUTES,
    }


def sensitivity_report(inp: dict, provider=None, window: int = DEFAULT_WINDOW_MINUTES) -> dict:
    """`inp` is a chart input (calculationMetadata.input) or a case input."""
    provider = provider or get_provider()
    utc0 = utc_of(inp)
    lon0, base = state_at(provider, utc0, inp)
    fwd = _first_flip(provider, utc0, inp, base, +1, window)
    back = _first_flip(provider, utc0, inp, base, -1, window)
    speeds = {b: provider.planet(b, utc0).speed for b in SEVEN_BODIES}
    speeds["rahu"] = speeds["ketu"] = _NODE_SPEED

    def get(key: str, entity: str, span: float | None) -> dict:
        later, earlier = fwd.get(key), back.get(key)
        estimated = False
        if later is None and earlier is None and span and entity in speeds:
            later = _estimate(lon0[entity], speeds[entity], span, +1)
            earlier = _estimate(lon0[entity], speeds[entity], span, -1)
            estimated = True
        return _entry(earlier, later, estimated)

    def house_entry(entity: str) -> dict:
        # a planet changes house when its own sign or the lagna sign changes
        parts = [get(f"{entity}.sign", entity, 30.0), get("lagna.sign", "lagna", None)]
        picked = {}
        for key in ("earlierMinutes", "laterMinutes"):
            cands = [(p[key], p["estimated"]) for p in parts if p[key] is not None]
            picked[key] = min(cands) if cands else (None, False)
        return _entry(picked["earlierMinutes"][0], picked["laterMinutes"][0],
                      picked["earlierMinutes"][1] or picked["laterMinutes"][1])

    entities = []
    for name in _ENTITIES:
        row = {
            "entity": name,
            "siderealLongitude": round(lon0[name], 6),
            "degreesInSign": round(lon0[name] % 30, 4),
            "sign": get(f"{name}.sign", name, 30.0),
            "pada": get(f"{name}.pada", name, _PADA_SPAN),
        }
        if name != "lagna":
            row["house"] = house_entry(name)
        entities.append(row)

    lord_entry = get("dashaLord", "moon", NAKSHATRA_SPAN)

    def second_dasha_start(minutes: float) -> datetime:
        moon = state_at(provider, utc0 + timedelta(minutes=minutes), inp)[0]["moon"]
        start = compute_vimshottari(moon, utc0)["mahadashas"][1]["start"]
        return datetime.fromisoformat(start.replace("Z", "+00:00"))

    ref = second_dasha_start(0)
    shift = {
        "plus10MinDays": round((second_dasha_start(10) - ref).total_seconds() / 86400, 3),
        "minus10MinDays": round((second_dasha_start(-10) - ref).total_seconds() / 86400, 3),
    }

    flags = []
    for row in entities:
        for feature in ("sign", "pada", "house"):
            cell = row.get(feature)
            if cell and cell["flagged"]:
                flags.append({"entity": row["entity"], "feature": feature,
                              "minutes": cell["minMinutes"]})
    if lord_entry["flagged"]:
        flags.append({"entity": "moon", "feature": "dashaLord",
                      "minutes": lord_entry["minMinutes"]})

    return {
        "birthUtc": utc0.isoformat(),
        "windowMinutes": window,
        "flagThresholdMinutes": FLAG_MINUTES,
        "entities": entities,
        "dashaLord": {"lord": base["dashaLord"], **lord_entry},
        "secondMahadashaStartShift": shift,
        "flags": sorted(flags, key=lambda f: f["minutes"]),
        "flaggedCount": len(flags),
    }
