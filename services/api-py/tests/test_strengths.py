from nakshatra_core.ephemeris import normalize_degrees
from nakshatra_core.shadbala import compute_shadbala
from nakshatra_core.vimshopaka import compute_vimshopaka


def test_shadbala_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        artifact = chart["artifact"]
        planets = {p["planet"]: p for p in artifact["planets"]}
        longitudes = {name: p["siderealLongitude"] for name, p in planets.items()}
        results = compute_shadbala(
            longitudes,
            artifact["ascendant"]["siderealLongitude"],
            normalize_degrees(longitudes["moon"] - longitudes["sun"]),
            {name: p["retrograde"] for name, p in planets.items()},
            planets["sun"]["house"] >= 7,
        )
        golden = artifact["strengthMetrics"]["shadbala"]
        for mine, gold in zip(results, golden, strict=True):
            label = f"{chart['label']} {gold['planet']}"
            assert mine["planet"] == gold["planet"], label
            for field in (
                "sthana", "dig", "kala", "cheshta", "naisargika", "drik",
                "totalVirupas", "totalRupas", "requiredRupas", "ratio",
            ):
                assert abs(mine[field] - gold[field]) < 1e-6, f"{label} {field}"


def test_vimshopaka_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        artifact = chart["artifact"]
        longitudes = {
            p["planet"]: p["siderealLongitude"] for p in artifact["planets"]
        }
        results = compute_vimshopaka(longitudes)
        golden = artifact["strengthMetrics"]["vimshopaka"]
        for mine, gold in zip(results, golden, strict=True):
            assert mine["planet"] == gold["planet"], chart["label"]
            assert abs(mine["score"] - gold["score"]) < 1e-9, (
                f"{chart['label']} {gold['planet']}"
            )
