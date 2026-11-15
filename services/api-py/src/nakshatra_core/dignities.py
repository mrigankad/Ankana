"""Planetary dignities and combustion - exact port of dignities.ts."""

from .ephemeris import normalize_degrees
from .zodiac import sign_of

PLANETS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "rahu", "ketu")

# planet -> (exaltation sign, own signs, moolatrikona [sign, from_deg, to_deg])
_DIGNITY_TABLE: dict[str, tuple[int, tuple[int, ...], tuple[int, int, int] | None]] = {
    "sun": (0, (4,), (4, 0, 20)),
    "moon": (1, (3,), (1, 3, 30)),
    "mars": (9, (0, 7), (0, 0, 12)),
    "mercury": (5, (2, 5), (5, 15, 20)),
    "jupiter": (3, (8, 11), (8, 0, 10)),
    "venus": (11, (1, 6), (6, 0, 15)),
    "saturn": (6, (9, 10), (10, 0, 20)),
}

# Naisargika (natural) friendships.
_FRIENDS: dict[str, tuple[str, ...]] = {
    "sun": ("moon", "mars", "jupiter"),
    "moon": ("sun", "mercury"),
    "mars": ("sun", "moon", "jupiter"),
    "mercury": ("sun", "venus"),
    "jupiter": ("sun", "moon", "mars"),
    "venus": ("mercury", "saturn"),
    "saturn": ("mercury", "venus"),
}

_ENEMIES: dict[str, tuple[str, ...]] = {
    "sun": ("venus", "saturn"),
    "moon": (),
    "mars": ("mercury",),
    "mercury": ("moon",),
    "jupiter": ("mercury", "venus"),
    "venus": ("sun", "moon"),
    "saturn": ("sun", "moon", "mars"),
}

_SIGN_LORD_PLANETS = (
    "mars", "venus", "mercury", "moon", "sun", "mercury",
    "venus", "mars", "jupiter", "saturn", "saturn", "jupiter",
)


def dignity_of(planet: str, sidereal_longitude: float) -> str:
    if planet in ("rahu", "ketu"):
        # Nodes have no classical dignity scheme in v1; treated as neutral.
        return "neutral"

    exaltation, own_signs, moolatrikona = _DIGNITY_TABLE[planet]
    sign = sign_of(sidereal_longitude)
    debilitation = (exaltation + 6) % 12

    if sign.index == exaltation:
        return "exalted"
    if sign.index == debilitation:
        return "debilitated"
    if (
        moolatrikona
        and sign.index == moolatrikona[0]
        and moolatrikona[1] <= sign.degrees_in_sign < moolatrikona[2]
    ):
        return "moolatrikona"
    if sign.index in own_signs:
        return "own"

    dispositor = _SIGN_LORD_PLANETS[sign.index]
    if dispositor == planet:
        return "own"
    if dispositor in _FRIENDS[planet]:
        return "friend"
    if dispositor in _ENEMIES[planet]:
        return "enemy"
    return "neutral"


# Classical combustion orbs in degrees from the Sun: (direct, retrograde).
_COMBUSTION_ORBS: dict[str, tuple[float, float]] = {
    "moon": (12, 12),
    "mars": (17, 17),
    "mercury": (14, 12),
    "jupiter": (11, 11),
    "venus": (10, 8),
    "saturn": (15, 15),
}


def is_combust(
    planet: str,
    planet_tropical_longitude: float,
    sun_tropical_longitude: float,
    retrograde: bool,
) -> bool:
    orbs = _COMBUSTION_ORBS.get(planet)
    if orbs is None:
        return False
    separation = min(
        normalize_degrees(planet_tropical_longitude - sun_tropical_longitude),
        normalize_degrees(sun_tropical_longitude - planet_tropical_longitude),
    )
    return separation <= (orbs[1] if retrograde else orbs[0])
