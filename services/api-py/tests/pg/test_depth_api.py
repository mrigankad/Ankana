"""Depth endpoints (planets, ashtakavarga, dashas) on real Postgres with RLS."""

import uuid

import pytest
from test_live_gaps import with_chart

pytestmark = pytest.mark.pg


def test_planets_endpoint(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    _, chart_id = with_chart(api, h)
    r = api.get(f"/v1/charts/{chart_id}/planets", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chart_id"] == chart_id and body["lagna"]["sign"] == "Pisces"
    rows = {p["planet"]: p for p in body["planets"]}
    assert len(rows) == 9
    for p in rows.values():
        assert p["nakshatra"] and 1 <= p["pada"] <= 4 and p["nakshatra_lord"] and p["sign_lord"]
        assert p["proof"]["nakshatra"]["inputs"] and p["proof"]["combust"]["source"]
    assert sorted(h_ for p in rows.values() for h_ in p["lord_of_houses"]) == list(range(1, 13))
    assert rows["rahu"]["avastha"] is None and rows["rahu"]["retrograde"] is True


def test_ashtakavarga_endpoint(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    _, chart_id = with_chart(api, h)
    r = api.get(f"/v1/charts/{chart_id}/ashtakavarga", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sarva_total"] == 337 and len(body["sarva"]) == 12
    assert [b["planet"] for b in body["bhinna"]] == body["planets_order"]
    for b in body["bhinna"]:
        assert len(b["bindus_by_sign"]) == 12 and sum(b["bindus_by_sign"]) == b["total"]
    assert body["thresholds"]["sarva_high"] == 28 and body["thresholds"]["sarva_low"] == 25


def test_dashas_endpoint_systems_and_asof(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    _, chart_id = with_chart(api, h)
    r = api.get(f"/v1/charts/{chart_id}/dashas", params={"asof": "2026-01-01T00:00:00Z"},
                headers=h)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["system"] == "vimshottari" and len(v["current"]) == 3
    assert v["mahadashas"][0]["children"][0]["children"]
    y = api.get(f"/v1/charts/{chart_id}/dashas", params={"system": "yogini"}, headers=h).json()
    assert y["system"] == "yogini" and len(y["current"]) == 2 and y["rule"]["total_years"] == 36
    assert api.get(f"/v1/charts/{chart_id}/dashas", params={"system": "chara"},
                   headers=h).status_code == 422


def test_depth_endpoints_are_tenant_isolated(api, auth, make_practice) -> None:
    _, ua = make_practice("A")
    _, ub = make_practice("B")
    _, chart_id = with_chart(api, auth(ua))
    for path in ("planets", "ashtakavarga", "dashas"):
        assert api.get(f"/v1/charts/{chart_id}/{path}", headers=auth(ub)).status_code == 404
        assert api.get(f"/v1/charts/{uuid.uuid4()}/{path}", headers=auth(ua)).status_code == 404
        assert api.get(f"/v1/charts/{chart_id}/{path}").status_code in (401, 403)
