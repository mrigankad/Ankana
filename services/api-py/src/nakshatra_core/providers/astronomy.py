"""Provider backed by the existing astronomy-engine code (approximate ayanamsa)."""

import math
from datetime import datetime, timedelta

from .. import ascendant as _asc
from .. import ayanamsa as _aya
from .. import ephemeris as _eph
from .. import sunrise as _sun
from .base import Angles, NotSupportedError, PlanetState


class AstronomyProvider:
    name = "astronomy"
    ayanamsas = ("lahiri",)
    sunrise_rules = ("standard",)  # upper limb + refraction (astronomy-engine)

    def planet(self, body: str, dt: datetime) -> PlanetState:
        lon = _eph.tropical_longitude(body, dt)
        h = timedelta(hours=6)
        before = _eph.tropical_longitude(body, dt - h)
        after = _eph.tropical_longitude(body, dt + h)
        delta = (after - before + 180) % 360 - 180
        return PlanetState(lon, delta / 0.5)

    def lunar_node(self, dt: datetime, kind: str = "mean") -> float:
        if kind != "mean":
            raise NotSupportedError("astronomy provider has only the mean node")
        return _eph.mean_lunar_node(dt)

    def angles(self, dt: datetime, latitude: float, longitude: float) -> Angles:
        asc = _asc.tropical_ascendant(dt, latitude, longitude)
        ramc = math.radians(
            _eph.normalize_degrees(_eph.greenwich_sidereal_degrees(dt) + longitude)
        )
        eps = math.radians(_asc.mean_obliquity(dt))
        mc = math.degrees(math.atan2(math.sin(ramc), math.cos(ramc) * math.cos(eps)))
        return Angles(asc, _eph.normalize_degrees(mc))

    def house_cusps(self, dt, latitude, longitude, system="whole_sign"):
        if system not in ("whole_sign", "equal"):
            raise NotSupportedError(f"house system {system} needs the swiss provider")
        asc = self.angles(dt, latitude, longitude).ascendant
        start = (asc // 30) * 30 if system == "whole_sign" else asc
        return [(start + 30 * i) % 360 for i in range(12)]

    def ayanamsa(self, dt: datetime, name: str = "lahiri") -> float:
        if name != "lahiri":
            raise NotSupportedError(f"ayanamsa {name} needs the swiss provider")
        return _aya.lahiri_ayanamsa(dt)

    def sunrise_sunset(self, dt, latitude, longitude, rule="standard"):
        if rule != "standard":
            raise NotSupportedError("hindu sunrise needs the swiss provider")
        return _sun.last_sunrise_and_next_sunset(dt, latitude, longitude)
