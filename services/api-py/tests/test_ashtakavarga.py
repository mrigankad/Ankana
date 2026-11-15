from nakshatra_core.ashtakavarga import compute_ashtakavarga, compute_sarvashtakavarga


def test_ashtakavarga_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        artifact = chart["artifact"]
        signs = {p["planet"]: p["signIndex"] for p in artifact["planets"]}
        results = compute_ashtakavarga(signs, artifact["ascendant"]["signIndex"])
        golden = artifact["strengthMetrics"]["ashtakavarga"]
        assert [
            {
                "planet": r["planet"],
                "bindusBySign": r["bindusBySign"],
                "totalBindus": r["totalBindus"],
            }
            for r in results
        ] == golden, chart["label"]
        assert compute_sarvashtakavarga(results) == (
            artifact["strengthMetrics"]["sarvashtakavarga"]
        ), chart["label"]
