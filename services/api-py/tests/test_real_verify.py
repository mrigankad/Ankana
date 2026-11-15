"""Real-chart harness: case files are valid, parsing works, the script runs end to end."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import verify_real_chart as v  # noqa: E402

from nakshatra_core.providers import get_provider  # noqa: E402
from nakshatra_core.sensitivity import sensitivity_report  # noqa: E402

PUBLIC = sorted((ROOT / "tests" / "real" / "public").glob("*.json"))


def test_public_cases_valid_and_pending() -> None:
    assert len(PUBLIC) >= 5
    for p in PUBLIC:
        case = json.loads(p.read_text(encoding="utf-8"))
        assert v.validate_case(case) == [], p.name
        assert case["consent"] in ("public-domain", "anonymised", "consented")
        assert case["source"]["citation"]


@pytest.mark.parametrize("text,expected", [
    ("Sc 14°58'", 210 + 14 + 58 / 60),
    ("14:58:12 Scorpio", 210 + 14 + 58 / 60 + 12 / 3600),
    (224.9667, 224.9667),
    ("Vi 2°03'", 150 + 2 + 3 / 60),
])
def test_parse_longitude(text, expected) -> None:
    assert v.parse_longitude(text)[0] == pytest.approx(expected, abs=1e-3)


def _entered(case: dict, comp: dict) -> None:
    case["observed"] = {
        "status": "entered",
        "planets": {n: v.deg_to_dms(comp["lon"][n]) for n in v.BODIES},
        "ascendant": v.deg_to_dms(comp["lon"]["lagna"]),
    }


def test_pass_and_fail_with_cause() -> None:
    case = json.loads(PUBLIC[0].read_text(encoding="utf-8"))
    provider = get_provider()
    _entered(case, v.compute_case(provider, case))
    status, _, _ = v.run(case, provider, 1.0, False, False)
    assert status == 0
    # an observation made one hour away fails and is diagnosed as a time problem
    _entered(case, v.compute_case(provider, case, shift_minutes=60))
    status, payload, _ = v.run(case, provider, 1.0, False, False)
    assert status == 1 and any("BIRTH TIME" in c for c in payload["causes"])


def test_pending_case_exits_3() -> None:
    case = json.loads(PUBLIC[0].read_text(encoding="utf-8"))
    status, _, lines = v.run(case, get_provider(), 1.0, False, False)
    assert status == 3 and lines


def test_sensitivity_flags_lagna_edge() -> None:
    inp = {"birthDate": "2003-08-29", "birthTime": "12:22", "timezoneName": "Asia/Kolkata",
           "latitude": 25.6185, "longitude": 88.1256}
    rep = sensitivity_report(inp, get_provider())
    assert {e["entity"] for e in rep["entities"]} >= {"lagna", "moon", "ketu"}
    assert any(f["entity"] == "lagna" and f["feature"] == "pada" for f in rep["flags"])


def test_provenance_in_artifact() -> None:
    from nakshatra_core.chart import compute_vedic_chart_artifact

    art = compute_vedic_chart_artifact({
        "birthDate": "1990-01-01", "birthTime": "10:30", "timezoneName": "Asia/Kolkata",
        "latitude": 25.3176, "longitude": 82.9739})
    prov = art["calculationMetadata"]["provenance"]
    assert prov["ephemeris"]["provider"] in ("swiss", "astronomy")
    assert prov["ephemeris"]["libraryVersion"]
    assert prov["nodeType"] == "mean" and prov["houseSystem"] == "whole_sign"
    assert prov["ayanamsa"]["name"] == "lahiri"
