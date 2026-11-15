"""Panchang (tithi, karana, yoga, vara, moon nakshatra) - exact port of panchang.ts."""

import math
from dataclasses import dataclass

from .ephemeris import normalize_degrees
from .zodiac import nakshatra_of

TITHI_NAMES = (
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi",
)

YOGA_NAMES = (
    "Vishkumbha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha",
    "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra",
    "Vaidhriti",
)

_MOVABLE_KARANAS = ("Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti")
_FIXED_KARANAS = ("Shakuni", "Chatushpada", "Naga", "Kimstughna")

VARA_NAMES = (
    "Ravivara", "Somavara", "Mangalavara", "Budhavara", "Guruvara",
    "Shukravara", "Shanivara",
)


@dataclass(frozen=True)
class Tithi:
    index: int
    name: str
    paksha: str


@dataclass(frozen=True)
class NamedIndex:
    index: int
    name: str


@dataclass(frozen=True)
class MoonNakshatra:
    index: int
    name: str
    pada: int


@dataclass(frozen=True)
class Panchang:
    tithi: Tithi
    karana: NamedIndex
    yoga: NamedIndex
    vara: NamedIndex
    moon_nakshatra: MoonNakshatra


def compute_panchang(
    sun_sidereal_longitude: float,
    moon_sidereal_longitude: float,
    local_weekday: int,
) -> Panchang:
    elongation = normalize_degrees(moon_sidereal_longitude - sun_sidereal_longitude)

    tithi_index = math.floor(elongation / 12)  # 0-29
    paksha = "shukla" if tithi_index < 15 else "krishna"
    within = tithi_index % 15
    if within == 14:
        tithi_name = "Purnima" if paksha == "shukla" else "Amavasya"
    else:
        tithi_name = TITHI_NAMES[within]

    # 60 half-tithi karanas: Kimstughna leads, 7 movable karanas repeat
    # eight times, and the final three are the remaining fixed karanas.
    karana_index = math.floor(elongation / 6)  # 0-59
    if karana_index == 0:
        karana_name = _FIXED_KARANAS[3]  # Kimstughna
    elif karana_index >= 57:
        karana_name = _FIXED_KARANAS[karana_index - 57]  # Shakuni, Chatushpada, Naga
    else:
        karana_name = _MOVABLE_KARANAS[(karana_index - 1) % 7]

    yoga_index = math.floor(
        normalize_degrees(sun_sidereal_longitude + moon_sidereal_longitude) / (360 / 27)
    )

    moon_nak = nakshatra_of(moon_sidereal_longitude)

    return Panchang(
        tithi=Tithi(index=tithi_index + 1, name=tithi_name, paksha=paksha),
        karana=NamedIndex(index=karana_index + 1, name=karana_name),
        yoga=NamedIndex(index=yoga_index + 1, name=YOGA_NAMES[yoga_index]),
        vara=NamedIndex(index=local_weekday, name=VARA_NAMES[local_weekday]),
        moon_nakshatra=MoonNakshatra(
            index=moon_nak.index + 1, name=moon_nak.name, pada=moon_nak.pada
        ),
    )
