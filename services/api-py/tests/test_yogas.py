from nakshatra_core.yogas import detect_yogas


def _input_from(artifact: dict) -> dict:
    planets = {p["planet"]: p for p in artifact["planets"]}
    return {
        "longitudes": {n: p["siderealLongitude"] for n, p in planets.items()},
        "signs": {n: p["signIndex"] for n, p in planets.items()},
        "ascendantSign": artifact["ascendant"]["signIndex"],
        "dignities": {n: p["dignity"] for n, p in planets.items()},
        "houseLords": [h["lord"] for h in artifact["houses"]],
    }


def test_yogas_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        results = detect_yogas(_input_from(chart["artifact"]))
        golden = chart["artifact"]["yogas"]
        assert len(results) == len(golden), chart["label"]
        for mine, gold in zip(results, golden, strict=True):
            label = f"{chart['label']} {gold['key']}"
            assert mine["key"] == gold["key"], label
            assert mine["name"] == gold["name"], label
            assert mine["present"] == gold["present"], label
            assert mine["category"] == gold["category"], label
            assert mine["evidence"] == gold["evidence"], label


def test_contradictory_yogas_never_cofire(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        results = {r["key"]: r for r in detect_yogas(_input_from(chart["artifact"]))}
        # Kemadruma (lonely Moon) excludes the flanking lunar yogas.
        if results["kemadruma"]["present"]:
            assert not results["sunapha"]["present"], chart["label"]
            assert not results["anapha"]["present"], chart["label"]
            assert not results["durudhara"]["present"], chart["label"]
