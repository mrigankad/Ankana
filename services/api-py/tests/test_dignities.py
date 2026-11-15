from nakshatra_core.ayanamsa import lahiri_ayanamsa
from nakshatra_core.dignities import dignity_of, is_combust
from nakshatra_core.time import to_utc_datetime


def test_dignities_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        for planet in chart["artifact"]["planets"]:
            assert dignity_of(planet["planet"], planet["siderealLongitude"]) == (
                planet["dignity"]
            ), f"{chart['label']} {planet['planet']}"


def test_combustion_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        inp = chart["input"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        ayan = lahiri_ayanamsa(dt)
        golden = {p["planet"]: p for p in chart["artifact"]["planets"]}
        sun_tropical = golden["sun"]["siderealLongitude"] + ayan
        for name, planet in golden.items():
            if name in ("sun", "rahu", "ketu"):
                continue
            combust = is_combust(
                name,
                planet["siderealLongitude"] + ayan,
                sun_tropical,
                planet["retrograde"],
            )
            assert combust == planet["combust"], f"{chart['label']} {name}"
