"""Geocentric tropical longitudes via Astronomy Engine.

Port of packages/astrology-core/src/ephemeris.ts - same underlying library,
same mean-node polynomial, same retrograde probe.
"""

from datetime import datetime, timedelta
from functools import lru_cache

from astronomy import Body, Ecliptic, GeoVector, SiderealTime, Time

from .time import julian_day


def _astro_time(dt: datetime) -> Time:
    return Time(julian_day(dt) - 2_451_545.0)

SEVEN_BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")

_BODY_MAP = {
    "sun": Body.Sun,
    "moon": Body.Moon,
    "mercury": Body.Mercury,
    "venus": Body.Venus,
    "mars": Body.Mars,
    "jupiter": Body.Jupiter,
    "saturn": Body.Saturn,
}


def normalize_degrees(value: float) -> float:
    return value % 360


@lru_cache(maxsize=16384)
def tropical_longitude(body: str, dt: datetime) -> float:
    vector = GeoVector(_BODY_MAP[body], _astro_time(dt), True)
    return normalize_degrees(Ecliptic(vector).elon)


def mean_lunar_node(dt: datetime) -> float:
    t = (julian_day(dt) - 2_451_545.0) / 36_525
    omega = (
        125.0445479
        - 1_934.1362891 * t
        + 0.0020754 * t * t
        + (t * t * t) / 467_441
        - (t * t * t * t) / 60_616_000
    )
    return normalize_degrees(omega)


@lru_cache(maxsize=8192)
def is_retrograde(body: str, dt: datetime) -> bool:
    if body in ("sun", "moon"):
        return False
    before = tropical_longitude(body, dt - timedelta(hours=6))
    after = tropical_longitude(body, dt + timedelta(hours=6))
    return normalize_degrees(after - before) > 180


def greenwich_sidereal_degrees(dt: datetime) -> float:
    return normalize_degrees(SiderealTime(_astro_time(dt)) * 15)
