"""Whole-artifact parity: compute the full artifact from raw birth input and
compare every discrete field against the TS golden artifact."""

from nakshatra_core.chart import compute_vedic_chart_artifact


def test_full_artifact_parity(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        golden = chart["artifact"]
        mine = compute_vedic_chart_artifact(chart["input"])
        label = chart["label"]

        assert mine["ascendant"]["signName"] == golden["ascendant"]["signName"], label
        assert mine["ascendant"]["nakshatra"] == golden["ascendant"]["nakshatra"], label
        assert mine["ascendant"]["pada"] == golden["ascendant"]["pada"], label

        for mp, gp in zip(mine["planets"], golden["planets"], strict=True):
            for field in (
                "planet", "signIndex", "signName", "nakshatra", "pada",
                "house", "dignity", "retrograde", "combust",
            ):
                assert mp[field] == gp[field], f"{label} {gp['planet']} {field}"

        assert [
            {k: h[k] for k in ("number", "signIndex", "signName", "lord", "occupants")}
            for h in mine["houses"]
        ] == golden["houses"], label
        assert mine["panchang"] == golden["panchang"], label
        assert mine["vargas"] == golden["vargas"], label
        assert mine["vimshottari"]["birthLord"] == golden["vimshottari"]["birthLord"], label
        assert mine["yoginiDasha"]["birthYogini"] == golden["yoginiDasha"]["birthYogini"], label
        assert [
            (y["key"], y["present"]) for y in mine["yogas"]
        ] == [(y["key"], y["present"]) for y in golden["yogas"]], label
        assert mine["aspects"] == golden["aspects"], label
        assert mine["conjunctions"] == golden["conjunctions"], label
        assert mine["strengthMetrics"]["sarvashtakavarga"] == (
            golden["strengthMetrics"]["sarvashtakavarga"]
        ), label
