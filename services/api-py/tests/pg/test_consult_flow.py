"""Consultation workflow on real Postgres with RLS: chart fact chips pinned in notes,
the pre-consult brief, session summaries with predictions, life events and the timeline,
and the optional AI draft."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from ankana_ai.providers import ProviderResponse
from app.db import make_engine
from app.main import create_app

pytestmark = pytest.mark.pg

BIRTH = {
    "birth_date": "1995-03-15", "birth_time": "06:42", "time_source": "certificate",
    "place_label": "Varanasi, Uttar Pradesh, India", "latitude": 25.3176,
    "longitude": 82.9739, "timezone_name": "Asia/Kolkata",
}


@pytest.fixture()
def add_member(api, auth, owner_engine):
    def _add(practice_id: str, label: str, role: str):
        subject = f"{label}-{practice_id[:8]}"
        api.get("/v1/me", headers=auth(subject))  # provisions user_account
        with owner_engine.begin() as c:
            uid = c.scalar(text("SELECT id FROM user_account WHERE subject=:s"), {"s": subject})
            c.execute(text("INSERT INTO member (practice_id,user_id,role) VALUES (:p,:u,:r)"),
                      {"p": practice_id, "u": uid, "r": role})
        return subject

    return _add


def mk_client(api, h, name="Ananya") -> str:
    r = api.post("/v1/clients", json={"display_name": name}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["client"]["id"]


def grant(api, h, cid, purpose="chart_compute"):
    return api.post(f"/v1/clients/{cid}/consents", headers=h, json={
        "purpose": purpose, "notice_version": "v1", "notice_text": "I agree",
        "channel": "in_person"})


@pytest.fixture(autouse=True)
def _ephemeris(monkeypatch):
    try:
        import swisseph  # noqa: F401
    except ImportError:
        monkeypatch.setenv("ANKANA_EPHEMERIS", "astronomy")


def with_chart(api, h, name="Ananya") -> tuple[str, str]:
    cid = mk_client(api, h, name)
    assert grant(api, h, cid).status_code == 201
    assert api.post(f"/v1/clients/{cid}/birth-records", json=BIRTH, headers=h).status_code == 201
    r = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert r.status_code == 201, r.text
    return cid, r.json()["chart"]["id"]


def consult(api, h, cid, **body) -> str:
    r = api.post(f"/v1/clients/{cid}/consultations", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["consultation"]["id"]


class FakeProvider:
    name = "fake"

    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        return ProviderResponse(content=[{"type": "text", "text": self.reply}],
                                stop_reason="end_turn", usage={}, model="fake-1")


def ai_client(app_engine, stub, provider) -> TestClient:
    return TestClient(create_app(engine=make_engine("sqlite://"), pg_engine=app_engine,
                                 verifier=stub, ai_provider=provider))


# ------------------------------------------------------------- pinned facts
def test_chart_facts_and_pinned_note_chips(api, auth, make_practice, owner_engine) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart = with_chart(api, h)
    r = api.get(f"/v1/clients/{cid}/chart-facts", headers=h)
    assert r.status_code == 200 and r.json()["chart_id"] == chart
    facts = r.json()["facts"]
    types = {f["type"] for f in facts}
    assert {"planet", "dasha", "yoga", "lal_kitab"} <= types
    assert any(f["ref"] == "planet:saturn" for f in facts)

    c = consult(api, h, cid, topic="Career", client_question="Should I take the Pune offer?")
    fact = {"id": "f1", "type": "planet", "ref": "planet:saturn",
            "label": "Saturn in Aquarius, house 12"}
    ok = api.post(f"/v1/consultations/{c}/notes", headers=h, json={
        "body": "Discuss {{fact:f1}} before the move.", "facts": [fact]})
    assert ok.status_code == 201, ok.text
    assert ok.json()["note"]["facts"] == [fact]
    got = api.get(f"/v1/consultations/{c}", headers=h).json()["consultation"]
    assert got["notes"][0]["facts"][0]["ref"] == "planet:saturn"
    assert got["client_question"] == "Should I take the Pune offer?"
    # marker without a fact, fact without a marker, duplicate ids, unknown type
    for bad in ({"body": "see {{fact:zz}}", "facts": []},
                {"body": "plain", "facts": [fact]},
                {"body": "{{fact:f1}}", "facts": [fact, fact]},
                {"body": "x", "facts": [{**fact, "type": "nonsense"}]}):
        assert api.post(f"/v1/consultations/{c}/notes", headers=h,
                        json=bad).status_code == 422
    # the structured facts sit next to an encrypted body
    with owner_engine.connect() as conn:
        body, stored = conn.execute(text(
            "SELECT body, facts FROM consultation_note WHERE practice_id=:p"), {"p": pid}).one()
    assert "Saturn" not in body and "Discuss" not in body
    assert stored[0]["ref"] == "planet:saturn"


# --------------------------------------------------------------------- brief
def test_brief_collects_the_prep_facts(api, auth, make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, chart = with_chart(api, h)
    now = datetime.now(tz=UTC)
    first = consult(api, h, cid, topic="Marriage timing",
                    consulted_at=(now - timedelta(days=30)).isoformat(),
                    note="Venus period favours it. {{fact:a}}",
                    note_facts=[{"id": "a", "type": "dasha", "ref": "dasha:venus",
                                 "label": "Venus dasha"}],
                    follow_up_date=(now - timedelta(days=2)).date().isoformat())
    nxt = consult(api, h, cid, topic="Career",
                  scheduled_at=(now + timedelta(hours=3)).isoformat(),
                  client_question="Is the Pune offer right?")
    plan = api.post(f"/v1/clients/{cid}/remedy-plans", headers=h, json={
        "title": "Saturn lamp", "cycle_days": 43, "items": [{"title": "Lamp, Saturdays"}]}
    ).json()["remedy_plan"]
    assert api.post(f"/v1/remedy-plans/{plan['id']}/start", headers=h, json={
        "start_date": (now - timedelta(days=3)).date().isoformat()}).status_code == 200
    item = plan["items"][0]["id"]
    api.post(f"/v1/remedy-plans/{plan['id']}/items/{item}/checkins", headers=h, json={
        "done": True, "checkin_date": (now - timedelta(days=1)).date().isoformat()})
    api.put(f"/v1/consultations/{first}/summary", headers=h, json={
        "topics": ["Marriage timing"],
        "follow_up_date": (now - timedelta(days=2)).date().isoformat(), "predictions": [
            {"statement": "Engagement likely", "window_start": "2026-01-01",
             "window_end": "2026-02-01"}]})

    b = api.get(f"/v1/clients/{cid}/brief", headers=h)
    assert b.status_code == 200, b.text
    brief = b.json()
    assert brief["chart_id"] == chart and brief["consultation_id"] == nxt
    assert brief["dasha"]["maha"] and brief["dasha"]["maha_ends"]
    assert 0 < len(brief["transits"]) <= 3
    assert brief["sade_sati"] is not None
    assert brief["stated_question"] == "Is the Pune offer right?"
    assert brief["last_consultation"]["id"] == first
    assert brief["last_consultation"]["excerpt"] == "Marriage timing"
    rem = brief["remedies"][0]
    assert rem["title"] == "Saturn lamp" and rem["day_number"] == 4
    assert rem["adherence_pct"] == 25  # 1 of 4 days done
    assert brief["follow_ups"][0]["overdue"] is True
    assert brief["open_predictions"][0]["due"] is True
    # a specific visit can be asked for
    other = api.get(f"/v1/clients/{cid}/brief?consultation_id={first}", headers=h).json()
    assert other["consultation_id"] == first and other["stated_question"] is None
    # no chart: still answers
    bare = mk_client(api, h, "No chart")
    nb = api.get(f"/v1/clients/{bare}/brief", headers=h).json()
    assert nb["chart_id"] is None and nb["dasha"] is None and nb["transits"] == []


# ------------------------------------------------- summary, predictions, timeline
def test_summary_predictions_outcomes_and_timeline(api, auth, make_practice, add_member) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, _ = with_chart(api, h)
    c = consult(api, h, cid, topic="Career")
    assert api.get(f"/v1/consultations/{c}/summary", headers=h).json()["summary"] is None
    body = {"topics": ["Career", " Career ", "Relocation"],
            "remedies_given": ["Lamp on Saturdays"], "follow_up_date": "2027-01-10",
            "predictions": [
                {"statement": "Job change", "window_start": "2026-12-01",
                 "window_end": "2027-03-01"},
                {"statement": "Move city", "window_start": None, "window_end": None}]}
    r = api.put(f"/v1/consultations/{c}/summary", headers=h, json=body)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["topics"] == ["Career", "Relocation"] and s["follow_up_date"] == "2027-01-10"
    assert [p["status"] for p in s["predictions"]] == ["pending", "pending"]
    # the follow-up date lands on the consultation
    assert api.get(f"/v1/consultations/{c}", headers=h).json()["consultation"][
        "follow_up_date"] == "2027-01-10"
    assert api.put(f"/v1/consultations/{c}/summary", headers=h, json={
        "predictions": [{"statement": "x", "window_start": "2027-02-01",
                         "window_end": "2027-01-01"}]}).status_code == 422

    job = next(p for p in s["predictions"] if p["statement"] == "Job change")
    r = api.patch(f"/v1/predictions/{job['id']}", headers=h, json={
        "status": "came_true", "outcome_note": "Joined in January"})
    assert r.status_code == 200 and r.json()["status"] == "came_true"
    assert r.json()["resolved_at"] is not None
    # editable later
    r = api.patch(f"/v1/predictions/{job['id']}", headers=h, json={"status": "unclear"})
    assert r.json()["status"] == "unclear" and r.json()["outcome_note"] == "Joined in January"
    assert api.patch(f"/v1/predictions/{job['id']}", headers=h,
                     json={"status": "bogus"}).status_code == 422
    # re-saving keeps listed predictions and drops pending ones left out of the list
    again = api.put(f"/v1/consultations/{c}/summary", headers=h, json={
        "topics": ["Career"],
        "predictions": [{"id": job["id"], "statement": "Job change",
                         "window_start": "2026-12-01", "window_end": "2027-03-01"}]}).json()
    assert [p["id"] for p in again["predictions"]] == [job["id"]]
    assert api.get(f"/v1/clients/{cid}/predictions?status=unclear",
                   headers=h).json()[0]["id"] == job["id"]

    ev = api.post(f"/v1/clients/{cid}/life-events", headers=h, json={
        "event_date": "2026-09-05", "kind": "job", "title": "Left the bank", "notes": "Resigned"})
    assert ev.status_code == 201
    eid = ev.json()["id"]
    assert api.patch(f"/v1/life-events/{eid}", headers=h, json={"title": "Left the bank job"}
                     ).json()["title"] == "Left the bank job"
    assert api.post(f"/v1/clients/{cid}/life-events", headers=h, json={
        "event_date": "2026-09-05", "kind": "nope", "title": "x"}).status_code == 422

    tl = api.get(f"/v1/clients/{cid}/timeline", headers=h).json()
    assert {"consultation", "prediction", "life_event"} <= {e["kind"] for e in tl}
    assert [e["at"] for e in tl] == sorted((e["at"] for e in tl), reverse=True)
    assert next(e for e in tl if e["kind"] == "consultation")["detail"] == "Career"
    assert api.delete(f"/v1/life-events/{eid}", headers=h).status_code == 204
    assert all(e["id"] != f"life_event:{eid}" for e in api.get(
        f"/v1/clients/{cid}/timeline", headers=h).json())

    # assistants see no clinical content
    ha = auth(add_member(pid, "asst", "assistant"))
    atl = api.get(f"/v1/clients/{cid}/timeline", headers=ha)
    assert atl.status_code == 200
    assert {e["kind"] for e in atl.json()} <= {"consultation", "remedy", "report"}
    assert all(e["detail"] is None for e in atl.json())
    for path in (f"/v1/clients/{cid}/brief", f"/v1/clients/{cid}/chart-facts",
                 f"/v1/consultations/{c}/summary", f"/v1/clients/{cid}/predictions"):
        assert api.get(path, headers=ha).status_code == 403, path


def test_consult_flow_is_tenant_isolated(api, auth, make_practice, owner_engine) -> None:
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    ha, hb = auth(ua), auth(ub)
    cid, _ = with_chart(api, ha)
    c = consult(api, ha, cid)
    pred = api.put(f"/v1/consultations/{c}/summary", headers=ha, json={
        "predictions": [{"statement": "secret"}]}).json()["predictions"][0]["id"]
    ev = api.post(f"/v1/clients/{cid}/life-events", headers=ha, json={
        "event_date": "2026-01-01", "title": "x"}).json()["id"]
    for method, path, body in (
            ("get", f"/v1/clients/{cid}/brief", None),
            ("get", f"/v1/clients/{cid}/timeline", None),
            ("get", f"/v1/clients/{cid}/predictions", None),
            ("get", f"/v1/consultations/{c}/summary", None),
            ("put", f"/v1/consultations/{c}/summary", {"topics": ["x"]}),
            ("patch", f"/v1/predictions/{pred}", {"status": "came_true"}),
            ("patch", f"/v1/life-events/{ev}", {"title": "y"}),
            ("delete", f"/v1/life-events/{ev}", None)):
        r = getattr(api, method)(path, headers=hb, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (path, r.status_code)
    with owner_engine.connect() as conn:
        for table in ("consultation_summary", "consult_prediction", "client_life_event"):
            assert conn.scalar(text(f"SELECT count(*) FROM {table} WHERE practice_id=:p"),
                               {"p": pb}) == 0
        raw = conn.scalar(text("SELECT statement FROM consult_prediction"))
    assert "secret" not in raw  # encrypted at rest


# ------------------------------------------------------------------ AI draft
def test_draft_summary_is_optional_consented_and_verified(app_engine, stub, api, auth,
                                                          make_practice) -> None:
    pid, u = make_practice()
    h = auth(u)
    cid, _ = with_chart(api, h)
    c = consult(api, h, cid, topic="Career", note="Saturn period, job change likely by spring.")

    # everything else works with no AI involved
    assert api.put(f"/v1/consultations/{c}/summary", headers=h, json={"topics": ["a"]}
                   ).status_code == 200
    reply = json.dumps({
        "topics": ["Career"], "remedies_given": [],
        "predictions": [{"statement": "Job change likely by spring",
                         "window_start": "2027-03-01", "window_end": "2027-05-31"},
                        {"statement": "Saturn in Aries blocks it", "window_start": "2027-05-31",
                         "window_end": "2027-01-01"}],
        "follow_up_date": "2027-06-10"})
    provider = FakeProvider("Here you go:\n" + reply)
    ai = ai_client(app_engine, stub, provider)
    denied = ai.post(f"/v1/consultations/{c}/summary/draft", headers=h)
    assert denied.status_code == 403 and denied.json()["code"] == "consent_required"
    assert provider.calls == 0
    assert grant(ai, h, cid, "ai_assistant").status_code == 201
    r = ai.post(f"/v1/consultations/{c}/summary/draft", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["summary"]["source"] == "ai" and out["summary"]["topics"] == ["Career"]
    assert out["summary"]["follow_up_date"] == "2027-06-10"
    assert out["summary"]["predictions"][1]["window_end"] is None  # inverted window dropped
    # the chart has Saturn in Aquarius; a false placement is flagged, not hidden
    assert out["verification"]["status"] == "mismatch"
    assert out["verification"]["mismatches"][0]["text"].startswith("Saturn in Aries")
    # the draft is not stored until saved
    assert api.get(f"/v1/consultations/{c}/summary",
                   headers=h).json()["summary"]["source"] == "manual"
    # no notes: refuse
    empty = consult(api, h, cid, topic="x")
    assert ai.post(f"/v1/consultations/{empty}/summary/draft", headers=h).status_code == 422
    # broken provider output is a 502, not a 500
    bad = ai_client(app_engine, stub, FakeProvider("no json here"))
    assert bad.post(f"/v1/consultations/{c}/summary/draft", headers=h).status_code == 502
