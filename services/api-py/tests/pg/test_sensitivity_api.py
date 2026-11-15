"""GET /v1/charts/{id}/sensitivity on the tenant session, and provenance in the artifact."""

import pytest
from test_core_api import ready_chart

pytestmark = pytest.mark.pg


def test_sensitivity_and_provenance(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    _, chart = ready_chart(api, h)
    art = api.get(f"/v1/charts/{chart}", headers=h).json()["artifact"]
    prov = art["calculationMetadata"]["provenance"]
    assert prov["ephemeris"]["provider"] in ("swiss", "astronomy")
    assert prov["nodeType"] == "mean" and prov["houseSystem"] == "whole_sign"
    r = api.get(f"/v1/charts/{chart}/sensitivity", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()["sensitivity"]
    assert {e["entity"] for e in body["entities"]} >= {"lagna", "moon", "rahu"}
    assert "dashaLord" in body and r.json()["flag_threshold_minutes"] == 10.0


def test_sensitivity_isolated_between_practices(api, auth, make_practice) -> None:
    _, ua = make_practice("A")
    _, ub = make_practice("B")
    _, chart = ready_chart(api, auth(ua))
    assert api.get(f"/v1/charts/{chart}/sensitivity", headers=auth(ub)).status_code == 404
