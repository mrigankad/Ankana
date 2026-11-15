import json
from datetime import datetime
from pathlib import Path

import pytest

from nakshatra_core.transits import compute_transit_snapshot, compute_transit_timeline

GOLDEN = Path(__file__).parent / "golden" / "transits.json"
MS_MINUTE = 60_000


@pytest.fixture(scope="module")
def golden_transits(golden_charts: list[dict]) -> dict:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    data["natal"] = next(
        c["artifact"] for c in golden_charts if c["label"] == data["natalLabel"]
    )
    return data


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_snapshot_matches_golden(golden_transits: dict) -> None:
    golden = golden_transits["snapshot"]
    result = compute_transit_snapshot(
        golden_transits["natal"], _parse(golden["date"])
    )
    for mine, gold in zip(result["planets"], golden["planets"], strict=True):
        label = gold["planet"]
        assert mine["planet"] == gold["planet"], label
        assert abs(mine["siderealLongitude"] - gold["siderealLongitude"]) < 0.05, label
        for field in (
            "signIndex", "signName", "retrograde", "houseFromLagna",
            "houseFromMoon", "nakshatra",
        ):
            assert mine[field] == gold[field], f"{label} {field}"
    assert result["sadeSati"] == golden["sadeSati"]
    assert result["jupiterSummary"] == golden["jupiterSummary"]
    assert result["nodesSummary"] == golden["nodesSummary"]


def test_timeline_matches_golden(golden_transits: dict) -> None:
    spec = golden_transits["timeline"]
    events = compute_transit_timeline(_parse(spec["from"]), spec["years"])
    golden_events = spec["events"]
    assert [(e["planet"], e["kind"], e["detail"]) for e in events] == [
        (e["planet"], e["kind"], e["detail"]) for e in golden_events
    ]
    for mine, gold in zip(events, golden_events, strict=True):
        gap_ms = abs(
            _parse(mine["date"]).timestamp() - _parse(gold["date"]).timestamp()
        ) * 1000
        assert gap_ms <= 90 * MS_MINUTE, f"{gold['detail']} off by {gap_ms / 60000:.1f} min"


# ------------------------------------------------ sade sati shortcut (performance fix)
def test_sade_sati_shortcut_matches_the_full_snapshot(golden_charts):
    from datetime import UTC, datetime, timedelta

    from nakshatra_core.transits import compute_transit_snapshot, sade_sati_active

    start = datetime(2020, 1, 1, tzinfo=UTC)
    seen = set()
    for chart in golden_charts[:4]:
        artifact = chart["artifact"] if "artifact" in chart else chart
        if "planets" not in artifact:
            continue
        for i in range(0, 365 * 12, 97):  # a dozen years, all three phases show up
            when = start + timedelta(days=i)
            full = compute_transit_snapshot(artifact, when)["sadeSati"]["active"]
            assert sade_sati_active(artifact, when) is full
            seen.add(full)
    assert seen == {True, False}


def test_planet_positions_are_cached_per_instant():
    from datetime import UTC, datetime

    from nakshatra_core.ephemeris import is_retrograde, tropical_longitude

    when = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)
    tropical_longitude.cache_clear()
    first = tropical_longitude("saturn", when)
    hits = tropical_longitude.cache_info().hits
    assert tropical_longitude("saturn", when) == first
    assert tropical_longitude.cache_info().hits == hits + 1
    assert is_retrograde("mars", when) is is_retrograde("mars", when)
