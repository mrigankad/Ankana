"""Sidereal zodiac mapping - exact port of zodiac.ts."""

import math
from dataclasses import dataclass

SIGN_NAMES = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

SIGN_LORDS = (
    "mars", "venus", "mercury", "moon", "sun", "mercury",
    "venus", "mars", "jupiter", "saturn", "saturn", "jupiter",
)

NAKSHATRA_NAMES = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
)

# Vimshottari lord cycle: repeats three times across the 27 nakshatras.
NAKSHATRA_LORD_CYCLE = (
    "ketu", "venus", "sun", "moon", "mars", "rahu", "jupiter", "saturn", "mercury",
)

NAKSHATRA_SPAN = 360 / 27  # 13deg 20min


@dataclass(frozen=True)
class SignPosition:
    index: int
    name: str
    lord: str
    degrees_in_sign: float


@dataclass(frozen=True)
class NakshatraPosition:
    index: int
    name: str
    lord: str
    pada: int
    fraction_traversed: float


def sign_of(sidereal_longitude: float) -> SignPosition:
    index = math.floor(sidereal_longitude / 30) % 12
    return SignPosition(
        index=index,
        name=SIGN_NAMES[index],
        lord=SIGN_LORDS[index],
        degrees_in_sign=sidereal_longitude - index * 30,
    )


def nakshatra_of(sidereal_longitude: float) -> NakshatraPosition:
    index = math.floor(sidereal_longitude / NAKSHATRA_SPAN) % 27
    within = sidereal_longitude - index * NAKSHATRA_SPAN
    return NakshatraPosition(
        index=index,
        name=NAKSHATRA_NAMES[index],
        lord=NAKSHATRA_LORD_CYCLE[index % 9],
        pada=math.floor(within / (NAKSHATRA_SPAN / 4)) + 1,
        fraction_traversed=within / NAKSHATRA_SPAN,
    )


def is_odd_sign(sign_index: int) -> bool:
    return sign_index % 2 == 0  # Aries (0) is the first odd sign.


def sign_modality(sign_index: int) -> str:
    return ("movable", "fixed", "dual")[sign_index % 3]
