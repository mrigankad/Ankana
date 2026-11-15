from nakshatra_core.ayanamsa import to_sidereal
from nakshatra_core.ephemeris import (
    SEVEN_BODIES,
    is_retrograde,
    mean_lunar_node,
    normalize_degrees,
    tropical_longitude,
)
from nakshatra_core.time import to_utc_datetime


def angular_gap(a: float, b: float) -> float:
    gap = abs(normalize_degrees(a) - normalize_degrees(b)) % 360
    return min(gap, 360 - gap)


def test_seven_bodies_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        inp = chart["input"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        golden = {p["planet"]: p for p in chart["artifact"]["planets"]}
        for body in SEVEN_BODIES:
            sidereal = to_sidereal(tropical_longitude(body, dt), dt)
            gap = angular_gap(sidereal, golden[body]["siderealLongitude"])
            assert gap < 0.05, f"{chart['label']} {body} off by {gap:.4f} deg"


def test_mean_node_matches_golden_rahu(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        inp = chart["input"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        golden = {p["planet"]: p for p in chart["artifact"]["planets"]}
        sidereal = to_sidereal(mean_lunar_node(dt), dt)
        gap = angular_gap(sidereal, golden["rahu"]["siderealLongitude"])
        assert gap < 0.01, f"{chart['label']} rahu off by {gap:.5f} deg"


def test_retrograde_flags_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        inp = chart["input"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        golden = {p["planet"]: p for p in chart["artifact"]["planets"]}
        for body in SEVEN_BODIES:
            assert is_retrograde(body, dt) == golden[body]["retrograde"], (
                f"{chart['label']} {body}"
            )
