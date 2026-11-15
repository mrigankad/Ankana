"""POST /v1/charts/preview: lagna preview for the intake form (no persistence)."""

import pytest

BODY = {"birth_date": "1995-03-15", "birth_time": "06:42:00", "latitude": 25.3176,
        "longitude": 82.9739, "timezone_name": "Asia/Kolkata"}


@pytest.fixture()
def staff(make_practice, auth):
    practice_id, subject = make_practice()
    return auth(subject, practice_id)


def test_preview_returns_lagna_and_window(api, staff):
    r = api.post("/v1/charts/preview", json=BODY, headers=staff)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["lagna"]["sign"] == "Pisces"
    assert 10 < d["lagna"]["degrees_in_sign"] < 11
    assert d["moon"]["nakshatra"] == "Magha"
    s = d["sensitivity"]
    # Lagna moves about 1 degree per 4 minutes: Pisces holds for roughly 40 min each side
    assert 1 <= s["d9_minutes_before"] + s["d9_minutes_after"] <= 30
    assert s["d1_minutes_before"] > s["d9_minutes_before"] - 1
    assert d["houses"]["1"] == ["Su"]


def test_preview_does_not_persist(api, staff):
    api.post("/v1/charts/preview", json=BODY, headers=staff)
    assert api.get("/v1/clients", headers=staff).json()["clients"] == []


def test_preview_requires_auth(api):
    assert api.post("/v1/charts/preview", json=BODY).status_code == 401


def test_preview_validates_input(api, staff):
    r = api.post("/v1/charts/preview", json={**BODY, "latitude": 200}, headers=staff)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")


def test_preview_is_rate_limited(api, staff):
    codes = [api.post("/v1/charts/preview", json=BODY, headers=staff).status_code
             for _ in range(45)]
    assert codes[0] == 200 and codes[-1] == 429
