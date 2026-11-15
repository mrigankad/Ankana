"""Generate provisional reference cases with Swiss Ephemeris.

Truth is `swisseph-provisional` until each case is replaced by a JHora export
(same file name, source "jhora-<version>", settings copied from JHora).

    python scripts/generate_reference_cases.py
"""

import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "reference"))

import runner  # noqa: E402

from nakshatra_core.providers import get_provider  # noqa: E402
from nakshatra_core.time import to_utc_datetime  # noqa: E402

CASES = [
    ("ananya-sharma", "Ananya Sharma, Varanasi (spec example)", "1995-03-15", "06:42",
     "Asia/Kolkata", 25.3176, 82.9739),
    ("delhi-1984", "Delhi, evening", "1984-10-31", "17:20", "Asia/Kolkata", 28.6139, 77.2090),
    ("london-dst-1962", "London, British Summer Time", "1962-07-04", "14:05", "Europe/London",
     51.5074, -0.1278),
    ("sydney-1988", "Southern hemisphere, DST", "1988-12-25", "03:30", "Australia/Sydney",
     -33.8688, 151.2093),
    ("tromso-1975", "High latitude 69.6N", "1975-09-10", "08:15", "Europe/Oslo", 69.6492,
     18.9553),
    ("newyork-2003", "New York winter", "2003-01-20", "22:47", "America/New_York", 40.7128,
     -74.0060),
    ("chennai-2010-dawn", "Birth minutes before sunrise", "2010-05-05", "05:38", "Asia/Kolkata",
     13.0827, 80.2707),
    ("mumbai-1947", "Historic date, midnight", "1947-08-15", "00:00", "Asia/Kolkata", 19.0760,
     72.8777),
    ("bengaluru-2040", "Future date", "2040-02-29", "11:11", "Asia/Kolkata", 12.9716, 77.5946),
    ("losangeles-1999", "Year-end, PST", "1999-12-31", "23:59", "America/Los_Angeles", 34.0522,
     -118.2437),
    ("nairobi-1971", "Equatorial, retrograde Saturn era", "1971-03-03", "10:00", "Africa/Nairobi",
     -1.2921, 36.8219),
]


def boundary_case(provider) -> tuple:
    """Find a birth minute where the Moon is just past a nakshatra boundary (sidereal)."""
    base = to_utc_datetime("2001-06-10", "00:00", "Asia/Kolkata")
    span = 360 / 27
    t = base
    while True:
        a = (provider.planet("moon", t).longitude - provider.ayanamsa(t)) % 360
        b = (provider.planet("moon", t + timedelta(minutes=1)).longitude
             - provider.ayanamsa(t + timedelta(minutes=1))) % 360
        if int(a // span) != int(b // span):
            break
        t += timedelta(minutes=1)
    local = (t + timedelta(minutes=1)).astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
    return ("moon-nakshatra-boundary", "Moon within ~0.01 deg of a nakshatra boundary",
            local.strftime("%Y-%m-%d"), local.strftime("%H:%M"), "Asia/Kolkata", 22.5726,
            88.3639)


def main() -> None:
    provider = get_provider("swiss")
    if not provider.using_files:
        sys.exit("Swiss .se1 data files missing: run scripts/fetch_ephe.py first")
    out = runner.CASES_DIR
    out.mkdir(parents=True, exist_ok=True)
    for cid, note, date, time, tz, lat, lon in [*CASES, boundary_case(provider)]:
        case = {
            "id": cid,
            "note": note,
            "source": "swisseph-provisional",
            "settings": {
                "ayanamsa": "lahiri",
                "ayanamsaMean": provider.mean_ayanamsa,
                "node": "mean",
                "sunriseRule": "hindu",
                "houseSystem": "whole_sign",
                "ephemerisFiles": "swisseph 2.10.03, sepl/semo/seas_18.se1",
            },
            "input": {"birthDate": date, "birthTime": time, "timezoneName": tz,
                      "latitude": lat, "longitude": lon},
        }
        case["expected"] = runner.compute(case, provider)
        (out / f"{cid}.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        print("wrote", cid)


if __name__ == "__main__":
    main()
