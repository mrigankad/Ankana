"""Lahiri (Chitrapaksha) ayanamsa - exact port of ayanamsa.ts.

Anchored at 23.85306 deg for J2000 with the general precession rate.
Must stay identical to the TS formula so golden pada/sign values hold.

Reference: the ICRC-standardized Lahiri value at J2000.0 is 23.853222 deg -
our anchor differs by ~0.6 arcsec, well inside pada-boundary tolerance; the
boundaries module flags any chart where such variance could matter.
"""

from datetime import datetime

from .ephemeris import normalize_degrees
from .time import julian_day


def lahiri_ayanamsa(dt: datetime) -> float:
    t = (julian_day(dt) - 2_451_545.0) / 36_525
    return 23.85306 + (5_028.796195 * t + 1.1054348 * t * t) / 3_600


def to_sidereal(tropical_longitude: float, dt: datetime) -> float:
    return normalize_degrees(tropical_longitude - lahiri_ayanamsa(dt))
