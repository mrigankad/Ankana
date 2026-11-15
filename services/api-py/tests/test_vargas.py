from nakshatra_core.vargas import compute_varga_charts


def test_varga_charts_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        artifact = chart["artifact"]
        longitudes = {
            p["planet"]: p["siderealLongitude"] for p in artifact["planets"]
        }
        result = compute_varga_charts(
            longitudes, artifact["ascendant"]["siderealLongitude"]
        )
        for key, golden_varga in artifact["vargas"].items():
            label = f"{chart['label']} {key}"
            assert result[key]["ascendantSign"] == golden_varga["ascendantSign"], label
            assert result[key]["planets"] == golden_varga["planets"], label
