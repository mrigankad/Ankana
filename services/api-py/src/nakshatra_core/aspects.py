"""Graha drishti aspects and conjunctions - exact port of aspects.ts."""

# Extra full sign aspects beyond the universal 7th, per graha drishti.
_SPECIAL_ASPECTS: dict[str, tuple[int, ...]] = {
    "mars": (4, 8),
    "jupiter": (5, 9),
    "saturn": (3, 10),
}

_ASPECTING_PLANETS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")


def sign_count(from_sign: int, to_sign: int) -> int:
    """Inclusive sign count from one sign to another (1-12)."""
    return ((to_sign - from_sign + 12) % 12) + 1


def compute_aspects(planet_signs: dict[str, int]) -> list[dict]:
    aspects: list[dict] = []
    for source in _ASPECTING_PLANETS:
        casts = (7, *_SPECIAL_ASPECTS.get(source, ()))
        for target, to_sign in planet_signs.items():
            if target == source:
                continue
            count = sign_count(planet_signs[source], to_sign)
            if count in casts:
                aspects.append({"from": source, "to": target, "count": count})
    return aspects


def compute_conjunctions(planet_signs: dict[str, int]) -> list[dict]:
    by_sign: dict[int, list[str]] = {}
    for planet, sign in planet_signs.items():
        by_sign.setdefault(sign, []).append(planet)
    return [
        {"signIndex": sign, "planets": planets}
        for sign, planets in sorted(by_sign.items())
        if len(planets) > 1
    ]
