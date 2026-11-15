"""Yogini dasha - exact port of dasha-yogini.ts."""

from datetime import datetime

from .dasha_vimshottari import iso_from_ms
from .zodiac import nakshatra_of

# The eight yoginis in sequence with their lords and years (36y cycle).
YOGINIS = (
    {"name": "Mangala", "planet": "moon", "years": 1},
    {"name": "Pingala", "planet": "sun", "years": 2},
    {"name": "Dhanya", "planet": "jupiter", "years": 3},
    {"name": "Bhramari", "planet": "mars", "years": 4},
    {"name": "Bhadrika", "planet": "mercury", "years": 5},
    {"name": "Ulka", "planet": "saturn", "years": 6},
    {"name": "Siddha", "planet": "venus", "years": 7},
    {"name": "Sankata", "planet": "rahu", "years": 8},
)

YOGINI_CYCLE_YEARS = 36

_MS_PER_YEAR = 365.2425 * 86_400_000


def compute_yogini(moon_sidereal_longitude: float, birth_utc: datetime) -> dict:
    """Starting yogini index follows the classical rule (nakshatra number + 3)
    mod 8, mapping remainder 1..8 onto Mangala..Sankata; balance is the
    untraversed fraction of that yogini's span."""
    nakshatra = nakshatra_of(moon_sidereal_longitude)
    nakshatra_number = nakshatra.index + 1  # 1-based
    remainder = (nakshatra_number + 3) % 8
    start_index = (8 if remainder == 0 else remainder) - 1  # 0-based

    start_yogini = YOGINIS[start_index]
    balance_years = start_yogini["years"] * (1 - nakshatra.fraction_traversed)

    mahadashas: list[dict] = []
    cursor = (
        birth_utc.timestamp() * 1000
        - (start_yogini["years"] - balance_years) * _MS_PER_YEAR
    )

    # Two full cycles = 72 years of coverage from the birth yogini.
    for i in range(16):
        yogini = YOGINIS[(start_index + i) % 8]
        end_ms = cursor + yogini["years"] * _MS_PER_YEAR

        children: list[dict] = []
        sub_cursor = cursor
        for j in range(8):
            # Antardashas run in sequence from the mahadasha's own yogini,
            # each proportional to its years within the 36-year total.
            sub = YOGINIS[((start_index + i) % 8 + j) % 8]
            sub_years = yogini["years"] * sub["years"] / YOGINI_CYCLE_YEARS
            sub_end = sub_cursor + sub_years * _MS_PER_YEAR
            children.append(
                {
                    "level": "antardasha",
                    "planet": sub["planet"],
                    "name": sub["name"],
                    "start": iso_from_ms(sub_cursor),
                    "end": iso_from_ms(sub_end),
                }
            )
            sub_cursor = sub_end

        mahadashas.append(
            {
                "level": "mahadasha",
                "planet": yogini["planet"],
                "name": yogini["name"],
                "start": iso_from_ms(cursor),
                "end": iso_from_ms(end_ms),
                "children": children,
            }
        )
        cursor = end_ms

    return {
        "birthNakshatra": nakshatra.name,
        "birthYogini": start_yogini["name"],
        "balanceYears": balance_years,
        "mahadashas": mahadashas,
    }
