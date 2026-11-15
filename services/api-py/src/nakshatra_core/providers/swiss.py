"""Swiss Ephemeris provider (pyswisseph).

LICENCE: pyswisseph/Swiss Ephemeris is AGPL-3.0 or the Astrodienst Professional
Licence. Fine for internal development; a closed production service needs the
professional licence. See services/api-py/LICENSING.md.

Data files: set ANKANA_SE_EPHE_PATH, or put sepl_18/semo_18/seas_18 .se1 in
services/api-py/ephe (scripts/fetch_ephe.py). Missing files fall back to the
built-in Moshier ephemeris (`using_files` is False).

Ayanamsa includes nutation by default (Swiss Ephemeris convention): planets are
apparent (true equinox of date), so the ayanamsa must carry the same nutation for
sidereal longitudes not to wobble by +-17 arcsec. Set ANKANA_AYANAMSA_MEAN=1 for the
classical mean value (inconsistent with apparent planets; for comparison only).
Open decision: confirm the JHora reference exports use the same.
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import swisseph as swe

from ..time import julian_day
from .base import Angles, NotSupportedError, PlanetState

_BODIES = {
    "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY, "venus": swe.VENUS,
    "mars": swe.MARS, "jupiter": swe.JUPITER, "saturn": swe.SATURN,
}
_SIDM = {
    "lahiri": swe.SIDM_LAHIRI,
    "raman": swe.SIDM_RAMAN,
    "kp": swe.SIDM_KRISHNAMURTI,
    "true_chitra": swe.SIDM_TRUE_CITRA,
}
_HSYS = {"whole_sign": b"W", "equal": b"E", "sripati": b"S"}


def ephe_path() -> str:
    """Directory searched for Swiss Ephemeris .se1 files ('' when none is configured)."""
    path = os.environ.get("ANKANA_SE_EPHE_PATH")
    if not path:
        default = Path(__file__).resolve().parents[3] / "ephe"
        path = str(default) if default.is_dir() else ""
    return path


def _configure() -> bool:
    path = ephe_path()
    if path:
        swe.set_ephe_path(path)
    return bool(path) and any(Path(path).glob("sepl_*.se1"))


def _from_jd(jd: float) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(days=jd - 2_440_587.5)


class SwissProvider:
    name = "swiss"
    ayanamsas = tuple(_SIDM)
    sunrise_rules = ("standard", "hindu")

    def __init__(self) -> None:
        self.using_files = _configure()
        self._eph_flag = swe.FLG_SWIEPH if self.using_files else swe.FLG_MOSEPH
        self.mean_ayanamsa = os.environ.get("ANKANA_AYANAMSA_MEAN", "") in ("1", "true")

    def planet(self, body: str, dt: datetime) -> PlanetState:
        xx, _ = swe.calc_ut(julian_day(dt), _BODIES[body], self._eph_flag | swe.FLG_SPEED)
        return PlanetState(xx[0] % 360, xx[3])

    def lunar_node(self, dt: datetime, kind: str = "mean") -> float:
        body = {"mean": swe.MEAN_NODE, "true": swe.TRUE_NODE}[kind]
        xx, _ = swe.calc_ut(julian_day(dt), body, self._eph_flag)
        return xx[0] % 360

    def angles(self, dt: datetime, latitude: float, longitude: float) -> Angles:
        _, ascmc = swe.houses_ex(julian_day(dt), latitude, longitude, b"W")
        return Angles(ascmc[0] % 360, ascmc[1] % 360)

    def house_cusps(self, dt, latitude, longitude, system="whole_sign"):
        if system not in _HSYS:
            raise NotSupportedError(f"unknown house system {system}")
        cusps, _ = swe.houses_ex(julian_day(dt), latitude, longitude, _HSYS[system])
        return [c % 360 for c in cusps]

    def ayanamsa(self, dt: datetime, name: str = "lahiri") -> float:
        if name not in _SIDM:
            raise NotSupportedError(f"unknown ayanamsa {name}")
        swe.set_sid_mode(_SIDM[name], 0, 0)
        flags = self._eph_flag | (swe.FLG_NONUT if self.mean_ayanamsa else 0)
        _, value = swe.get_ayanamsa_ex_ut(julian_day(dt), flags)
        return value

    def sunrise_sunset(self, dt, latitude, longitude, rule="standard"):
        if rule not in self.sunrise_rules:
            raise NotSupportedError(f"unknown sunrise rule {rule}")
        extra = swe.BIT_HINDU_RISING if rule == "hindu" else 0
        pressure = 0.0 if rule == "hindu" else 1013.25
        geo = (longitude, latitude, 0.0)

        def event(jd: float, kind: int) -> float | None:
            res, tret = swe.rise_trans(
                jd, swe.SUN, kind | extra, geo, pressure, 15.0, self._eph_flag
            )
            return tret[0] if res == 0 else None

        jd_birth = julian_day(dt)
        sunrise = None
        cursor = jd_birth - 30 / 24
        for _ in range(4):
            found = event(cursor, swe.CALC_RISE)
            if found is None or found > jd_birth:
                break
            sunrise = found
            cursor = found + 1 / 1440
        if sunrise is None:  # polar edge case, mirrors the astronomy provider
            sunrise = julian_day(dt.replace(hour=0, minute=0, second=0, microsecond=0))
        sunset = event(sunrise, swe.CALC_SET)
        if sunset is None:
            sunset = sunrise + 0.5
        return _from_jd(sunrise), _from_jd(sunset)
