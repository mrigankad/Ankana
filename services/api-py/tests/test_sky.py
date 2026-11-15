"""Sky events, the natal transit timeline and the daily panchang."""

from datetime import UTC, datetime

import pytest

from nakshatra_core.sky import chart_transit_timeline, daily_panchang, sky_events

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _natal(moon: int, lagna: int = 0) -> dict:
    return {"ascendant": {"signIndex": lagna}, "planets": [{"planet": "moon", "signIndex": moon}]}


def test_lunations_and_ingresses_in_a_known_window() -> None:
    events = sky_events(datetime(2026, 11, 8, tzinfo=UTC), 20)
    kinds = {(e["planet"], e["kind"]) for e in events}
    assert ("moon", "amavasya") in kinds and ("moon", "purnima") in kinds
    new = next(e for e in events if e["kind"] == "amavasya")
    full = next(e for e in events if e["kind"] == "purnima")
    assert new["at"].date().isoformat() == "2026-11-09"
    assert full["at"].date().isoformat() == "2026-11-24"
    sun = next(e for e in events if e["planet"] == "sun" and e["kind"] == "ingress")
    assert sun["sign_index"] == 7  # Scorpio, Vrishchika sankranti on 16 Nov
    assert [e["at"] for e in events] == sorted(e["at"] for e in events)


def test_stations_are_reported_for_planets_that_have_them() -> None:
    events = sky_events(datetime(2026, 11, 8, tzinfo=UTC), 10)
    stations = {(e["planet"], e["kind"]) for e in events if "station" in e["kind"]}
    assert ("mercury", "direct-station") in stations
    assert ("venus", "direct-station") in stations


def test_timeline_houses_and_drishti_are_relative_to_the_natal_chart() -> None:
    tl = chart_transit_timeline(_natal(moon=4, lagna=11), NOW, 12)
    assert tl["natal"] == {"lagna_sign": "Pisces", "moon_sign": "Leo"}
    assert tl["events"] == sorted(tl["events"], key=lambda e: (e["date"], e["planet"], e["kind"]))
    jupiter = next(e for e in tl["events"] if e["planet"] == "jupiter" and e["kind"] == "ingress")
    assert jupiter["sign"] == "Cancer"
    assert jupiter["house_from_lagna"] == 5  # Pisces to Cancer, inclusive
    assert jupiter["house_from_moon"] == 12
    # Jupiter in Cancer casts its 9th drishti onto Pisces: the lagna.
    asp = next(e for e in tl["events"] if e["planet"] == "jupiter" and e["kind"] == "aspect")
    assert asp["target"] == "lagna" and asp["aspect"] == 9
    # A planet entering the Moon's sign is a conjunction.
    assert any(e["kind"] == "conjunction" and e["target"] == "moon" for e in tl["events"])


def test_sade_sati_phases_follow_saturn_from_the_natal_moon() -> None:
    tl = chart_transit_timeline(_natal(moon=0), NOW, 12)  # Moon in Aries, Saturn in Pisces
    assert tl["sade_sati"]["active_now"] and tl["sade_sati"]["phase_now"] == "rising"
    first, second = tl["sade_sati"]["phases"][:2]
    assert first["phase"] == "rising" and first["starts_at"] is None
    assert second["phase"] == "peak" and second["starts_at"] == first["ends_at"]
    ends = [e for e in tl["events"] if e["kind"] == "sade_sati"]
    assert ends and ends[0]["phase"] == "peak" and ends[0]["planet"] == "saturn"


def test_no_sade_sati_for_a_moon_far_from_saturn() -> None:
    tl = chart_transit_timeline(_natal(moon=4), NOW, 12)
    assert tl["sade_sati"] == {"active_now": False, "phase_now": None, "phases": []}
    assert not [e for e in tl["events"] if e["kind"] == "sade_sati"]


def test_months_are_clamped() -> None:
    assert chart_transit_timeline(_natal(4), NOW, 99)["months"] == 24
    assert chart_transit_timeline(_natal(4), NOW, 0)["months"] == 1


def test_daily_panchang_for_delhi() -> None:
    day = datetime(2026, 11, 14, 6, 30, tzinfo=UTC)
    p = daily_panchang(day, 28.6139, 77.209, (day.weekday() + 1) % 7)
    assert p["vara"] == "Shanivara"
    assert p["tithi"]["name"] == "Panchami" and p["tithi"]["paksha"] == "shukla"
    assert p["nakshatra"]["name"] == "Purva Ashadha"
    sunrise = datetime.fromisoformat(p["sunrise"].replace("Z", "+00:00"))
    sunset = datetime.fromisoformat(p["sunset"].replace("Z", "+00:00"))
    seg = (sunset - sunrise) / 8
    start = datetime.fromisoformat(p["rahu_kaal"]["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(p["rahu_kaal"]["end"].replace("Z", "+00:00"))
    assert abs((start - sunrise) - seg * 2) < seg / 100  # Saturday: third eighth
    assert abs((end - start) - seg) < seg / 100
    assert p["tithi"]["ends_at"] > p["sunrise"]


@pytest.mark.parametrize("weekday,segment", [(0, 8), (1, 2), (2, 7), (3, 5), (4, 6), (5, 4), (6, 3)])
def test_rahu_kaal_segment_by_weekday(weekday: int, segment: int) -> None:
    day = datetime(2026, 11, 14, 6, 30, tzinfo=UTC)
    p = daily_panchang(day, 28.6139, 77.209, weekday)
    sunrise = datetime.fromisoformat(p["sunrise"].replace("Z", "+00:00"))
    sunset = datetime.fromisoformat(p["sunset"].replace("Z", "+00:00"))
    start = datetime.fromisoformat(p["rahu_kaal"]["start"].replace("Z", "+00:00"))
    seg = (sunset - sunrise) / 8
    assert abs((start - sunrise) - seg * (segment - 1)) < seg / 100
