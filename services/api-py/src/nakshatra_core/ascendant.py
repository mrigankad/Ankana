"""Ascendant (lagna) - exact port of ascendant.ts."""

import math
from datetime import datetime

from .ayanamsa import to_sidereal
from .ephemeris import greenwich_sidereal_degrees, normalize_degrees
from .time import julian_day

_DEG = math.pi / 180


def mean_obliquity(dt: datetime) -> float:
    """Mean obliquity of the ecliptic (Meeus 22.2), in degrees."""
    t = (julian_day(dt) - 2_451_545.0) / 36_525
    return 23.43929111 - (46.815 * t + 0.00059 * t * t - 0.001813 * t * t * t) / 3_600


def tropical_ascendant(dt: datetime, latitude: float, longitude: float) -> float:
    """RAMC is the local sidereal time in degrees; the atan2 form keeps the
    ascendant in the correct semicircle without quadrant fix-ups."""
    ramc = normalize_degrees(greenwich_sidereal_degrees(dt) + longitude)
    epsilon = mean_obliquity(dt)
    ascendant = math.atan2(
        math.cos(ramc * _DEG),
        -(
            math.sin(ramc * _DEG) * math.cos(epsilon * _DEG)
            + math.tan(latitude * _DEG) * math.sin(epsilon * _DEG)
        ),
    )
    return normalize_degrees(ascendant / _DEG)


def sidereal_ascendant(dt: datetime, latitude: float, longitude: float) -> float:
    return to_sidereal(tropical_ascendant(dt, latitude, longitude), dt)
