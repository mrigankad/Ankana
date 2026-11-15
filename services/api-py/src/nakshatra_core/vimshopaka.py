"""Vimshopaka bala (shadvarga scheme) - exact port of vimshopaka.ts."""

import math

from .dignities import dignity_of
from .vargas import varga_sign

# Shadvarga weights totalling 20 (BPHS vimshopaka, shadvarga scheme).
_SHADVARGA_WEIGHTS = {"d1": 6, "d2": 2, "d3": 4, "d9": 5, "d12": 2, "d30": 1}

# Fraction of a varga's weight earned per dignity in that varga.
_DIGNITY_FRACTION = {
    "exalted": 1, "moolatrikona": 1, "own": 1, "friend": 0.75,
    "neutral": 0.5, "enemy": 0.25, "debilitated": 0.125,
}

_SCORED_PLANETS = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn")


def compute_vimshopaka(longitudes: dict[str, float]) -> list[dict]:
    results: list[dict] = []
    for planet in _SCORED_PLANETS:
        score = 0.0
        for chart, weight in _SHADVARGA_WEIGHTS.items():
            sign = varga_sign(chart, longitudes[planet])
            # Dignity evaluated at the varga sign's midpoint.
            dignity = dignity_of(planet, sign * 30 + 15)
            score += weight * _DIGNITY_FRACTION[dignity]
        # JS Math.round semantics (half away from zero for positives).
        results.append({"planet": planet, "score": math.floor(score * 100 + 0.5) / 100})
    return results
