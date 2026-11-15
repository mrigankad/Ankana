from datetime import datetime
from zoneinfo import ZoneInfo

from nakshatra_core.panchang import compute_panchang
from nakshatra_core.time import to_utc_datetime


def test_panchang_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        inp = chart["input"]
        golden = chart["artifact"]["panchang"]
        planets = {p["planet"]: p for p in chart["artifact"]["planets"]}
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        local = dt.astimezone(ZoneInfo(inp["timezoneName"]))
        weekday = _js_weekday(local)
        result = compute_panchang(
            planets["sun"]["siderealLongitude"],
            planets["moon"]["siderealLongitude"],
            weekday,
        )
        label = chart["label"]
        assert result.tithi.index == golden["tithi"]["index"], label
        assert result.tithi.name == golden["tithi"]["name"], label
        assert result.tithi.paksha == golden["tithi"]["paksha"], label
        assert result.karana.name == golden["karana"]["name"], label
        assert result.yoga.name == golden["yoga"]["name"], label
        assert result.vara.name == golden["vara"]["name"], label
        assert result.moon_nakshatra.name == golden["moonNakshatra"]["name"], label
        assert result.moon_nakshatra.pada == golden["moonNakshatra"]["pada"], label


def _js_weekday(local: datetime) -> int:
    # JS Date.getDay(): Sunday=0 .. Saturday=6; Python weekday(): Monday=0.
    return (local.weekday() + 1) % 7
