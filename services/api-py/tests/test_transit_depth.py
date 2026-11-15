"""Lifetime Sade Sati, gochara with bindus and vedha, and the Jupiter plus Saturn double transit."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nakshatra_core.transit_depth import (
    GOCHARA_FAVOURABLE,
    double_transit,
    gochara_snapshot,
    sade_sati_lifetime,
)
from nakshatra_core.transits import sade_sati_active

NOW = datetime(2026, 11, 15, tzinfo=UTC)
GOLDEN = Path(__file__).parent / "golden" / "charts.json"


@pytest.fixture(scope="module")
def natal() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))[0]["artifact"]


def _d(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def test_sade_sati_lifetime_shape_and_phase_order(natal) -> None:
    r = sade_sati_lifetime(natal, NOW)
    assert r["moon_sign"] == "Virgo"
    sade = [p for p in r["periods"] if p["kind"] == "sade_sati"]
    assert len(sade) >= 3
    for p in sade:
        assert [ph["phase"] for ph in p["phases"]] == ["rising", "peak", "setting"]
        # the phases tile the period with no gaps or overlaps
        assert p["phases"][0]["starts_at"] == p["starts_at"]
        assert p["phases"][-1]["ends_at"] == p["ends_at"]
        assert p["phases"][0]["ends_at"] == p["phases"][1]["starts_at"]
        assert p["phases"][1]["ends_at"] == p["phases"][2]["starts_at"]
        assert 6.5 < (_d(p["ends_at"]) - _d(p["starts_at"])).days / 365.25 < 8.2
    # Saturn returns to the same Moon band about every 29.5 years
    gap = (_d(sade[1]["starts_at"]) - _d(sade[0]["starts_at"])).days / 365.25
    assert 27 < gap < 32
    assert [p["starts_at"] for p in r["periods"]] == sorted(p["starts_at"] for p in r["periods"])
    assert {p["kind"] for p in r["periods"]} == {"sade_sati", "dhaiya_kantaka", "dhaiya_ashtama"}
    assert "Phaladeepika" in r["proof"]


def test_sade_sati_agrees_with_the_snapshot_engine(natal) -> None:
    r = sade_sati_lifetime(natal, NOW)
    sade = [(_d(p["starts_at"]), _d(p["ends_at"])) for p in r["periods"] if p["kind"] == "sade_sati"]
    day = datetime(2004, 1, 1, tzinfo=UTC)
    while day < datetime(2050, 1, 1, tzinfo=UTC):
        inside = any(a <= day < b for a, b in sade)
        active = sade_sati_active(natal, day)
        assert inside or not active, day  # never miss a day the snapshot engine calls active
        if inside and not active:
            # only a short retrograde dip out of the band may differ, and only near an edge
            assert any(abs((day - edge).days) < 400 for a, b in sade for edge in (a, b)), day
        day += timedelta(days=97)


def test_status_current_and_next(natal) -> None:
    # Moon in Virgo: Saturn in Leo (2006-2009) is the 12th, so Sade Sati rising.
    when = datetime(2008, 3, 1, tzinfo=UTC)
    r = sade_sati_lifetime(natal, when)
    assert r["current"]["kind"] == "sade_sati" and r["current"]["phase"] == "rising"
    assert r["periods"][r["current"]["period_index"]]["status"] == "current"
    nxt = r["periods"][r["next_index"]]
    assert nxt["status"] == "upcoming" and _d(nxt["starts_at"]) > when
    quiet = sade_sati_lifetime(natal, NOW)
    assert quiet["current"]["kind"] is None and quiet["current"]["period_index"] is None
    assert quiet["periods"][quiet["next_index"]]["kind"] == "dhaiya_ashtama"
    assert quiet["periods"][quiet["next_sade_sati_index"]]["kind"] == "sade_sati"


def test_ages_are_clamped_at_birth(natal) -> None:
    first = sade_sati_lifetime(natal, NOW)["periods"][0]
    assert first["age_start"] >= 0 and first["age_end"] > first["age_start"]


def test_gochara_bindus_come_from_the_natal_ashtakavarga(natal) -> None:
    g = gochara_snapshot(natal, NOW)
    bav = {r["planet"]: r["bindusBySign"] for r in natal["strengthMetrics"]["ashtakavarga"]}
    sav = natal["strengthMetrics"]["sarvashtakavarga"]
    assert [r["planet"] for r in g["planets"]] == [
        "sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]
    for row in g["planets"]:
        assert row["sav"] == sav[row["sign_index"]]
        if row["planet"] in bav:
            assert row["bindus"] == bav[row["planet"]][row["sign_index"]]
            assert 0 <= row["bindus"] <= 8
        else:
            assert row["bindus"] is None and row["verdict"] == "not_rated"
        assert row["house_from_moon"] == (row["sign_index"] - 5) % 12 + 1


def test_gochara_verdict_rules(natal) -> None:
    g = {r["planet"]: r for r in gochara_snapshot(natal, NOW)["planets"]}
    # 15 Nov 2026 against a Virgo Moon: Venus in Virgo is the 1st (favourable, 4 bindus).
    assert g["venus"]["house_from_moon"] == 1 and g["venus"]["verdict"] == "favourable"
    assert g["venus"]["vedha_house"] == 8 and g["venus"]["vedha_by"] == []
    # Mercury in the 2nd is favourable but holds 3 bindus: muted.
    assert g["mercury"]["reason_code"] == "favourable_weak_bindus"
    assert g["mercury"]["verdict"] == "mixed"
    # Jupiter in the 12th is unfavourable, softened by 5 bindus.
    assert g["jupiter"]["reason_code"] == "unfavourable_softened"
    # Saturn in the 7th with 1 bindu.
    assert g["saturn"]["verdict"] == "unfavourable"
    for row in g.values():
        assert row["reason"]


def test_vedha_blocks_a_favourable_house_and_exemptions_hold(natal) -> None:
    found = None
    day = NOW
    for _ in range(600):
        g = gochara_snapshot(natal, day)
        for row in g["planets"]:
            if row["reason_code"] == "vedha_blocked":
                found = (row, g)
                break
        if found:
            break
        day += timedelta(days=3)
    assert found, "expected a vedha day within about five years"
    row, g = found
    good, vedha = GOCHARA_FAVOURABLE[row["planet"]]
    assert row["vedha_house"] == vedha[good.index(row["house_from_moon"])]
    assert row["verdict"] == "mixed" and row["vedha_by"]
    by_planet = {r["planet"]: r for r in g["planets"]}
    for blocker in row["vedha_by"]:
        assert by_planet[blocker]["house_from_moon"] == row["vedha_house"]
        assert {row["planet"], blocker} not in ({"sun", "saturn"}, {"moon", "mercury"})


def test_vedha_tables_are_well_formed() -> None:
    for planet, (good, vedha) in GOCHARA_FAVOURABLE.items():
        assert len(good) == len(vedha), planet
        assert all(1 <= h <= 12 for h in (*good, *vedha))


def test_gochara_what_if_date_differs(natal) -> None:
    a = gochara_snapshot(natal, NOW)
    b = gochara_snapshot(natal, datetime(2031, 3, 1, tzinfo=UTC))
    assert a["date"] != b["date"]
    sa = next(r for r in a["planets"] if r["planet"] == "saturn")
    sb = next(r for r in b["planets"] if r["planet"] == "saturn")
    assert sa["sign"] != sb["sign"]
    c = gochara_snapshot(natal, datetime(2008, 3, 1, tzinfo=UTC))
    assert c["saturn_status"] == {"kind": "sade_sati", "phase": "rising", "house_from_moon": 12}


def test_double_transit_houses_need_both_planets(natal) -> None:
    d = double_transit(natal, NOW, 24)
    assert d["months"] == 24 and d["reference"] == "lagna"
    assert d["spans"][0]["starts_at"] == d["start"] and d["spans"][-1]["ends_at"] == d["end"]
    # cross-check the first span by hand: Jupiter in Leo and Saturn in Pisces.
    first = d["spans"][0]
    assert (first["jupiter_sign"], first["saturn_sign"]) == ("Leo", "Pisces")
    lagna = natal["ascendant"]["signIndex"]
    leo, pisces = 4, 11
    expect = []
    for h in range(1, 13):
        sign = (lagna + h - 1) % 12
        j = ((sign - leo) % 12) + 1 in (1, 5, 7, 9)
        s = ((sign - pisces) % 12) + 1 in (1, 3, 7, 10)
        if j and s:
            expect.append(h)
    assert first["houses"] == expect
    assert len(d["houses"]) == 12
    assert [h["house"] for h in d["houses"] if h["active_now"]] == first["houses"]
    for h in d["houses"]:
        for w in h["windows"]:
            assert w["starts_at"] < w["ends_at"]
    assert "Rao" in d["proof"]


def test_double_transit_moon_reference_and_window_clamp(natal) -> None:
    moon = double_transit(natal, NOW, 6, "moon")
    assert moon["reference"] == "moon" and moon["reference_sign"] == "Virgo"
    assert moon["houses"][0]["sign"] == "Virgo"
    assert double_transit(natal, NOW, 99)["months"] == 36
