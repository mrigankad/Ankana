"""Parity of ankana_lalkitab with the TS package, via tests/fixtures/lal_kitab_parity.json.

Regenerate the fixture (TS is the source of truth):
  cd packages/lal-kitab
  LK_PARITY_OUT=../../services/api-py/tests/fixtures/lal_kitab_parity.json \
    npx vitest run parity-export
"""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ankana_lalkitab import (
    data_coverage,
    lal_kitab_report,
    lk_chart,
    varshphal,
    year_of_life,
)
from ankana_lalkitab.data import planet_house_entries
from app.db import make_engine
from app.main import create_app

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "lal_kitab_parity.json").read_text(encoding="utf-8")
)
_CAMEL = re.compile(r"([A-Z])")


def snake(obj):
    """camelCase keys -> snake_case, recursively (data keys are already snake_case)."""
    if isinstance(obj, dict):
        return {_CAMEL.sub(lambda m: "_" + m.group(1).lower(), k): snake(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [snake(v) for v in obj]
    return obj


def parse_now(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: c["id"])
def test_report_matches_ts(case):
    got = lal_kitab_report(
        case["artifact"], origin=case.get("origin"), age=case.get("age"), now=parse_now(case["now"])
    ).model_dump(by_alias=True, mode="json")
    assert got == snake(case["report"])


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: c["id"])
def test_varshphal_ages_match_ts(case):
    chart = lk_chart(case["artifact"], case.get("origin"))
    expected = snake(case["varshphal_ages"])
    for exp in expected:
        got = varshphal(chart, exp["age"]).model_dump(by_alias=True, mode="json")
        assert got == exp


def test_year_of_life_matches_ts():
    for row in FIXTURE["year_of_life"]:
        assert year_of_life(row["birth"], parse_now(row["now"])) == row["year"]


def test_fixture_exercises_the_rules():
    reports = [c["report"] for c in FIXTURE["cases"]]
    assert any(r["rin"] for r in reports)
    assert any(r["masnui"] for r in reports)
    assert any(p["status"] == "dormant" for r in reports for p in r["sleepingPlanets"])
    assert any(u["kind"] == "house_entry" for r in reports for u in r["remedies"]["upay"])


def test_data_coverage_reads_single_source():
    cov = data_coverage()
    assert cov["planet_house"]["total"] == len(planet_house_entries) >= 108


def test_api_route_matches_report():
    client = TestClient(create_app(engine=make_engine("sqlite://")))
    cid = client.post("/api/v1/clients", json={"fullName": "T"}).json()["client"]["id"]
    rec = client.post(
        f"/api/v1/clients/{cid}/birth-records",
        json={
            "birthDate": "1995-03-15",
            "birthTime": "06:42",
            "timezoneName": "Asia/Kolkata",
            "placeLabel": "Varanasi, Uttar Pradesh, India",
            "latitude": 25.3176,
            "longitude": 82.9739,
        },
    ).json()["birthRecord"]
    job = client.post(
        "/api/v1/charts/generate", json={"clientId": cid, "birthRecordId": rec["id"]}
    ).json()["job"]["id"]

    for url in (f"/v1/charts/{job}/lal-kitab", f"/api/v1/charts/jobs/{job}/lal-kitab"):
        res = client.get(url, params={"origin": "aries_h1", "age": 30})
        assert res.status_code == 200
        body = res.json()
        assert body["jobId"] == job
        assert body["lalKitab"]["origin"] == "aries_h1"
        assert body["lalKitab"]["varshphal"]["age"] == 30
    assert client.get(f"/v1/charts/{job}/lal-kitab", params={"origin": "x"}).status_code == 400
    assert client.get(f"/v1/charts/{job}/lal-kitab", params={"age": 101}).status_code == 400
    assert client.get(f"/v1/charts/{job}/lal-kitab", params={"age": "a"}).status_code == 400
    assert client.get("/v1/charts/nope/lal-kitab").status_code == 404
