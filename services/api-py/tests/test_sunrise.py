from datetime import datetime
from zoneinfo import ZoneInfo

from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_core.sunrise import last_sunrise_and_next_sunset
from nakshatra_core.time import to_utc_datetime

RAIGANJ = {
    "birthDate": "2003-08-29",
    "birthTime": "12:22",
    "timezoneName": "Asia/Kolkata",
    "latitude": 25.6167,
    "longitude": 88.1233,
}


def test_sunrise_before_midday_birth() -> None:
    birth = to_utc_datetime("2003-08-29", "12:22", "Asia/Kolkata")
    sunrise, sunset = last_sunrise_and_next_sunset(birth, 25.6167, 88.1233)
    local_rise = sunrise.astimezone(ZoneInfo("Asia/Kolkata"))
    assert local_rise.date() == datetime(2003, 8, 29).date()
    assert 4 <= local_rise.hour <= 6
    assert sunset > sunrise


def test_vara_unchanged_for_daytime_birth() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    assert artifact["panchang"]["vara"]["name"] == "Shukravara"  # Friday
    assert "sunrise" in artifact and "sunset" in artifact


def test_vara_uses_previous_day_before_sunrise() -> None:
    # 03:00 IST on Friday 2003-08-29 is before sunrise: vara is still Thursday.
    artifact = compute_vedic_chart_artifact({**RAIGANJ, "birthTime": "03:00"})
    assert artifact["panchang"]["vara"]["name"] == "Guruvara"
