"""Core practice API on real Postgres: clients, consent, birth records, charts
(idempotent), Lal Kitab, ask, consultations, remedy plans, problem+json,
pagination and cross-practice isolation."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from ankana_ai import MockProvider
from app.db import make_engine
from app.main import create_app

pytestmark = pytest.mark.pg

BIRTH = {
    "birth_date": "1995-03-15", "birth_time": "06:42", "time_source": "certificate",
    "place_label": "Varanasi, Uttar Pradesh, India", "latitude": 25.3176,
    "longitude": 82.9739, "timezone_name": "Asia/Kolkata",
}


@pytest.fixture(autouse=True)
def _ephemeris(monkeypatch):
    """Swiss is the default; fall back to astronomy-engine where pyswisseph has no wheel."""
    try:
        import swisseph  # noqa: F401
    except ImportError:
        monkeypatch.setenv("ANKANA_EPHEMERIS", "astronomy")


@pytest.fixture()
def ai_api(app_engine, stub) -> TestClient:
    app = create_app(engine=make_engine("sqlite://"), pg_engine=app_engine, verifier=stub,
                     ai_provider=MockProvider())
    return TestClient(app)


@pytest.fixture()
def add_member(api, auth, owner_engine):
    def _add(practice_id: str, subject: str, role: str, client_id: str | None = None):
        api.get("/v1/me", headers=auth(subject))  # provisions user_account
        with owner_engine.begin() as c:
            uid = c.scalar(text("SELECT id FROM user_account WHERE subject=:s"), {"s": subject})
            c.execute(text("INSERT INTO member (practice_id,user_id,role,client_id) "
                           "VALUES (:p,:u,:r,:c)"),
                      {"p": practice_id, "u": uid, "r": role, "c": client_id})
        return subject

    def unique(practice_id: str, label: str, role: str, client_id: str | None = None):
        return _add(practice_id, f"{label}-{practice_id[:8]}", role, client_id)

    return unique


def mk_client(api, h, name="Ananya") -> str:
    r = api.post("/v1/clients", json={"display_name": name}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["client"]["id"]


def grant(api, h, cid, purpose="chart_compute", version="v1"):
    return api.post(f"/v1/clients/{cid}/consents", headers=h, json={
        "purpose": purpose, "notice_version": version, "notice_text": "I agree", "channel": "in_person"})


def ready_chart(api, h, with_ai=False) -> tuple[str, str]:
    cid = mk_client(api, h)
    assert grant(api, h, cid).status_code == 201
    if with_ai:
        assert grant(api, h, cid, "ai_assistant").status_code == 201
    assert api.post(f"/v1/clients/{cid}/birth-records", json=BIRTH, headers=h).status_code == 201
    r = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert r.status_code == 201, r.text
    return cid, r.json()["chart"]["id"]


def actions(owner_engine, pid):
    with owner_engine.connect() as c:
        return [r[0] for r in c.execute(text(
            "SELECT action FROM audit_event WHERE practice_id=:p ORDER BY created_at"), {"p": pid})]


# ------------------------------------------------------------------ clients
def test_client_crud_and_soft_delete(api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    r = api.patch(f"/v1/clients/{cid}", json={"display_name": "Ananya S", "timezone": "Asia/Kolkata"},
                  headers=h)
    assert r.status_code == 200 and r.json()["client"]["display_name"] == "Ananya S"
    assert api.patch(f"/v1/clients/{cid}", json={"display_name": None}, headers=h).status_code == 422
    assert api.get("/v1/clients", params={"q": "ananya"}, headers=h).json()["clients"]
    assert api.get("/v1/clients", params={"q": "zzz"}, headers=h).json()["clients"] == []
    assert api.delete(f"/v1/clients/{cid}", headers=h).status_code == 204
    assert api.get(f"/v1/clients/{cid}", headers=h).status_code == 404
    assert api.get("/v1/clients", headers=h).json()["clients"] == []
    assert actions(owner_engine, pid) == [
        "practice.created", "client.created", "client.updated", "client.deleted"]


def test_pagination_cursor(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    made = [mk_client(api, h, f"C{i}") for i in range(5)]
    seen, cursor = [], None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = api.get("/v1/clients", params=params, headers=h).json()
        assert len(page["clients"]) <= 2
        seen += [c["id"] for c in page["clients"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == made[::-1]
    bad = api.get("/v1/clients", params={"cursor": "garbage"}, headers=h)
    assert bad.status_code == 400 and bad.json()["code"] == "invalid_cursor"


def test_problem_json_shape(api, auth, make_practice) -> None:
    _, u = make_practice()
    r = api.get(f"/v1/clients/{uuid.uuid4()}", headers=auth(u))
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 404 and body["code"] == "not_found" and body["detail"]
    assert body["instance"].startswith("/v1/clients/")
    v = api.post("/v1/clients", json={}, headers=auth(u))
    assert v.status_code == 422 and v.json()["code"] == "validation_error"
    assert v.json()["errors"][0]["loc"]
    assert api.get("/v1/clients").json()["status"] == 401


# ----------------------------------------------------------------- consents
def test_consent_record_withdraw_and_refuse_chart(api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    api.post(f"/v1/clients/{cid}/birth-records", json=BIRTH, headers=h)
    refused = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert refused.status_code == 403 and refused.json()["code"] == "consent_required"
    assert refused.json()["purpose"] == "chart_compute"

    r1 = grant(api, h, cid)
    assert r1.status_code == 201 and r1.json()["consent"]["notice_text"] == "I agree"
    again = grant(api, h, cid)  # same version: no new evidence row
    assert again.status_code == 200 and again.json()["consent"]["id"] == r1.json()["consent"]["id"]
    assert grant(api, h, cid, version="v2").status_code == 201
    state = api.get(f"/v1/clients/{cid}/consents", headers=h).json()
    assert state["active"]["chart_compute"] is True and state["active"]["marketing"] is False
    assert len(state["consents"]) == 2
    assert api.post(f"/v1/clients/{cid}/charts", json={}, headers=h).status_code == 201

    w = api.post(f"/v1/clients/{cid}/consents/chart_compute/withdraw", headers=h)
    assert w.status_code == 200 and w.json()["active"]["chart_compute"] is False
    assert all(c["withdrawn_at"] for c in w.json()["consents"])
    assert api.post(f"/v1/clients/{cid}/consents/chart_compute/withdraw",
                    headers=h).status_code == 404
    assert api.post(f"/v1/clients/{cid}/charts", json={}, headers=h).status_code == 403
    # Re-grant after withdrawal is a new row; history is kept.
    assert grant(api, h, cid).status_code == 201
    assert len(api.get(f"/v1/clients/{cid}/consents", headers=h).json()["consents"]) == 3
    assert api.post(f"/v1/clients/{cid}/consents", headers=h,
                    json={"purpose": "bogus", "notice_version": "v1"}).status_code == 422
    acts = actions(owner_engine, pid)
    assert acts.count("consent.granted") == 3 and acts.count("consent.withdrawn") == 1


# ------------------------------------------------------------ birth records
def test_birth_records_are_versioned(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    v1 = api.post(f"/v1/clients/{cid}/birth-records", json=BIRTH, headers=h).json()["birth_record"]
    v2 = api.post(f"/v1/clients/{cid}/birth-records", headers=h,
                  json={**BIRTH, "birth_time": "06:50", "time_source": "memory"}
                  ).json()["birth_record"]
    assert (v1["version"], v2["version"]) == (1, 2) and v2["supersedes_id"] == v1["id"]
    listed = api.get(f"/v1/clients/{cid}/birth-records", headers=h).json()["birth_records"]
    assert [b["version"] for b in listed] == [2, 1]  # v1 still readable
    unknown = api.post(f"/v1/clients/{cid}/birth-records", headers=h, json={
        **BIRTH, "birth_time": "07:00", "time_source": "unknown"}).json()["birth_record"]
    assert unknown["birth_time"] is None
    assert api.post(f"/v1/clients/{cid}/birth-records", headers=h,
                    json={**BIRTH, "birth_time": None}).status_code == 422
    assert api.post(f"/v1/clients/{cid}/birth-records", headers=h,
                    json={**BIRTH, "timezone_name": "Mars/Base"}).status_code == 422
    assert api.post(f"/v1/clients/{cid}/birth-records", headers=h,
                    json={**BIRTH, "time_source": "dream"}).status_code == 422


# ------------------------------------------------------------------- charts
def test_chart_generation_is_idempotent(api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    grant(api, h, cid)
    api.post(f"/v1/clients/{cid}/birth-records", json=BIRTH, headers=h)
    first = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    second = api.post(f"/v1/clients/{cid}/charts", json={"ayanamsa": "lahiri"}, headers=h)
    assert first.status_code == 201 and second.status_code == 200
    a, b = first.json()["chart"], second.json()["chart"]
    assert a["created"] is True and b["created"] is False and a["id"] == b["id"]
    assert a["engine_version"].startswith("py-") and len(a["settings_hash"]) == 64
    # Different chart style = different settings hash = new artifact.
    other = api.post(f"/v1/clients/{cid}/charts", json={"chart_style": "south"}, headers=h)
    assert other.status_code == 201 and other.json()["chart"]["id"] != a["id"]
    assert other.json()["chart"]["settings_hash"] != a["settings_hash"]
    # New birth record version = new artifact.
    api.post(f"/v1/clients/{cid}/birth-records", headers=h,
             json={**BIRTH, "birth_time": "07:10", "time_source": "memory"})
    third = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert third.status_code == 201 and third.json()["chart"]["birth_record_id"] != a["birth_record_id"]
    with owner_engine.connect() as c:
        n = c.scalar(text("SELECT count(*) FROM chart_artifact WHERE practice_id=:p"), {"p": pid})
        charts_used = c.scalar(text(
            "SELECT value FROM usage_counter WHERE practice_id=:p AND metric='charts'"), {"p": pid})
    assert n == 3 and charts_used == 3
    assert actions(owner_engine, pid).count("chart.generated") == 3
    listed = api.get(f"/v1/clients/{cid}/charts", headers=h).json()["charts"]
    assert len(listed) == 3
    # unsupported setting surfaces as 422 problem, not 500
    bad = api.post(f"/v1/clients/{cid}/charts", json={"ayanamsa": "nope"}, headers=h)
    assert bad.status_code == 422 and bad.headers["content-type"].startswith("application/problem")


def test_idempotency_key_replay_and_conflict(api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = {**auth(u), "Idempotency-Key": "abc-123"}
    cid = mk_client(api, auth(u))
    grant(api, auth(u), cid)
    api.post(f"/v1/clients/{cid}/birth-records", json=BIRTH, headers=auth(u))
    r1 = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    r2 = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert r1.status_code == 201 and r2.status_code == 201  # replayed verbatim
    assert r1.json() == r2.json()
    clash = api.post(f"/v1/clients/{cid}/charts", json={"chart_style": "east"}, headers=h)
    assert clash.status_code == 422 and clash.json()["code"] == "idempotency_key_reuse"
    with owner_engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM chart_artifact WHERE practice_id=:p"),
                        {"p": pid}) == 1


def test_chart_views(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    _, chart = ready_chart(api, h)
    detail = api.get(f"/v1/charts/{chart}", headers=h).json()
    assert detail["artifact"]["ascendant"]["signName"] and detail["reading"]
    assert api.get(f"/v1/charts/{chart}/predictions", params={"horizon_years": 2},
                   headers=h).json()["predictions"] is not None
    assert "remedies" in api.get(f"/v1/charts/{chart}/remedies", headers=h).json()
    t = api.get(f"/v1/charts/{chart}/transits", params={"date": "2026-01-01T00:00:00Z"}, headers=h)
    assert t.status_code == 200 and t.json()["transits"]
    lk = api.get(f"/v1/charts/{chart}/lal-kitab", params={"origin": "aries_h1", "age": 30}, headers=h)
    assert lk.status_code == 200 and lk.json()["chartId"] == chart and lk.json()["lalKitab"]
    assert api.get(f"/v1/charts/{chart}/lal-kitab", params={"origin": "x"},
                   headers=h).json()["code"] == "invalid_origin"
    assert api.get(f"/v1/charts/{chart}/lal-kitab", params={"age": 999},
                   headers=h).json()["code"] == "invalid_age"
    assert api.get(f"/v1/charts/{uuid.uuid4()}", headers=h).status_code == 404
    assert api.get("/v1/charts/not-a-uuid", headers=h).status_code == 422


def test_chart_for_unknown_birth_time(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    grant(api, h, cid)
    api.post(f"/v1/clients/{cid}/birth-records", headers=h,
             json={**BIRTH, "birth_time": None, "time_source": "unknown"})
    r = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert r.status_code == 201
    art = api.get(f"/v1/charts/{r.json()['chart']['id']}", headers=h).json()["artifact"]
    assert art["calculationMetadata"]["input"]["timeUnknown"] is True


# ---------------------------------------------------------------------- ask
def test_ask_requires_consent_records_usage(ai_api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart = ready_chart(ai_api, h)  # chart_compute only
    q = {"question": "Where is my Moon placed?"}
    denied = ai_api.post(f"/v1/charts/{chart}/ask", json=q, headers=h)
    assert denied.status_code == 403 and denied.json()["code"] == "consent_required"
    assert denied.json()["purpose"] == "ai_assistant"
    grant(ai_api, h, cid, "ai_assistant")
    r = ai_api.post(f"/v1/charts/{chart}/ask", json=q, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["verification"]["status"] == "verified" and "Moon is in" in r.json()["answer"]
    assert ai_api.post(f"/v1/charts/{chart}/ask", json={"question": "x"},
                       headers=h).status_code == 422
    with owner_engine.connect() as c:
        asks = c.scalar(text(
            "SELECT value FROM usage_counter WHERE practice_id=:p AND metric='ai_asks'"), {"p": pid})
    assert asks == 1  # consent-denied and validation-failed calls are not metered
    # withdraw: blocked again
    ai_api.post(f"/v1/clients/{cid}/consents/ai_assistant/withdraw", headers=h)
    assert ai_api.post(f"/v1/charts/{chart}/ask", json=q, headers=h).status_code == 403


def test_ask_stream_and_unavailable_provider(ai_api, api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    _, chart = ready_chart(ai_api, h, with_ai=True)
    r = ai_api.post(f"/v1/charts/{chart}/ask", headers=h,
                    json={"question": "Where is my Moon?", "stream": True})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [ln.split(": ", 1)[1] for ln in r.text.splitlines() if ln.startswith("event: ")]
    assert "answer" in events and events[-1] == "done"
    # api fixture has no injected provider and no env: 503 problem
    import os

    saved = {k: os.environ.pop(k, None)
             for k in ("ANKANA_AI_PROVIDER", "ANTHROPIC_API_KEY", "OLLAMA_BASE_URL")}
    try:
        r = api.post(f"/v1/charts/{chart}/ask", json={"question": "Where is my Moon?"}, headers=h)
        assert r.status_code == 503 and r.json()["code"] == "ai_unavailable"
    finally:
        os.environ.update({k: v for k, v in saved.items() if v})


# -------------------------------------------------------------------- roles
def test_assistant_and_client_role_rules(ai_api, auth, make_practice, add_member) -> None:
    pid, owner = make_practice()
    ho = auth(owner)
    cid, chart = ready_chart(ai_api, ho, with_ai=True)
    other_cid, other_chart = ready_chart(ai_api, ho, with_ai=True)
    ha = auth(add_member(pid, "asst", "assistant"))
    hp = auth(add_member(pid, "portal", "client", cid))
    # assistant can read charts, lal-kitab and ask; cannot generate or delete
    assert ai_api.get(f"/v1/charts/{chart}", headers=ha).status_code == 200
    assert ai_api.get(f"/v1/charts/{chart}/lal-kitab", headers=ha).status_code == 200
    assert ai_api.post(f"/v1/charts/{chart}/ask", headers=ha,
                       json={"question": "Where is my Moon?"}).status_code == 200
    assert ai_api.post(f"/v1/clients/{cid}/charts", json={}, headers=ha).status_code == 403
    assert ai_api.delete(f"/v1/clients/{cid}", headers=ha).status_code == 403
    assert ai_api.post(f"/v1/clients/{cid}/remedy-plans", json={"title": "x"},
                       headers=ha).status_code == 403
    # client role: own chart only
    assert ai_api.get(f"/v1/charts/{chart}", headers=hp).status_code == 200
    assert ai_api.get(f"/v1/charts/{chart}/lal-kitab", headers=hp).status_code == 200
    assert ai_api.post(f"/v1/charts/{chart}/ask", headers=hp,
                       json={"question": "Where is my Moon?"}).status_code == 200
    assert ai_api.get(f"/v1/charts/{other_chart}", headers=hp).status_code == 404
    assert ai_api.get(f"/v1/charts/{other_chart}/lal-kitab", headers=hp).status_code == 404
    assert ai_api.post(f"/v1/charts/{other_chart}/ask", headers=hp,
                       json={"question": "Where is my Moon?"}).status_code == 404
    assert ai_api.get(f"/v1/clients/{cid}/charts", headers=hp).status_code == 200
    assert ai_api.get(f"/v1/clients/{other_cid}/charts", headers=hp).status_code == 404
    assert ai_api.post(f"/v1/clients/{cid}/charts", json={}, headers=hp).status_code == 403
    assert ai_api.post(f"/v1/clients/{cid}/consultations", json={}, headers=hp).status_code == 403
    # client can manage only their own consent
    assert grant(ai_api, hp, cid, "marketing").status_code == 201
    assert grant(ai_api, hp, other_cid, "marketing").status_code == 404


def test_cross_practice_isolation_for_new_resources(ai_api, auth, make_practice) -> None:
    _, ua = make_practice("A")
    pb, ub = make_practice("B")
    ha, hb = auth(ua), auth(ub)
    cid, chart = ready_chart(ai_api, ha, with_ai=True)
    plan = ai_api.post(f"/v1/clients/{cid}/remedy-plans", headers=ha,
                       json={"title": "P", "items": [{"title": "Lamp"}]}).json()["remedy_plan"]
    cons = ai_api.post(f"/v1/clients/{cid}/consultations", headers=ha,
                       json={"topic": "career"}).json()["consultation"]
    urls = [
        ("get", f"/v1/charts/{chart}"), ("get", f"/v1/charts/{chart}/lal-kitab"),
        ("get", f"/v1/charts/{chart}/predictions"), ("get", f"/v1/charts/{chart}/remedies"),
        ("get", f"/v1/charts/{chart}/transits"),
        ("post", f"/v1/charts/{chart}/ask"), ("get", f"/v1/clients/{cid}/charts"),
        ("post", f"/v1/clients/{cid}/charts"), ("get", f"/v1/clients/{cid}/consents"),
        ("post", f"/v1/clients/{cid}/consents/chart_compute/withdraw"),
        ("get", f"/v1/clients/{cid}/birth-records"),
        ("post", f"/v1/clients/{cid}/birth-records"),
        ("get", f"/v1/clients/{cid}/consultations"), ("get", f"/v1/consultations/{cons['id']}"),
        ("post", f"/v1/consultations/{cons['id']}/notes"),
        ("delete", f"/v1/consultations/{cons['id']}"),
        ("get", f"/v1/clients/{cid}/remedy-plans"), ("get", f"/v1/remedy-plans/{plan['id']}"),
        ("post", f"/v1/remedy-plans/{plan['id']}/start"),
        ("post", f"/v1/remedy-plans/{plan['id']}/complete"),
        ("post", f"/v1/remedy-plans/{plan['id']}/items"),
        ("post", f"/v1/remedy-plans/{plan['id']}/items/{plan['items'][0]['id']}/checkins"),
    ]
    bodies = {"post": {"question": "Where is my Moon?", "body": "n", "title": "t", **BIRTH}}
    for method, url in urls:
        kw = {"json": bodies["post"]} if method == "post" else {}
        r = getattr(ai_api, method)(url, headers=hb, **kw)
        assert r.status_code == 404, (method, url, r.status_code, r.text)
    # and B's list endpoints show nothing of A's
    assert ai_api.get("/v1/clients", headers=hb).json()["clients"] == []
    assert pb  # B exists and is otherwise functional
    assert ai_api.get(f"/v1/charts/{chart}", headers=ha).status_code == 200


# ------------------------------------------------------------ consultations
def test_consultations_and_notes(api, auth, make_practice, add_member, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart = ready_chart(api, h)
    r = api.post(f"/v1/clients/{cid}/consultations", headers=h, json={
        "topic": "career", "mode": "video", "chart_artifact_id": chart, "note": "first note"})
    assert r.status_code == 201, r.text
    cons = r.json()["consultation"]
    assert cons["chart_artifact_id"] == chart and cons["notes"][0]["body"] == "first note"
    bad = api.post(f"/v1/clients/{cid}/consultations", headers=h,
                   json={"chart_artifact_id": str(uuid.uuid4())})
    assert bad.status_code == 422
    n = api.post(f"/v1/consultations/{cons['id']}/notes", json={"body": "second"}, headers=h)
    assert n.status_code == 201
    got = api.get(f"/v1/consultations/{cons['id']}", headers=h).json()["consultation"]
    assert [x["body"] for x in got["notes"]] == ["first note", "second"]
    listed = api.get(f"/v1/clients/{cid}/consultations", headers=h).json()["consultations"]
    assert len(listed) == 1 and "notes" not in listed[0]
    # assistants see the consultation but not note bodies, and cannot write
    ha = auth(add_member(pid, "asst", "assistant"))
    seen = api.get(f"/v1/consultations/{cons['id']}", headers=ha).json()["consultation"]
    assert seen["notes"] == []
    assert api.post(f"/v1/consultations/{cons['id']}/notes", json={"body": "x"},
                    headers=ha).status_code == 403
    nid = n.json()["note"]["id"]
    assert api.delete(f"/v1/consultations/{cons['id']}/notes/{nid}", headers=h).status_code == 204
    assert len(api.get(f"/v1/consultations/{cons['id']}", headers=h
                       ).json()["consultation"]["notes"]) == 1
    assert api.delete(f"/v1/consultations/{cons['id']}", headers=h).status_code == 204
    assert api.get(f"/v1/consultations/{cons['id']}", headers=h).status_code == 404
    acts = actions(owner_engine, pid)
    assert {"consultation.created", "consultation.deleted", "consultation_note.deleted"} <= set(acts)


# ------------------------------------------------------------------ remedies
def _plan(api, h, cid, **over):
    body = {"title": "Lal Kitab 43 day", "items": [{"title": "Feed crows"}, {"title": "Lamp"}],
            **over}
    r = api.post(f"/v1/clients/{cid}/remedy-plans", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["remedy_plan"]


def test_remedy_plan_lifecycle(api, auth, make_practice, add_member, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    plan = _plan(api, h, cid)
    assert plan["cycle_days"] == 43 and plan["status"] == "draft" and len(plan["items"]) == 2
    pid1, item = plan["id"], plan["items"][0]["id"]
    # check-in before start refused
    assert api.post(f"/v1/remedy-plans/{pid1}/items/{item}/checkins", json={},
                    headers=h).status_code == 409
    started = api.post(f"/v1/remedy-plans/{pid1}/start", headers=h).json()["remedy_plan"]
    assert started["status"] == "active" and started["day_number"] == 1
    assert started["end_date"] == (
        datetime.now(tz=UTC).date() + timedelta(days=42)).isoformat()
    assert api.post(f"/v1/remedy-plans/{pid1}/start", headers=h).status_code == 409
    # one active plan per client
    second = _plan(api, h, cid, title="second")
    clash = api.post(f"/v1/remedy-plans/{second['id']}/start", headers=h)
    assert clash.status_code == 409 and clash.json()["code"] == "active_plan_exists"
    # check-ins: today, idempotent per day, out of cycle refused
    c1 = api.post(f"/v1/remedy-plans/{pid1}/items/{item}/checkins",
                  json={"note": "done"}, headers=h)
    assert c1.status_code == 200 and c1.json()["checkin"]["done"] is True
    c2 = api.post(f"/v1/remedy-plans/{pid1}/items/{item}/checkins",
                  json={"done": False}, headers=h)
    assert c2.json()["checkin"]["id"] == c1.json()["checkin"]["id"]
    assert c2.json()["checkin"]["done"] is False
    api.post(f"/v1/remedy-plans/{pid1}/items/{item}/checkins", json={}, headers=h)
    yesterday = (datetime.now(tz=UTC).date() - timedelta(days=1)).isoformat()
    assert api.post(f"/v1/remedy-plans/{pid1}/items/{item}/checkins",
                    json={"checkin_date": yesterday}, headers=h).status_code == 422
    far = (datetime.now(tz=UTC).date() + timedelta(days=60)).isoformat()
    assert api.post(f"/v1/remedy-plans/{pid1}/items/{item}/checkins",
                    json={"checkin_date": far}, headers=h).status_code == 422
    assert api.post(f"/v1/remedy-plans/{pid1}/items/{uuid.uuid4()}/checkins", json={},
                    headers=h).status_code == 404
    got = api.get(f"/v1/remedy-plans/{pid1}", headers=h).json()["remedy_plan"]
    assert {i["id"]: i["done_days"] for i in got["items"]}[item] == 1
    # complete frees the slot
    done = api.post(f"/v1/remedy-plans/{pid1}/complete", headers=h)
    assert done.json()["remedy_plan"]["status"] == "completed"
    assert api.post(f"/v1/remedy-plans/{pid1}/complete", headers=h).status_code == 409
    assert api.post(f"/v1/remedy-plans/{second['id']}/start", headers=h).status_code == 200
    assert api.post(f"/v1/remedy-plans/{second['id']}/cancel", headers=h).status_code == 200
    assert len(api.get(f"/v1/clients/{cid}/remedy-plans", headers=h).json()["remedy_plans"]) == 2
    empty = _plan(api, h, cid, title="empty", items=[])
    assert api.post(f"/v1/remedy-plans/{empty['id']}/start", headers=h).status_code == 409
    add = api.post(f"/v1/remedy-plans/{empty['id']}/items", json={"title": "Late"}, headers=h)
    assert add.status_code == 201
    custom = _plan(api, h, cid, title="short", cycle_days=7)
    assert custom["cycle_days"] == 7
    assert {"remedy_plan.created", "remedy_plan.started", "remedy_plan.completed",
            "remedy_plan.cancelled"} <= set(actions(owner_engine, pid))


def test_remedy_client_role_and_idempotent_create(api, auth, make_practice, add_member) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid = mk_client(api, h)
    other = mk_client(api, h, "Other")
    hk = {**h, "Idempotency-Key": "plan-1"}
    a = api.post(f"/v1/clients/{cid}/remedy-plans", json={"title": "P"}, headers=hk)
    b = api.post(f"/v1/clients/{cid}/remedy-plans", json={"title": "P"}, headers=hk)
    assert a.json() == b.json()
    assert len(api.get(f"/v1/clients/{cid}/remedy-plans", headers=h).json()["remedy_plans"]) == 1
    plan = _plan(api, h, other)
    api.post(f"/v1/remedy-plans/{plan['id']}/start", headers=h)
    mine = _plan(api, h, cid)
    api.post(f"/v1/remedy-plans/{mine['id']}/start", headers=h)
    hp = auth(add_member(pid, "portal", "client", cid))
    assert api.get(f"/v1/remedy-plans/{plan['id']}", headers=hp).status_code == 404
    assert api.get(f"/v1/remedy-plans/{mine['id']}", headers=hp).status_code == 200
    item = mine["items"][0]["id"]
    assert api.post(f"/v1/remedy-plans/{mine['id']}/items/{item}/checkins", json={},
                    headers=hp).status_code == 200
    after = api.get(f"/v1/remedy-plans/{mine['id']}", headers=hp).json()["remedy_plan"]
    assert after["items"][0]["done_today"] is True and after["items"][0]["done_days"] == 1
    assert api.post(f"/v1/remedy-plans/{mine['id']}/complete", headers=hp).status_code == 403
    assert api.post(f"/v1/remedy-plans/{plan['id']}/items/{plan['items'][0]['id']}/checkins",
                    json={}, headers=hp).status_code == 404


# ------------------------------------------------------------------ openapi
def test_openapi_shape(api, tmp_path) -> None:
    spec = api.get("/openapi.json").json()
    ops = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            ops.setdefault(op["operationId"], []).append((method, path))
    assert all(len(v) == 1 for v in ops.values()), {k: v for k, v in ops.items() if len(v) > 1}
    v1 = {p: i for p, i in spec["paths"].items() if p.startswith("/v1/")}
    assert "/v1/clients/{client_id}/charts" in v1 and "/v1/charts/{chart_id}/ask" in v1
    for path, item in v1.items():
        for method, op in item.items():
            assert op.get("tags"), (method, path)
            assert not op.get("deprecated"), (method, path)
    assert "Problem" in spec["components"]["schemas"]
    legacy = spec["paths"]["/api/v1/clients"]["post"]
    assert legacy["deprecated"] is True
    assert spec["paths"]["/api/v1/charts/jobs/{job_id}/lal-kitab"]["get"]["deprecated"] is True
    assert spec["paths"]["/v1/clients/{client_id}/charts"]["post"]["operationId"] == "generateChart"
    json.dumps(spec)


def test_meta_is_public(api, monkeypatch) -> None:
    monkeypatch.setenv("ANKANA_GIT_SHA", "abc123")
    r = api.get("/v1/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["license"] == "AGPL-3.0-only" and body["git_sha"] == "abc123"
    assert body["source_url"] == "https://github.com/mrigankad/Ankana"
    assert body["ephemeris"] in ("swiss", "astronomy") and body["version"]


def test_openapi_export_script_is_current() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, "scripts/export_openapi.py"], cwd=root, check=True)
    assert subprocess.run([sys.executable, "scripts/export_openapi.py", "--check"],
                          cwd=root).returncode == 0


def test_birth_record_in_a_dst_gap_is_rejected(api, auth, make_practice) -> None:
    pid, subject = make_practice("DST Practice")
    h = auth(subject, pid)
    cid = api.post("/v1/clients", json={"display_name": "Gap"}, headers=h).json()["client"]["id"]
    body = {"birth_date": "2024-03-10", "birth_time": "02:30", "time_source": "certificate",
            "place_label": "New York", "latitude": 40.7, "longitude": -74.0,
            "timezone_name": "America/New_York"}
    r = api.post(f"/v1/clients/{cid}/birth-records", json=body, headers=h)
    assert r.status_code == 422 and "does not exist" in r.json()["detail"]
    body["birth_time"] = "01:30"
    assert api.post(f"/v1/clients/{cid}/birth-records", json=body, headers=h).status_code == 201


def test_concurrent_same_idempotency_key_never_500_and_creates_one_row(
        api, auth, make_practice, owner_engine) -> None:
    import threading

    pid, u = make_practice()
    cid = mk_client(api, auth(u))
    h = {**auth(u), "Idempotency-Key": "race-1"}
    barrier = threading.Barrier(2)
    codes: list[int] = []

    def go() -> None:
        barrier.wait(timeout=10)
        codes.append(api.post(f"/v1/clients/{cid}/remedy-plans", json={"title": "Plan"},
                              headers=h).status_code)

    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert sorted(codes) in ([201, 201], [201, 409]), codes  # replay or retry-later, never 500
    with owner_engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM remedy_plan WHERE practice_id=:p"),
                        {"p": pid}) == 1


def test_client_search_treats_percent_and_underscore_literally(api, auth, make_practice) -> None:
    _, u = make_practice()
    h = auth(u)
    for name in ("Asha Rao", "100% Devotee", "a_b"):
        mk_client(api, h, name)
    names = lambda q: [c["display_name"] for c in api.get(  # noqa: E731
        "/v1/clients", params={"q": q}, headers=h).json()["clients"]]
    assert names("%") == ["100% Devotee"]
    assert names("a_b") == ["a_b"]
