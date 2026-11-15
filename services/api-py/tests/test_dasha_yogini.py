from datetime import datetime

from nakshatra_core.dasha_yogini import compute_yogini
from nakshatra_core.time import to_utc_datetime

MS_MINUTE = 60_000


def _iso_to_ms(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000


def _assert_periods(ours: list[dict], golden: list[dict], label: str) -> None:
    assert len(ours) == len(golden), label
    for mine, gold in zip(ours, golden, strict=True):
        assert mine["planet"] == gold["planet"], label
        assert mine.get("name") == gold.get("name"), label
        assert abs(_iso_to_ms(mine["start"]) - _iso_to_ms(gold["start"])) <= MS_MINUTE, label
        assert abs(_iso_to_ms(mine["end"]) - _iso_to_ms(gold["end"])) <= MS_MINUTE, label
        if gold.get("children"):
            _assert_periods(mine.get("children", []), gold["children"], label)


def test_yogini_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        inp = chart["input"]
        golden = chart["artifact"]["yoginiDasha"]
        moon = next(p for p in chart["artifact"]["planets"] if p["planet"] == "moon")
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        result = compute_yogini(moon["siderealLongitude"], dt)
        assert result["birthNakshatra"] == golden["birthNakshatra"], chart["label"]
        assert result["birthYogini"] == golden["birthYogini"], chart["label"]
        assert abs(result["balanceYears"] - golden["balanceYears"]) < 1e-6, chart["label"]
        _assert_periods(result["mahadashas"], golden["mahadashas"], chart["label"])
