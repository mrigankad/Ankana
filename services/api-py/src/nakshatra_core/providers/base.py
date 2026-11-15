"""Ephemeris provider interface.

All longitudes are tropical degrees in [0, 360); times are timezone-aware
datetimes. Sidereal conversion is `tropical - ayanamsa`, done by the caller.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class NotSupportedError(NotImplementedError):
    """The provider cannot honour this option (e.g. true node on astronomy-engine)."""


@dataclass(frozen=True)
class PlanetState:
    longitude: float  # tropical degrees
    speed: float  # degrees/day, negative = retrograde


@dataclass(frozen=True)
class Angles:
    ascendant: float  # tropical
    midheaven: float  # tropical


class Ephemeris(Protocol):
    name: str
    ayanamsas: tuple[str, ...]
    sunrise_rules: tuple[str, ...]

    def planet(self, body: str, dt: datetime) -> PlanetState: ...

    def lunar_node(self, dt: datetime, kind: str = "mean") -> float:
        """Tropical longitude of the ascending node (Rahu). kind: mean|true."""
        ...

    def angles(self, dt: datetime, latitude: float, longitude: float) -> Angles: ...

    def house_cusps(
        self, dt: datetime, latitude: float, longitude: float, system: str = "whole_sign"
    ) -> list[float]:
        """12 tropical cusps. whole_sign and equal everywhere; sripati swiss only."""
        ...

    def ayanamsa(self, dt: datetime, name: str = "lahiri") -> float: ...

    def sunrise_sunset(
        self, dt: datetime, latitude: float, longitude: float, rule: str = "standard"
    ) -> tuple[datetime, datetime]:
        """(last sunrise <= dt, first sunset after it). rule: standard|hindu."""
        ...
