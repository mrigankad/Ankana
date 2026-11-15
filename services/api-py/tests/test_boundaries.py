"""Boundary-case hardening: behavior at sign/nakshatra/pada edges must be
deterministic, and charts with bodies near a boundary must carry warnings."""

from nakshatra_core.boundaries import boundary_warnings
from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_core.zodiac import NAKSHATRA_SPAN, nakshatra_of, sign_of

RAIGANJ = {
    "birthDate": "2003-08-29",
    "birthTime": "12:22",
    "timezoneName": "Asia/Kolkata",
    "latitude": 25.6167,
    "longitude": 88.1233,
}


def test_sign_boundary_is_half_open() -> None:
    # Exactly on a boundary belongs to the next sign; epsilon below stays.
    assert sign_of(30.0).name == "Taurus"
    assert sign_of(29.999999).name == "Aries"
    assert sign_of(0.0).name == "Aries"
    assert sign_of(359.999999).name == "Pisces"


def test_nakshatra_and_pada_boundaries_are_half_open() -> None:
    span = NAKSHATRA_SPAN
    assert nakshatra_of(span).name == "Bharani"
    assert nakshatra_of(span - 1e-9).name == "Ashwini"
    pada_span = span / 4
    assert nakshatra_of(pada_span - 1e-9).pada == 1
    assert nakshatra_of(pada_span).pada == 2


def test_boundary_warnings_flag_close_bodies() -> None:
    # Moon 0.05 deg inside Taurus: sign boundary warning expected.
    warnings = boundary_warnings({"moon": 30.05}, ascendant_longitude=15.0)
    kinds = {(w["body"], w["kind"]) for w in warnings}
    assert ("moon", "sign") in kinds
    # Every warning carries the distance.
    assert all(0 <= w["distanceDeg"] <= 0.1 for w in warnings)


def test_boundary_warnings_quiet_when_far() -> None:
    warnings = boundary_warnings({"sun": 15.0}, ascendant_longitude=45.0)
    assert [w for w in warnings if w["body"] == "sun"] == []


def test_artifact_carries_boundary_warnings_field() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    assert "boundaryWarnings" in artifact
    # Raiganj: Rahu at 0.41 deg Taurus and Ketu at 0.41 deg Scorpio are within
    # 0.5 deg of a sign boundary but outside the 0.1 deg threshold; the chart
    # should still list any sub-threshold hits deterministically.
    for warning in artifact["boundaryWarnings"]:
        assert set(warning) == {"body", "kind", "distanceDeg"}
