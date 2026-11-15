"""Calculation provenance: which ephemeris, library version and settings made a chart.

Recorded in every chart artifact's `calculationMetadata.provenance` so a stored
chart can always be traced to the software state that produced it.
"""

from __future__ import annotations

import importlib.metadata as _md
from pathlib import Path


def _dist_version(name: str) -> str | None:
    try:
        return _md.version(name)
    except _md.PackageNotFoundError:
        return None


def ephemeris_provenance(provider) -> dict:
    """Provider name, library name/version and ephemeris data mode."""
    name = getattr(provider, "name", type(provider).__name__)
    if name == "swiss":
        import swisseph as swe

        using_files = bool(getattr(provider, "using_files", False))
        files: list[str] = []
        if using_files:
            from .providers import swiss as _swiss

            path = _swiss.ephe_path()
            if path:
                files = sorted(p.name for p in Path(path).glob("*.se1"))
        return {
            "provider": "swiss",
            "library": "pyswisseph",
            "libraryVersion": getattr(swe, "__version__", None) or _dist_version("pyswisseph"),
            "sweVersion": swe.version,
            "dataMode": "swiss-files" if using_files else "moshier-fallback",
            "ephemerisFiles": files,
            "meanAyanamsa": bool(getattr(provider, "mean_ayanamsa", False)),
        }
    if name == "astronomy":
        return {
            "provider": "astronomy",
            "library": "astronomy-engine",
            "libraryVersion": _dist_version("astronomy-engine"),
            "dataMode": "vsop87-analytic",
            "ephemerisFiles": [],
        }
    return {"provider": name, "library": None, "libraryVersion": None,
            "dataMode": "unknown", "ephemerisFiles": []}


def calculation_provenance(provider, *, ayanamsa_name: str, ayanamsa_value: float,
                           node_type: str, house_system: str = "whole_sign") -> dict:
    return {
        "ephemeris": ephemeris_provenance(provider),
        "ayanamsa": {"name": ayanamsa_name, "value": ayanamsa_value},
        "nodeType": node_type,
        "houseSystem": house_system,
    }
