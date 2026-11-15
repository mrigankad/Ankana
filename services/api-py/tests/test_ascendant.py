from nakshatra_core.ascendant import sidereal_ascendant
from nakshatra_core.ephemeris import normalize_degrees
from nakshatra_core.houses import house_of, whole_sign_houses
from nakshatra_core.time import to_utc_datetime
from nakshatra_core.zodiac import nakshatra_of, sign_of


def angular_gap(a: float, b: float) -> float:
    gap = abs(normalize_degrees(a) - normalize_degrees(b)) % 360
    return min(gap, 360 - gap)


def test_ascendant_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        inp = chart["input"]
        asc_golden = chart["artifact"]["ascendant"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        asc = sidereal_ascendant(dt, inp["latitude"], inp["longitude"])
        assert angular_gap(asc, asc_golden["siderealLongitude"]) < 0.05, chart["label"]
        assert sign_of(asc).name == asc_golden["signName"], chart["label"]
        assert nakshatra_of(asc).name == asc_golden["nakshatra"], chart["label"]
        assert nakshatra_of(asc).pada == asc_golden["pada"], chart["label"]


def test_houses_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        asc = chart["artifact"]["ascendant"]["siderealLongitude"]
        houses = whole_sign_houses(asc)
        golden_houses = chart["artifact"]["houses"]
        assert [h.sign_name for h in houses] == [g["signName"] for g in golden_houses]
        assert [h.lord for h in houses] == [g["lord"] for g in golden_houses]
        for planet in chart["artifact"]["planets"]:
            assert house_of(planet["siderealLongitude"], asc) == planet["house"], (
                f"{chart['label']} {planet['planet']}"
            )
