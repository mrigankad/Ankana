"""Depth views over the golden chart artifacts: hand-checked values and invariants."""

from datetime import UTC, datetime

import pytest

from nakshatra_core.depth import (
    SARVA_HIGH,
    ashtakavarga_depth,
    baladi_avastha,
    chara_karakas,
    dashas_depth,
    planet_depth,
)

RAIGANJ = "raiganj-2003"


def _artifact(golden_charts: list[dict], label: str) -> dict:
    return next(c["artifact"] for c in golden_charts if c["label"] == label)


def test_planet_values_match_hand_check(golden_charts) -> None:
    rows = {r["planet"]: r for r in planet_depth(_artifact(golden_charts, RAIGANJ))["planets"]}
    # Moon 152.05 deg: Uttara Phalguni runs 146.667 to 160, pada 2 starts 150, lord Sun.
    moon = rows["moon"]
    assert (moon["nakshatra"], moon["pada"], moon["nakshatra_lord"]) == (
        "Uttara Phalguni", 2, "sun")
    assert moon["sign_lord"] == "mercury"
    # Virgo is an even sign, first 6 degrees are mrita (reversed order).
    assert moon["avastha"] == "mrita"
    # Sun in Leo 11.64: odd sign, second slice, kumara.
    assert rows["sun"]["avastha"] == "kumara"
    # Venus 2.9 degrees from the Sun, direct orb 10.
    venus = rows["venus"]["combust"]
    assert venus["is_combust"] and venus["orb"] == 10 and venus["separation"] < 3.5
    # Retrograde Mercury and Mars; nodes retrograde, no avastha, no karaka.
    assert rows["mercury"]["retrograde"] and rows["mars"]["retrograde"]
    assert rows["rahu"]["avastha"] is None and rows["rahu"]["karaka"] is None
    assert rows["rahu"]["combust"]["applicable"] is False


def test_planet_depth_agrees_with_artifact_for_every_golden_chart(golden_charts) -> None:
    for chart in golden_charts:
        art = chart["artifact"]
        rows = planet_depth(art)["planets"]
        for row, src in zip(rows, art["planets"], strict=True):
            assert row["planet"] == src["planet"]
            assert row["nakshatra"] == src["nakshatra"] and row["pada"] == src["pada"]
            assert row["combust"]["is_combust"] == src["combust"], chart["label"]
            assert row["house"] == src["house"]
        lords = sorted(h for r in rows for h in r["lord_of_houses"])
        assert lords == list(range(1, 13)), "every house has exactly one lord"
        # Seven distinct chara karakas, atmakaraka has the highest degree in sign.
        karakas = {r["planet"]: r["karaka"] for r in rows if r["karaka"]}
        assert len(set(karakas.values())) == 7
        ak = next(p for p, k in karakas.items() if k == "atmakaraka")
        assert ak == max((r for r in rows if r["karaka"]), key=lambda r: r["degrees_in_sign"])["planet"]


@pytest.mark.parametrize(("sign", "deg", "expected"), [
    (0, 3.0, "bala"), (0, 29.9, "mrita"), (1, 3.0, "mrita"), (1, 29.9, "bala"),
    (4, 12.0, "yuva"), (5, 18.0, "kumara"), (0, 30.0, "mrita"),
])
def test_baladi_avastha(sign: int, deg: float, expected: str) -> None:
    assert baladi_avastha(sign, deg) == expected


def test_chara_karakas_ranks_by_degree() -> None:
    planets = [{"planet": p, "degreesInSign": d} for p, d in
               [("sun", 5), ("moon", 20), ("mars", 1), ("mercury", 9), ("jupiter", 28),
                ("venus", 12), ("saturn", 15), ("rahu", 29)]]
    k = chara_karakas(planets)
    assert k["jupiter"] == "atmakaraka" and k["moon"] == "amatyakaraka"
    assert k["mars"] == "darakaraka" and "rahu" not in k


def test_ashtakavarga_depth_totals_and_contributors(golden_charts) -> None:
    for chart in golden_charts:
        out = ashtakavarga_depth(chart["artifact"])
        assert out["sarva_total"] == 337 and sum(out["sarva"]) == 337
        expected_totals = {"sun": 48, "moon": 49, "mars": 39, "mercury": 54,
                           "jupiter": 56, "venus": 52, "saturn": 39}
        for b in out["bhinna"]:
            assert b["total"] == expected_totals[b["planet"]] == sum(b["bindus_by_sign"])
            # The contributor lists are the proof: one name per bindu.
            assert [len(c) for c in b["contributors"]] == b["bindus_by_sign"]
        for sign in range(12):
            assert out["sarva"][sign] == sum(b["bindus_by_sign"][sign] for b in out["bhinna"])
        assert out["thresholds"]["sarva_high"] == SARVA_HIGH == 28


def test_vimshottari_tree_is_contiguous_and_marks_running_period(golden_charts) -> None:
    art = _artifact(golden_charts, RAIGANJ)
    when = datetime(2026, 6, 1, tzinfo=UTC)
    out = dashas_depth(art, "vimshottari", when)
    assert [n["level"] for n in out["current"]] == ["mahadasha", "antardasha", "pratyantardasha"]
    maha = out["mahadashas"]
    assert len(maha) == 9 and round(sum(m["years"] for m in maha[1:]), 3) > 0
    for prev, nxt in zip(maha, maha[1:], strict=False):
        assert prev["end"] == nxt["start"]
    for m in maha:
        assert len(m["children"]) == 9
        assert round(sum(a["years"] for a in m["children"]), 2) == round(m["years"], 2)
        for a in m["children"]:
            assert len(a["children"]) == 9
            assert round(sum(p["years"] for p in a["children"]), 2) == round(a["years"], 2)
    # Exactly one running maha, and the pratyantar contains the as-of instant.
    assert sum(1 for m in maha if m["state"] == "current") == 1
    last = out["current"][-1]
    assert datetime.fromisoformat(last["start"]) <= when < datetime.fromisoformat(last["end"])
    assert out["rule"]["total_years"] == 120 and out["rule"]["years"]["venus"] == 20


def test_yogini_tree_and_levels(golden_charts) -> None:
    art = _artifact(golden_charts, "varanasi-1990")
    out = dashas_depth(art, "yogini", datetime(2026, 6, 1, tzinfo=UTC))
    assert out["rule"]["levels"] == 2 and out["rule"]["total_years"] == 36
    assert [n["level"] for n in out["current"]] == ["mahadasha", "antardasha"]
    assert out["birth"]["lord"] == art["yoginiDasha"]["birthYogini"]
    assert out["current"][0]["name"] in out["lord_cycle"]
    assert all(m["name"] for m in out["mahadashas"])


def test_dasha_system_validated() -> None:
    with pytest.raises(ValueError):
        dashas_depth({}, "chara")
