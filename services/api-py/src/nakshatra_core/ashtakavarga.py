"""Ashtakavarga and Sarvashtakavarga - exact port of ashtakavarga.ts.

Classical Bhinnashtakavarga benefic-place tables (BPHS). Row totals give the
classical bindu counts: Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56,
Venus 52, Saturn 39; Sarvashtakavarga total 337.
"""

ASHTAKAVARGA_PLANETS = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn")

_CONTRIBUTORS = (*ASHTAKAVARGA_PLANETS, "lagna")

_BENEFIC_PLACES: dict[str, dict[str, tuple[int, ...]]] = {
    "sun": {
        "sun": (1, 2, 4, 7, 8, 9, 10, 11),
        "moon": (3, 6, 10, 11),
        "mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "mercury": (3, 5, 6, 9, 10, 11, 12),
        "jupiter": (5, 6, 9, 11),
        "venus": (6, 7, 12),
        "saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "lagna": (3, 4, 6, 10, 11, 12),
    },
    "moon": {
        "sun": (3, 6, 7, 8, 10, 11),
        "moon": (1, 3, 6, 7, 10, 11),
        "mars": (2, 3, 5, 6, 9, 10, 11),
        "mercury": (1, 3, 4, 5, 7, 8, 10, 11),
        "jupiter": (1, 4, 7, 8, 10, 11, 12),
        "venus": (3, 4, 5, 7, 9, 10, 11),
        "saturn": (3, 5, 6, 11),
        "lagna": (3, 6, 10, 11),
    },
    "mars": {
        "sun": (3, 5, 6, 10, 11),
        "moon": (3, 6, 11),
        "mars": (1, 2, 4, 7, 8, 10, 11),
        "mercury": (3, 5, 6, 11),
        "jupiter": (6, 10, 11, 12),
        "venus": (6, 8, 11, 12),
        "saturn": (1, 4, 7, 8, 9, 10, 11),
        "lagna": (1, 3, 6, 10, 11),
    },
    "mercury": {
        "sun": (5, 6, 9, 11, 12),
        "moon": (2, 4, 6, 8, 10, 11),
        "mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "mercury": (1, 3, 5, 6, 9, 10, 11, 12),
        "jupiter": (6, 8, 11, 12),
        "venus": (1, 2, 3, 4, 5, 8, 9, 11),
        "saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "lagna": (1, 2, 4, 6, 8, 10, 11),
    },
    "jupiter": {
        "sun": (1, 2, 3, 4, 7, 8, 9, 10, 11),
        "moon": (2, 5, 7, 9, 11),
        "mars": (1, 2, 4, 7, 8, 10, 11),
        "mercury": (1, 2, 4, 5, 6, 9, 10, 11),
        "jupiter": (1, 2, 3, 4, 7, 8, 10, 11),
        "venus": (2, 5, 6, 9, 10, 11),
        "saturn": (3, 5, 6, 12),
        "lagna": (1, 2, 4, 5, 6, 7, 9, 10, 11),
    },
    "venus": {
        "sun": (8, 11, 12),
        "moon": (1, 2, 3, 4, 5, 8, 9, 11, 12),
        "mars": (3, 5, 6, 9, 11, 12),
        "mercury": (3, 5, 6, 9, 11),
        "jupiter": (5, 8, 9, 10, 11),
        "venus": (1, 2, 3, 4, 5, 8, 9, 10, 11),
        "saturn": (3, 4, 5, 8, 9, 10, 11),
        "lagna": (1, 2, 3, 4, 5, 8, 9, 11),
    },
    "saturn": {
        "sun": (1, 2, 4, 7, 8, 10, 11),
        "moon": (3, 6, 11),
        "mars": (3, 5, 6, 10, 11, 12),
        "mercury": (6, 8, 9, 10, 11, 12),
        "jupiter": (5, 6, 11, 12),
        "venus": (6, 11, 12),
        "saturn": (3, 5, 6, 11),
        "lagna": (1, 3, 4, 6, 10, 11),
    },
}


def compute_ashtakavarga(signs: dict[str, int], ascendant_sign: int) -> list[dict]:
    results: list[dict] = []
    for target in ASHTAKAVARGA_PLANETS:
        bindus_by_sign = [0] * 12
        for contributor in _CONTRIBUTORS:
            from_sign = ascendant_sign if contributor == "lagna" else signs[contributor]
            for house in _BENEFIC_PLACES[target][contributor]:
                bindus_by_sign[(from_sign + house - 1) % 12] += 1
        results.append(
            {
                "planet": target,
                "bindusBySign": bindus_by_sign,
                "totalBindus": sum(bindus_by_sign),
            }
        )
    return results


def compute_sarvashtakavarga(results: list[dict]) -> list[int]:
    """Per-sign sums across the seven bhinnashtakavargas."""
    sums = [0] * 12
    for result in results:
        for sign, bindus in enumerate(result["bindusBySign"]):
            sums[sign] += bindus
    return sums
