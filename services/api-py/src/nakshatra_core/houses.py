"""Whole-sign houses - exact port of houses.ts."""

from dataclasses import dataclass

from .zodiac import SIGN_LORDS, SIGN_NAMES, sign_of


@dataclass(frozen=True)
class House:
    number: int
    sign_index: int
    sign_name: str
    lord: str


def whole_sign_houses(ascendant_sidereal_longitude: float) -> list[House]:
    asc_sign = sign_of(ascendant_sidereal_longitude).index
    return [
        House(
            number=offset + 1,
            sign_index=(asc_sign + offset) % 12,
            sign_name=SIGN_NAMES[(asc_sign + offset) % 12],
            lord=SIGN_LORDS[(asc_sign + offset) % 12],
        )
        for offset in range(12)
    ]


def house_of(sidereal_longitude: float, ascendant_sidereal_longitude: float) -> int:
    asc_sign = sign_of(ascendant_sidereal_longitude).index
    body_sign = sign_of(sidereal_longitude).index
    return ((body_sign - asc_sign + 12) % 12) + 1
