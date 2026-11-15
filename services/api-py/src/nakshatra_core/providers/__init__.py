"""Ephemeris providers. Select with env ANKANA_EPHEMERIS=swiss|astronomy (default swiss; Ankana is AGPL-3.0, see LICENSING.md)."""

import os
from functools import cache

from .base import Angles, Ephemeris, NotSupportedError, PlanetState

__all__ = ["Angles", "Ephemeris", "NotSupportedError", "PlanetState", "get_provider"]


@cache
def _build(name: str) -> Ephemeris:
    if name == "swiss":
        from .swiss import SwissProvider

        return SwissProvider()
    if name == "astronomy":
        from .astronomy import AstronomyProvider

        return AstronomyProvider()
    raise ValueError(f"unknown ephemeris provider {name!r} (use swiss|astronomy)")


def get_provider(name: str | None = None) -> Ephemeris:
    return _build((name or os.environ.get("ANKANA_EPHEMERIS") or "swiss").lower())
