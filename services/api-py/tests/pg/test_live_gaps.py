"""Live-data gaps: client tags and enriched list rows, the Today feed, the transit
timeline, client reports and plan usage, on real Postgres with RLS."""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.tenancy.rls import APP_ROLE

pytestmark = pytest.mark.pg

BIRTH = {
    "birth_date": "1995-03-15", "birth_time": "06:42", "time_source": "certificate",
    "place_label": "Varanasi, Uttar Pradesh, India", "latitude": 25.3176,
    "longitude": 82.9739, "timezone_name": "Asia/Kolkata",
}


@pytest.fixture(autouse=True)
def _ephemeris(monkeypatch):
    try:
        import swisseph  # noqa: F401
    except ImportError:
        monkeypatch.setenv("ANKANA_EPHEMERIS", "astronomy")


def mk_client(api, h, name="Ananya") -> str:
    r = api.post("/v1/clients", json={"display_name": name}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["client"]["id"]


def with_chart(api, h, name="Ananya", **birth) -> tuple[str, str]:
    cid = mk_client(api, h, name)
    assert api.post(f"/v1/clients/{cid}/consents", headers=h, json={
        "purpose": "chart_compute", "notice_version": "v1", "notice_text": "ok",
        "channel": "in_person"}).status_code == 201
    assert api.post(f"/v1/clients/{cid}/birth-records", json={**BIRTH, **birth},
                    headers=h).status_code == 201
    r = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert r.status_code == 201, r.text
    return cid, r.json()["chart"]["id"]


def day(offset: int = 0) -> str:
    return (datetime.now(tz=UTC) + timedelta(days=offset)).date().isoformat()


# -------------------------------------------------------------------- tags
def test_tags_set_normalise_and_replace(api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    assert api.get(f"/v1/clients/{cid}/tags", headers=h).json() == {"tags": []}
    r = api.put(f"/v1/clients/{cid}/tags", headers=h,
                json={"tags": ["Lal Kitab", "  lal   kitab ", "Matching"]})
    assert r.status_code == 200 and r.json()["tags"] == ["Lal Kitab", "Matching"]
    r = api.put(f"/v1/clients/{cid}/tags", headers=h, json={"tags": ["Matching", "Rectify"]})
    assert sorted(r.json()["tags"]) == ["Matching", "Rectify"]
    assert api.put(f"/v1/clients/{cid}/tags", headers=h, json={"tags": [""]}).status_code == 422
    assert api.put(f"/v1/clients/{cid}/tags", headers=h,
                   json={"tags": ["x" * 41]}).status_code == 422
    assert api.put(f"/v1/clients/{cid}/tags", headers=h,
                   json={"tags": [str(i) for i in range(21)]}).status_code == 422
    counts = api.get("/v1/client-tags", headers=h).json()["tags"]
    assert {t["tag"]: t["count"] for t in counts} == {"Matching": 1, "Rectify": 1}
    assert api.put(f"/v1/clients/{cid}/tags", headers=h, json={"tags": []}).json() == {"tags": []}
    with owner_engine.connect() as c:
        assert "client.tags_updated" in [r[0] for r in c.execute(text(
            "SELECT action FROM audit_event WHERE practice_id=:p"), {"p": pid})]


def test_tags_are_tenant_isolated_and_rls_forced(api, auth, make_practice, owner_engine) -> None:
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    ha, hb = auth(ua), auth(ub)
    ca = mk_client(api, ha, "Alpha")
    cb = mk_client(api, hb, "Beta")
    api.put(f"/v1/clients/{ca}/tags", headers=ha, json={"tags": ["Secret"]})
    api.put(f"/v1/clients/{cb}/tags", headers=hb, json={"tags": ["Other"]})
    assert api.put(f"/v1/clients/{ca}/tags", headers=hb, json={"tags": ["Hijack"]}).status_code == 404
    assert api.get(f"/v1/clients/{ca}/tags", headers=hb).status_code == 404
    assert [t["tag"] for t in api.get("/v1/client-tags", headers=hb).json()["tags"]] == ["Other"]
    assert api.get("/v1/clients", params={"tag": "Secret"}, headers=hb).json()["clients"] == []
    with owner_engine.connect() as c:
        row = c.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                             "WHERE relname='client_tag'")).one()
        assert tuple(row) == (True, True)
        assert c.scalar(text("SELECT count(*) FROM pg_policies WHERE tablename='client_tag'")) == 1
        assert c.scalar(text("SELECT has_table_privilege(:r, 'client_tag', 'SELECT')"),
                        {"r": APP_ROLE})


# ------------------------------------------------------------ enriched list
def test_list_rows_carry_chart_dasha_visit_followup_and_tags(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart_id = with_chart(api, h)
    api.put(f"/v1/clients/{cid}/tags", headers=h, json={"tags": ["Lal Kitab"]})
    past = (datetime.now(tz=UTC) - timedelta(days=9)).isoformat()
    assert api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "consulted_at": past, "follow_up_date": day(3), "topic": "Career"}).status_code == 201
    booked = (datetime.now(tz=UTC) + timedelta(days=2)).isoformat()
    assert api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "scheduled_at": booked}).status_code == 201
    bare = mk_client(api, h, "No Chart")

    page = api.get("/v1/clients", headers=h).json()
    rows = {r["display_name"]: r for r in page["clients"]}
    r = rows["Ananya"]
    assert r["latest_chart_id"] == chart_id
    assert r["lagna_sign"] == "Pisces" and 0 <= r["lagna_degree"] < 30
    assert r["current_dasha"]["maha"] and r["current_dasha"]["antar"]
    assert r["tags"] == ["Lal Kitab"]
    assert r["last_consultation_at"].startswith(day(-9))
    assert r["next_consultation_at"].startswith(day(2))
    assert r["next_follow_up"] == day(3)
    assert r["needs_rectify"] is False
    empty = rows["No Chart"]
    assert empty["id"] == bare and empty["lagna_sign"] is None and empty["current_dasha"] is None
    assert empty["next_follow_up"] is None and empty["tags"] == []
    assert page["facets"]["total"] == 2 and page["facets"]["follow_up_due"] == 1
    assert page["facets"]["tags"] == [{"tag": "Lal Kitab", "count": 1}]


def test_follow_up_closes_once_a_later_consultation_happens(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "consulted_at": (datetime.now(tz=UTC) - timedelta(days=10)).isoformat(),
        "follow_up_date": day(-4)})
    row = api.get("/v1/clients", headers=h).json()["clients"][0]
    assert row["next_follow_up"] == day(-4)  # overdue and still open
    assert api.get("/v1/clients", params={"follow_up_due": True}, headers=h).json()["clients"]
    api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "consulted_at": (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()})
    row = api.get("/v1/clients", headers=h).json()["clients"][0]
    assert row["next_follow_up"] is None
    assert api.get("/v1/clients", params={"follow_up_due": True}, headers=h).json()["clients"] == []


def test_filters_by_tag_rectify_and_follow_up(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    a = mk_client(api, h, "Asha")
    b = mk_client(api, h, "Bhavna")
    c = mk_client(api, h, "Chetan")
    api.put(f"/v1/clients/{a}/tags", headers=h, json={"tags": ["Matching"]})
    api.put(f"/v1/clients/{b}/tags", headers=h, json={"tags": ["matching", "Lal Kitab"]})
    for cid, source in ((b, "approximate"), (c, "certificate")):
        api.post(f"/v1/clients/{cid}/birth-records", headers=h,
                 json={**BIRTH, "time_source": source})
    api.post(f"/v1/clients/{c}/consultations", headers=h, json={"follow_up_date": day(5)})

    def names(**p):
        rows = api.get("/v1/clients", params=p, headers=h).json()["clients"]
        return sorted(r["display_name"] for r in rows)

    assert names(tag="MATCHING") == ["Asha", "Bhavna"]  # case-insensitive
    assert names(tag="Lal Kitab") == ["Bhavna"]
    assert names(needs_rectify=True) == ["Bhavna"]
    assert names(needs_rectify=False) == ["Asha", "Chetan"]
    assert names(follow_up_due=True) == ["Chetan"]
    assert names(tag="Matching", needs_rectify=True) == ["Bhavna"]
    facets = api.get("/v1/clients", headers=h).json()["facets"]
    assert facets["needs_rectify"] == 1 and facets["follow_up_due"] == 1
    assert {t["tag"] for t in facets["tags"]} == {"Matching", "matching", "Lal Kitab"}


def test_unknown_birth_time_needs_rectify_and_sorting_with_cursor(api, auth,
                                                                   make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    ids = {n: mk_client(api, h, n) for n in ("Dev", "Anil", "Chitra", "Bela")}
    api.post(f"/v1/clients/{ids['Dev']}/birth-records", headers=h,
             json={**BIRTH, "time_source": "unknown", "birth_time": None})
    assert [r["display_name"] for r in api.get(
        "/v1/clients", params={"needs_rectify": True}, headers=h).json()["clients"]] == ["Dev"]
    # name sort pages through every client exactly once
    seen, cursor = [], None
    while True:
        params = {"sort": "name", "limit": 3, **({"cursor": cursor} if cursor else {})}
        page = api.get("/v1/clients", params=params, headers=h).json()
        seen += [r["display_name"] for r in page["clients"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == ["Anil", "Bela", "Chitra", "Dev"]
    assert api.get("/v1/clients", params={"cursor": "garbage"}, headers=h).status_code == 400
    assert api.get("/v1/clients", params={"sort": "bogus"}, headers=h).status_code == 422
    # follow-up sort: earliest open follow-up first, none last
    api.post(f"/v1/clients/{ids['Chitra']}/consultations", headers=h,
             json={"follow_up_date": day(2)})
    api.post(f"/v1/clients/{ids['Bela']}/consultations", headers=h,
             json={"follow_up_date": day(1)})
    order = [r["display_name"] for r in api.get(
        "/v1/clients", params={"sort": "follow_up"}, headers=h).json()["clients"]]
    assert order[:2] == ["Bela", "Chitra"] and set(order[2:]) == {"Anil", "Dev"}
    # last consultation sort: most recent first, never visited last
    api.post(f"/v1/clients/{ids['Anil']}/consultations", headers=h, json={
        "consulted_at": (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()})
    order = [r["display_name"] for r in api.get(
        "/v1/clients", params={"sort": "last_consult"}, headers=h).json()["clients"]]
    assert set(order[:2]) == {"Bela", "Chitra"} and order[2:] == ["Anil", "Dev"]


# ------------------------------------------------------------------- today
def test_today_lists_booked_consultations_in_practice_time(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart_id = with_chart(api, h)
    api.put("/v1/notification-settings", headers=h, json={"timezone": "Asia/Kolkata"})
    local = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    at = local.replace(hour=11, minute=30, second=0, microsecond=0)
    r = api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "scheduled_at": at.isoformat(), "topic": "Career question"})
    assert r.status_code == 201 and r.json()["consultation"]["scheduled_at"]
    api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "scheduled_at": (at + timedelta(days=1)).isoformat(), "topic": "Not today"})
    t = api.get("/v1/today", headers=h)
    assert t.status_code == 200, t.text
    body = t.json()
    assert body["date"] == local.date().isoformat() and body["timezone"] == "Asia/Kolkata"
    assert [c["topic"] for c in body["consultations"]] == ["Career question"]
    c = body["consultations"][0]
    assert c["client_name"] == "Ananya" and c["chart_id"] == chart_id
    assert c["lagna_sign"] == "Pisces" and c["status"] == "prepared"
    assert set(c["houses"]) <= {str(i) for i in range(1, 13)} and c["houses"]


def test_today_flags_missing_chart_and_unsure_birth_time(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    bare = mk_client(api, h, "Bare")
    unsure, _ = with_chart(api, h, "Unsure", time_source="approximate")
    now = datetime.now(tz=UTC).isoformat()
    for cid in (bare, unsure):
        api.post(f"/v1/clients/{cid}/consultations", headers=h, json={"consulted_at": now})
    body = api.get("/v1/today", headers=h).json()
    status = {c["client_name"]: c["status"] for c in body["consultations"]}
    assert status == {"Bare": "no_chart", "Unsure": "needs_birth_time"}


def test_today_needs_you_summary(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h, "Due Soon")
    api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "consulted_at": (datetime.now(tz=UTC) - timedelta(days=8)).isoformat(),
        "follow_up_date": day(-2), "topic": "Review"})
    body = api.get("/v1/today", headers=h).json()
    n = body["needs_you"]
    assert n["followups"] == 1 and n["total"] >= 1
    item = next(i for i in n["items"] if i["kind"] == "followup")
    assert item["client_name"] == "Due Soon" and item["days"] == 2 and item["detail"] == "Review"


def test_today_panchang_sky_and_clients_touched(api, auth, make_practice, monkeypatch) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart_id = with_chart(api, h)
    artifact = api.get(f"/v1/charts/{chart_id}", headers=h).json()["artifact"]
    moon_sign = next(p for p in artifact["planets"] if p["planet"] == "moon")["signIndex"]
    asc = artifact["ascendant"]["signIndex"]
    other = next(i for i in range(12) if i not in (moon_sign, asc))
    when = datetime.now(tz=UTC) + timedelta(days=2)
    fake = [
        {"at": when, "planet": "saturn", "kind": "ingress", "sign_index": moon_sign},
        {"at": when + timedelta(days=1), "planet": "mars", "kind": "ingress", "sign_index": asc},
        {"at": when + timedelta(days=2), "planet": "venus", "kind": "ingress", "sign_index": other},
        {"at": when + timedelta(days=30), "planet": "sun", "kind": "ingress", "sign_index": other},
    ]
    monkeypatch.setattr("app.v1.today.sky_events", lambda start, days: fake)
    body = api.get("/v1/today", headers=h).json()
    pan = body["panchang"]
    assert pan["tithi"]["name"] and pan["nakshatra"]["name"] and pan["vara"].endswith("vara")
    assert pan["rahu_kaal_start"] < pan["rahu_kaal_end"] and pan["sunrise"] < pan["sunset"]
    assert body["place"]["source"] == "timezone_default" and body["place"]["label"] == "New Delhi"
    touched = {(e["planet"], e["clients_touched"]) for e in body["sky"]}
    assert touched == {("saturn", 1), ("mars", 1), ("venus", 0)}  # day 32 is beyond the week
    assert body["sky"][0]["client_ids"] == [cid]
    assert body["next_ingress"]["planet"] == "saturn"


def test_today_place_and_unset_zone(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    r = api.put("/v1/notification-settings", headers=h, json={"timezone": "America/New_York"})
    assert r.status_code == 200
    body = api.get("/v1/today", headers=h).json()
    assert body["panchang"] is None and body["place"]["source"] == "unset"
    r = api.put("/v1/practice/location", headers=h, json={
        "place_label": "New York, USA", "latitude": 40.7128, "longitude": -74.006})
    assert r.status_code == 200 and r.json()["source"] == "practice"
    body = api.get("/v1/today", headers=h).json()
    assert body["panchang"]["tithi"]["name"] and body["place"]["label"] == "New York, USA"
    assert api.put("/v1/practice/location", headers=h, json={
        "place_label": "x", "latitude": 99, "longitude": 0}).status_code == 422


def test_today_is_per_practice(api, auth, make_practice) -> None:
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    ha, hb = auth(ua), auth(ub)
    ca = mk_client(api, ha, "Only A")
    api.post(f"/v1/clients/{ca}/consultations", headers=ha, json={
        "consulted_at": datetime.now(tz=UTC).isoformat()})
    assert len(api.get("/v1/today", headers=ha).json()["consultations"]) == 1
    assert api.get("/v1/today", headers=hb).json()["consultations"] == []
    assert api.get("/v1/today").status_code == 401


# ---------------------------------------------------------- transit timeline
def test_transit_timeline_endpoint(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    _, chart_id = with_chart(api, h)
    r = api.get(f"/v1/charts/{chart_id}/transits/timeline", headers=h)
    assert r.status_code == 200, r.text
    tl = r.json()
    assert tl["chart_id"] == chart_id and tl["months"] == 12
    assert tl["natal"]["lagna_sign"] == "Pisces" and tl["natal"]["moon_sign"] == "Leo"
    kinds = {e["kind"] for e in tl["events"]}
    assert {"ingress", "aspect"} <= kinds
    for e in tl["events"]:
        assert 1 <= e["house_from_lagna"] <= 12 and 1 <= e["house_from_moon"] <= 12
    dates = [e["date"] for e in tl["events"]]
    assert dates == sorted(dates)
    assert tl["sade_sati"]["active_now"] is False
    short = api.get(f"/v1/charts/{chart_id}/transits/timeline", params={"months": 1},
                    headers=h).json()
    assert short["months"] == 1 and len(short["events"]) < len(tl["events"])
    assert api.get(f"/v1/charts/{chart_id}/transits/timeline", params={"months": 0},
                   headers=h).status_code == 422
    assert api.get(f"/v1/charts/{chart_id}/transits/timeline", params={"months": 25},
                   headers=h).status_code == 422


def test_transit_timeline_is_tenant_isolated(api, auth, make_practice) -> None:
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    _, chart_id = with_chart(api, auth(ua))
    assert api.get(f"/v1/charts/{chart_id}/transits/timeline", headers=auth(ub)).status_code == 404
    assert api.get(f"/v1/charts/{uuid.uuid4()}/transits/timeline",
                   headers=auth(ua)).status_code == 404


# ----------------------------------------------------------- client reports
def test_client_reports_list(api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart_id = with_chart(api, h)
    other, other_chart = with_chart(api, h, "Other")
    assert api.get(f"/v1/clients/{cid}/reports", headers=h).json() == {
        "reports": [], "next_cursor": None}
    with owner_engine.begin() as c:
        for status, chart in (("done", chart_id), ("queued", chart_id), ("failed", other_chart)):
            c.execute(text(
                "INSERT INTO report (practice_id, chart_artifact_id, template, template_version, "
                "language, options, status, size_bytes) VALUES (:p, :c, 'standard', '1', 'hi', "
                "CAST(:o AS jsonb), :s, 2048)"),
                {"p": pid, "c": chart, "s": status, "o": '{"sections": ["summary", "dasha"]}'})
    page = api.get(f"/v1/clients/{cid}/reports", headers=h).json()
    assert len(page["reports"]) == 2
    assert {r["status"] for r in page["reports"]} == {"done", "queued"}
    r0 = page["reports"][0]
    assert r0["chart_id"] == chart_id and r0["language"] == "hi"
    assert r0["sections"] == ["summary", "dasha"] and r0["template"] == "standard"
    assert [r["status"] for r in api.get(f"/v1/clients/{other}/reports",
                                         headers=h).json()["reports"]] == ["failed"]
    one = api.get(f"/v1/clients/{cid}/reports", params={"limit": 1}, headers=h).json()
    assert len(one["reports"]) == 1 and one["next_cursor"]
    assert api.get(f"/v1/clients/{uuid.uuid4()}/reports", headers=h).status_code == 404


def test_client_reports_are_tenant_isolated(api, auth, make_practice) -> None:
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    cid, _ = with_chart(api, auth(ua))
    assert api.get(f"/v1/clients/{cid}/reports", headers=auth(ub)).status_code == 404


# -------------------------------------------------------------------- usage
def test_usage_is_unlimited_when_billing_is_off(api, auth, make_practice, monkeypatch) -> None:
    monkeypatch.delenv("ANKANA_BILLING", raising=False)
    pid, u = make_practice()
    h = auth(u)
    with_chart(api, h)
    r = api.get("/v1/usage", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["billing"] is False and body["unlimited"] is True and body["plan"] is None
    assert body["period"] == datetime.now(tz=UTC).strftime("%Y-%m")
    meters = {m["metric"]: m for m in body["meters"]}
    assert meters["charts"]["used"] == 1 and meters["charts"]["limit"] is None
    assert meters["clients"]["used"] == 1 and meters["reports"]["used"] == 0


def test_usage_reports_plan_limits_when_billing_is_on(api, auth, make_practice,
                                                      monkeypatch) -> None:
    monkeypatch.setenv("ANKANA_BILLING", "on")
    pid, u = make_practice()
    h = auth(u)
    mk_client(api, h)
    body = api.get("/v1/usage", headers=h).json()
    assert body["billing"] is True and body["plan"] == "free" and body["unlimited"] is False
    meters = {m["metric"]: m for m in body["meters"]}
    assert meters["clients"] == {"metric": "clients", "used": 1, "limit": 5, "period": "current"}
    assert meters["reports"]["limit"] == 0 and meters["ai_asks"]["limit"] == 10
    assert "charts" not in meters


def test_usage_is_per_practice_and_needs_a_session(api, auth, make_practice, monkeypatch) -> None:
    monkeypatch.delenv("ANKANA_BILLING", raising=False)
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    mk_client(api, auth(ua))
    body = api.get("/v1/usage", headers=auth(ub)).json()
    assert {m["metric"]: m["used"] for m in body["meters"]}["clients"] == 0
    assert api.get("/v1/usage").status_code == 401


# ----------------------------------------------------------- consultations
def test_consultation_scheduled_at_round_trip(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    at = (datetime.now(tz=UTC) + timedelta(days=3)).replace(microsecond=0)
    r = api.post(f"/v1/clients/{cid}/consultations", headers=h,
                 json={"scheduled_at": at.isoformat()})
    c = r.json()["consultation"]
    assert datetime.fromisoformat(c["scheduled_at"]) == at
    assert datetime.fromisoformat(c["consulted_at"]) == at  # defaults to the booking
    listed = api.get(f"/v1/clients/{cid}/consultations", headers=h).json()["consultations"]
    assert datetime.fromisoformat(listed[0]["scheduled_at"]) == at
    plain = api.post(f"/v1/clients/{cid}/consultations", headers=h, json={}).json()["consultation"]
    assert plain["scheduled_at"] is None


# ------------------------------------------------------ transit depth endpoints
def test_sade_sati_gochara_and_double_transit_endpoints(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    _, chart_id = with_chart(api, h)
    ss = api.get(f"/v1/charts/{chart_id}/transits/sade-sati", headers=h)
    assert ss.status_code == 200, ss.text
    body = ss.json()
    assert body["chart_id"] == chart_id and body["moon_sign"] == "Leo"
    assert {p["kind"] for p in body["periods"]} == {"sade_sati", "dhaiya_kantaka", "dhaiya_ashtama"}
    assert body["periods"] == sorted(body["periods"], key=lambda p: p["starts_at"])
    assert body["proof"]
    past = api.get(f"/v1/charts/{chart_id}/transits/sade-sati", headers=h,
                   params={"as_of": "2000-01-01T00:00:00Z"}).json()
    assert past["periods"][past["next_index"]]["status"] == "upcoming"

    g = api.get(f"/v1/charts/{chart_id}/transits/gochara", headers=h,
                params={"date": "2026-11-15T00:00:00Z"})
    assert g.status_code == 200, g.text
    gb = g.json()
    assert gb["date"].startswith("2026-11-15") and len(gb["planets"]) == 9
    assert sum(gb["tally"].values()) == 7
    assert all(r["verdict"] in {"favourable", "mixed", "unfavourable", "not_rated"} for r in gb["planets"])
    other = api.get(f"/v1/charts/{chart_id}/transits/gochara", headers=h,
                    params={"date": "2031-03-01T00:00:00Z"}).json()
    assert other["date"].startswith("2031-03-01")
    assert api.get(f"/v1/charts/{chart_id}/transits/gochara", headers=h,
                   params={"date": "1500-01-01T00:00:00Z"}).status_code == 400

    d = api.get(f"/v1/charts/{chart_id}/transits/double", headers=h)
    assert d.status_code == 200, d.text
    db = d.json()
    assert db["months"] == 24 and len(db["houses"]) == 12 and db["reference"] == "lagna"
    assert api.get(f"/v1/charts/{chart_id}/transits/double", headers=h,
                   params={"reference": "moon", "months": 12}).json()["reference"] == "moon"
    assert api.get(f"/v1/charts/{chart_id}/transits/double", headers=h,
                   params={"months": 37}).status_code == 422


def test_transit_depth_is_tenant_isolated_and_authenticated(api, auth, make_practice) -> None:
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    _, chart_id = with_chart(api, auth(ua))
    for path in ("sade-sati", "gochara", "double"):
        url = f"/v1/charts/{chart_id}/transits/{path}"
        assert api.get(url, headers=auth(ub)).status_code == 404
        assert api.get(url).status_code == 401
        assert api.get(f"/v1/charts/{uuid.uuid4()}/transits/{path}", headers=auth(ua)).status_code == 404
