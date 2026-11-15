"""Simplified Shadbala - exact port of shadbala.ts.

Implements the dominant classical terms exactly (uccha, kendradi, ojayugma,
dig, naisargika, paksha, nathonnatha) and substitutes documented neutral
values where the full BPHS term needs data outside the current artifact.
Ratio ordering is the product-facing contract.
"""

from .aspects import sign_count
from .dignities import dignity_of
from .vargas import varga_sign
from .zodiac import is_odd_sign, sign_of

SHADBALA_PLANETS = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn")

# Deep-debilitation longitudes (uccha bala measures distance from these).
_DEBILITATION_POINT = {
    "sun": 190, "moon": 213, "mars": 118, "mercury": 345,
    "jupiter": 275, "venus": 177, "saturn": 20,
}

# Naisargika (natural) strength in virupas, fixed by BPHS.
_NAISARGIKA = {
    "sun": 60, "moon": 51.43, "venus": 42.86, "jupiter": 34.29,
    "mercury": 25.71, "mars": 17.14, "saturn": 8.57,
}

# House where each planet gains full directional strength.
_DIG_BALA_HOUSE = {
    "jupiter": 1, "mercury": 1, "sun": 10, "mars": 10,
    "saturn": 7, "moon": 4, "venus": 4,
}

# Classical minimum requirements in rupas (1 rupa = 60 virupas).
_REQUIRED_RUPAS = {
    "sun": 5, "moon": 6, "mars": 5, "mercury": 7,
    "jupiter": 6.5, "venus": 5.5, "saturn": 5,
}

_DIGNITY_VIRUPAS = {
    "exalted": 30, "moolatrikona": 25, "own": 20, "friend": 15,
    "neutral": 10, "enemy": 5, "debilitated": 2,
}


def compute_shadbala(
    longitudes: dict[str, float],
    ascendant_longitude: float,
    moon_sun_elongation: float,
    retrograde: dict[str, bool],
    is_day_birth: bool,
) -> list[dict]:
    asc_sign = sign_of(ascendant_longitude).index
    results: list[dict] = []

    for planet in SHADBALA_PLANETS:
        lon = longitudes[planet]
        sign = sign_of(lon).index

        # Sthana bala. Uccha: 0 at deep debilitation, 60 at deep exaltation.
        distance = abs((lon - _DEBILITATION_POINT[planet]) % 360)
        arc = 360 - distance if distance > 180 else distance
        uccha = arc / 3

        # Kendradi bala: kendra 60, panapara 30, apoklima 15.
        house = sign_count(asc_sign, sign)
        if house in (1, 4, 7, 10):
            kendradi = 60
        elif house in (2, 5, 8, 11):
            kendradi = 30
        else:
            kendradi = 15

        # Ojayugma: Moon and Venus favor even signs, the rest odd (D1 + D9).
        prefers_even = planet in ("moon", "venus")
        d9 = varga_sign("d9", lon)
        ojayugma = 0
        if is_odd_sign(sign) != prefers_even:
            ojayugma += 15
        if is_odd_sign(d9) != prefers_even:
            ojayugma += 15

        # Saptavargaja simplified to D1 + D9 dignity contributions.
        saptavargaja = (
            _DIGNITY_VIRUPAS[dignity_of(planet, lon)]
            + _DIGNITY_VIRUPAS[dignity_of(planet, d9 * 30 + 15)]
        )

        sthana = uccha + kendradi + ojayugma + saptavargaja

        # Dig bala: 60 at the power house cusp, 0 opposite.
        power_house = _DIG_BALA_HOUSE[planet]
        house_gap = min(abs(house - power_house), 12 - abs(house - power_house))
        dig = 60 * (1 - house_gap / 6)

        # Kala bala (simplified). Nathonnatha: Moon/Mars/Saturn strong at
        # night, Sun/Jupiter/Venus by day, Mercury always strong.
        day_strong = planet in ("sun", "jupiter", "venus")
        if planet == "mercury":
            nathonnatha = 60
        else:
            nathonnatha = 60 if is_day_birth == day_strong else 0

        # Paksha bala: benefics wax with the Moon, malefics wane.
        elongation_arc = (
            360 - moon_sun_elongation
            if moon_sun_elongation > 180
            else moon_sun_elongation
        )
        paksha_benefic = elongation_arc / 3
        benefic = planet in ("moon", "mercury", "jupiter", "venus")
        paksha = paksha_benefic if benefic else 60 - paksha_benefic

        # Remaining kala sub-balas held neutral (documented simplification).
        kala = nathonnatha + paksha + 30

        # Cheshta bala (simplified motion strength).
        if planet in ("sun", "moon"):
            cheshta = 30
        else:
            cheshta = 60 if retrograde[planet] else 30

        # Drik bala held neutral (sign-aspect model too coarse).
        drik = 0

        total_virupas = sthana + dig + kala + cheshta + _NAISARGIKA[planet] + drik
        total_rupas = total_virupas / 60

        results.append(
            {
                "planet": planet,
                "sthana": sthana,
                "dig": dig,
                "kala": kala,
                "cheshta": cheshta,
                "naisargika": _NAISARGIKA[planet],
                "drik": drik,
                "totalVirupas": total_virupas,
                "totalRupas": total_rupas,
                "requiredRupas": _REQUIRED_RUPAS[planet],
                "ratio": total_rupas / _REQUIRED_RUPAS[planet],
            }
        )

    return results
