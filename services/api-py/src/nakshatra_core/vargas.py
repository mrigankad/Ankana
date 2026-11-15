"""Divisional (varga) charts - exact port of vargas.ts."""

import math

from .zodiac import is_odd_sign, sign_of

VARGA_KEYS = ("d1", "d2", "d3", "d7", "d9", "d10", "d12", "d30", "d60")

_DIVISIONS = {"d1": 1, "d2": 2, "d3": 3, "d7": 7, "d9": 9, "d10": 10, "d12": 12,
              "d30": 30, "d60": 60}

# Trimsamsa spans: (to_degree, result_sign) applied in order.
_TRIMSAMSA_ODD = ((5, 0), (10, 10), (18, 8), (25, 2), (30, 6))
_TRIMSAMSA_EVEN = ((5, 1), (12, 5), (20, 11), (25, 9), (30, 7))


def varga_sign(chart: str, sidereal_longitude: float) -> int:
    """Sidereal longitude -> sign index (0-11) in the requested divisional chart."""
    pos = sign_of(sidereal_longitude)
    sign, degrees_in_sign = pos.index, pos.degrees_in_sign
    divisions = _DIVISIONS[chart]
    part = min(math.floor(degrees_in_sign / (30 / divisions)), divisions - 1)

    if chart == "d1":
        return sign
    if chart == "d2":
        # Odd signs: Leo then Cancer. Even signs: Cancer then Leo.
        leo_first = is_odd_sign(sign)
        is_first_half = part == 0
        return 4 if is_first_half == leo_first else 3
    if chart == "d3":
        return (sign + part * 4) % 12  # same, 5th, 9th
    if chart == "d7":
        return (sign * 7 + part) % 12
    if chart == "d9":
        return (sign * 9 + part) % 12
    if chart == "d10":
        return ((sign if is_odd_sign(sign) else sign + 8) + part) % 12
    if chart == "d12":
        return (sign + part) % 12
    if chart == "d30":
        spans = _TRIMSAMSA_ODD if is_odd_sign(sign) else _TRIMSAMSA_EVEN
        for to_degree, result_sign in spans:
            if degrees_in_sign < to_degree:
                return result_sign
        return spans[-1][1]
    if chart == "d60":
        return (sign + part) % 12
    raise ValueError(f"unknown varga chart: {chart}")


def compute_varga_charts(
    planet_longitudes: dict[str, float], ascendant_longitude: float
) -> dict[str, dict]:
    return {
        chart: {
            "ascendantSign": varga_sign(chart, ascendant_longitude),
            "planets": {
                planet: varga_sign(chart, lon)
                for planet, lon in planet_longitudes.items()
            },
        }
        for chart in VARGA_KEYS
    }
