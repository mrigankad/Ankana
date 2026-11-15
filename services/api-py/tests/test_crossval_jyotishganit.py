"""Independent cross-validation against jyotishganit (Skyfield + JPL DE421,
True Chitra Paksha ayanamsa). Different ephemeris and ayanamsa variant, so
agreement on discrete fields is strong evidence of correctness.

Skipped automatically when the optional dependency is unavailable.
"""

import pytest

jyotishganit = pytest.importorskip("jyotishganit")

from datetime import datetime  # noqa: E402

from nakshatra_core.chart import compute_vedic_chart_artifact  # noqa: E402

CASES = [
    ("raiganj-2003", "2003-08-29", "12:22", 5.5, 25.6167, 88.1233),
    ("varanasi-1990", "1990-01-01", "10:30", 5.5, 25.3176, 82.9739),
]

ARCMIN_2 = 2 / 60


def _their_chart(date: str, time: str, tz: float, lat: float, lon: float):
    from jyotishganit import calculate_birth_chart

    year, month, day = (int(x) for x in date.split("-"))
    hour, minute = (int(x) for x in time.split(":"))
    return calculate_birth_chart(
        datetime(year, month, day, hour, minute), lat, lon, tz
    )


@pytest.mark.parametrize("label,date,time,tz,lat,lon", CASES)
def test_signs_and_nakshatras_agree(label, date, time, tz, lat, lon) -> None:
    ours = compute_vedic_chart_artifact(
        {
            "birthDate": date,
            "birthTime": time,
            "timezoneName": "Asia/Kolkata",
            "latitude": lat,
            "longitude": lon,
        }
    )
    theirs = _their_chart(date, time, tz, lat, lon)

    their_planets = {
        p.celestial_body.lower(): p for p in theirs.d1_chart.planets
    }
    mismatches = []
    for planet in ours["planets"]:
        name = planet["planet"]
        if name not in their_planets:
            continue
        theirs_p = their_planets[name]
        if theirs_p.sign != planet["signName"]:
            mismatches.append(
                f"{label} {name}: sign {planet['signName']} vs {theirs_p.sign}"
            )
        if theirs_p.nakshatra != planet["nakshatra"]:
            mismatches.append(
                f"{label} {name}: nakshatra {planet['nakshatra']} vs "
                f"{theirs_p.nakshatra}"
            )
    assert not mismatches, "\n".join(mismatches)
