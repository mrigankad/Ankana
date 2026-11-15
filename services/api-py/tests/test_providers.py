import pytest

from nakshatra_core.providers import NotSupportedError, get_provider
from nakshatra_core.time import to_utc_datetime

DT = to_utc_datetime("1995-03-15", "06:42", "Asia/Kolkata")
LAT, LON = 25.3176, 82.9739


def test_default_provider_is_swiss(monkeypatch) -> None:
    pytest.importorskip("swisseph")
    monkeypatch.delenv("ANKANA_EPHEMERIS", raising=False)
    assert get_provider().name == "swiss"


def test_env_selects_provider(monkeypatch) -> None:
    pytest.importorskip("swisseph")
    monkeypatch.setenv("ANKANA_EPHEMERIS", "swiss")
    assert get_provider().name == "swiss"


def test_unknown_provider_rejected() -> None:
    with pytest.raises(ValueError):
        get_provider("jhora")


def test_astronomy_rejects_unsupported_options() -> None:
    p = get_provider("astronomy")
    with pytest.raises(NotSupportedError):
        p.ayanamsa(DT, "raman")
    with pytest.raises(NotSupportedError):
        p.lunar_node(DT, "true")
    with pytest.raises(NotSupportedError):
        p.sunrise_sunset(DT, LAT, LON, "hindu")


def test_swiss_ayanamsas_distinct_and_sane() -> None:
    pytest.importorskip("swisseph")
    p = get_provider("swiss")
    values = {n: p.ayanamsa(DT, n) for n in p.ayanamsas}
    assert 23.7 < values["lahiri"] < 23.9
    assert len(set(round(v, 3) for v in values.values())) == 4
    assert abs(values["kp"] - values["lahiri"]) < 0.1


def test_swiss_true_node_close_to_mean_node() -> None:
    pytest.importorskip("swisseph")
    p = get_provider("swiss")
    gap = abs((p.lunar_node(DT, "true") - p.lunar_node(DT, "mean") + 180) % 360 - 180)
    assert 0 < gap < 2


def test_swiss_hindu_sunrise_later_than_standard() -> None:
    pytest.importorskip("swisseph")
    p = get_provider("swiss")
    hindu, _ = p.sunrise_sunset(DT, LAT, LON, "hindu")
    standard, _ = p.sunrise_sunset(DT, LAT, LON, "standard")
    assert 60 < (hindu - standard).total_seconds() < 600


def test_whole_sign_cusps_start_at_sign_boundaries() -> None:
    for name in ("astronomy", "swiss"):
        if name == "swiss":
            pytest.importorskip("swisseph")
        cusps = get_provider(name).house_cusps(DT, LAT, LON, "whole_sign")
        assert len(cusps) == 12
        assert all(abs(c % 30) < 1e-6 or abs(c % 30 - 30) < 1e-6 for c in cusps)
