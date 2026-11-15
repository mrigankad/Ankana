from nakshatra_core.aspects import compute_aspects, compute_conjunctions


def _planet_signs(artifact: dict) -> dict[str, int]:
    # Preserve the artifact's planet order (matches TS object insertion order).
    return {p["planet"]: p["signIndex"] for p in artifact["planets"]}


def test_aspects_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        result = compute_aspects(_planet_signs(chart["artifact"]))
        golden = [
            {"from": a["from"], "to": a["to"], "count": a["count"]}
            for a in chart["artifact"]["aspects"]
        ]
        assert result == golden, chart["label"]


def test_conjunctions_match_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        result = compute_conjunctions(_planet_signs(chart["artifact"]))
        golden = [
            {"signIndex": c["signIndex"], "planets": c["planets"]}
            for c in chart["artifact"]["conjunctions"]
        ]
        assert result == golden, chart["label"]
