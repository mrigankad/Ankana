"""Vimshottari dasha - exact port of dasha-vimshottari.ts.

Periods carry ISO-8601 millisecond strings identical to the TS engine so
serialized artifacts stay byte-compatible.
"""

from datetime import UTC, datetime, timedelta

from .zodiac import NAKSHATRA_LORD_CYCLE, nakshatra_of

VIMSHOTTARI_YEARS: dict[str, float] = {
    "ketu": 7, "venus": 20, "sun": 6, "moon": 10, "mars": 7,
    "rahu": 18, "jupiter": 16, "saturn": 19, "mercury": 17,
}

VIMSHOTTARI_TOTAL_YEARS = 120

_DAYS_PER_YEAR = 365.2425
_MS_PER_YEAR = _DAYS_PER_YEAR * 86_400_000


def iso_from_ms(ms: float) -> str:
    # epoch + timedelta: fromtimestamp() fails on Windows for pre-1970 instants
    dt = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=round(ms))
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _lord_sequence(start_lord: str) -> list[str]:
    start = NAKSHATRA_LORD_CYCLE.index(start_lord)
    return [NAKSHATRA_LORD_CYCLE[(start + i) % 9] for i in range(9)]


def _build_sub_periods(
    parent_planet: str, parent_start_ms: float, parent_years: float, level: str
) -> list[dict]:
    periods: list[dict] = []
    cursor = parent_start_ms
    for planet in _lord_sequence(parent_planet):
        years = parent_years * VIMSHOTTARI_YEARS[planet] / VIMSHOTTARI_TOTAL_YEARS
        end_ms = cursor + years * _MS_PER_YEAR
        period: dict = {
            "level": level,
            "planet": planet,
            "start": iso_from_ms(cursor),
            "end": iso_from_ms(end_ms),
        }
        if level == "antardasha":
            period["children"] = _build_sub_periods(
                planet, cursor, years, "pratyantardasha"
            )
        periods.append(period)
        cursor = end_ms
    return periods


def compute_vimshottari(moon_sidereal_longitude: float, birth_utc: datetime) -> dict:
    nakshatra = nakshatra_of(moon_sidereal_longitude)
    birth_lord = nakshatra.lord
    birth_lord_years = VIMSHOTTARI_YEARS[birth_lord]
    balance_years = birth_lord_years * (1 - nakshatra.fraction_traversed)

    mahadashas: list[dict] = []
    # The first mahadasha started before birth; its balance runs from birth.
    cursor = birth_utc.timestamp() * 1000 - (birth_lord_years - balance_years) * _MS_PER_YEAR

    for planet in _lord_sequence(birth_lord):
        years = VIMSHOTTARI_YEARS[planet]
        end_ms = cursor + years * _MS_PER_YEAR
        mahadashas.append(
            {
                "level": "mahadasha",
                "planet": planet,
                "start": iso_from_ms(cursor),
                "end": iso_from_ms(end_ms),
                "children": _build_sub_periods(planet, cursor, years, "antardasha"),
            }
        )
        cursor = end_ms

    return {
        "birthNakshatra": nakshatra.name,
        "birthLord": birth_lord,
        "balanceYears": balance_years,
        "mahadashas": mahadashas,
    }
