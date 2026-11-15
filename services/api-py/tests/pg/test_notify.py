"""Reminders on real Postgres: due computation across zones, idempotent scheduling,
missed-day policies, consent gating, sending, public links, API, RLS."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from app import worker
from app.jobs import queue
from app.notify import channels, links, scheduler
from app.notify.policy import evaluate_plan
from app.tenancy.models import RemedyPlan
from app.tenancy.session import tenant_session

NOW = datetime(2026, 11, 4, 4, 0, tzinfo=UTC)  # 09:30 IST on 4 Nov
TODAY = date(2026, 11, 4)


@pytest.fixture(autouse=True)
def clean(owner_engine):
    with owner_engine.begin() as c:
        c.execute(text("DELETE FROM job"))
    console = channels.ConsoleChannel("email")
    channels.set_channel("email", console)
    channels.set_channel("whatsapp", channels.ConsoleChannel("whatsapp"))
    yield console
    channels.set_channel("email", None)
    channels.set_channel("whatsapp", None)


def jobs(engine, kind="notify_send"):
    with engine.begin() as c:
        return c.scalar(text("SELECT count(*) FROM job WHERE kind=:k"), {"k": kind})


def mk(api, auth, make_practice, owner_engine, *, policy="restart", start=TODAY - timedelta(days=3),
       tz="Asia/Kolkata", email_opt=True, consent=True, language=None, cycle=43):
    pid, subject = make_practice()
    h = auth(subject, pid)
    body = {"display_name": "Asha Rao", "contact_email": "asha@example.test",
            "contact_phone": "+910000000000"}
    if language:
        body["preferred_language"] = language
    cid = api.post("/v1/clients", json=body, headers=h).json()["client"]["id"]
    if consent:
        assert api.post(f"/v1/clients/{cid}/consents", headers=h, json={
            "purpose": "reminders", "notice_version": "v1"}).status_code == 201
    r = api.put(f"/v1/clients/{cid}/notification-prefs", headers=h, json={
        "email_opt_in": email_opt})
    assert r.status_code == 200, r.text
    assert api.put("/v1/notification-settings", headers=h, json={"timezone": tz}).status_code == 200
    plan = api.post(f"/v1/clients/{cid}/remedy-plans", headers=h, json={
        "title": "Saturn remedy", "cycle_days": cycle, "missed_day_policy": policy,
        "items": [{"title": "Feed crows"}, {"title": "Lamp"}]}).json()["remedy_plan"]
    r = api.post(f"/v1/remedy-plans/{plan['id']}/start", headers=h,
                 json={"start_date": start.isoformat()})
    assert r.status_code == 200, r.text
    return {"pid": pid, "h": h, "cid": cid, "plan": plan,
            "items": [i["id"] for i in plan["items"]]}


def checkin(owner_engine, w, day, items=None):
    with owner_engine.begin() as c:
        for item in items or w["items"]:
            c.execute(text(
                "INSERT INTO remedy_checkin (practice_id,item_id,checkin_date,done) "
                "VALUES (:p,:i,:d,true) ON CONFLICT (item_id,checkin_date) DO UPDATE "
                "SET done=true"), {"p": w["pid"], "i": item, "d": day})


def run(engine, w, now=NOW, tz="Asia/Kolkata", hour=8):
    with tenant_session(engine, w["pid"]) as db:
        return scheduler.process_practice(db, tz, hour, now)


def plan_row(engine, w):
    with tenant_session(engine, w["pid"]) as db:
        p = db.get(RemedyPlan, uuid.UUID(w["plan"]["id"]))
        return {k: getattr(p, k) for k in ("start_date", "cycle_days", "missed_days",
                                           "restart_count", "extended_days",
                                           "evaluated_through", "last_missed_date")}


def outbox(api, w, **q):
    return api.get("/v1/notifications", headers=w["h"], params=q).json()["notifications"]


# -------------------------------------------------------------- due / idempotency
def test_due_reminder_created_once_per_plan_day_channel(api, auth, make_practice, owner_engine,
                                                        app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    s1 = run(app_engine, w)
    assert s1.by_kind == {"remedy_due": 1} and jobs(owner_engine) == 1
    s2 = run(app_engine, w)
    assert s2.created == 0 and jobs(owner_engine) == 1
    out = outbox(api, w)
    assert len(out) == 1 and out[0]["kind"] == "remedy_due" and out[0]["channel"] == "email"
    assert out[0]["local_date"] == "2026-11-04" and out[0]["status"] == "pending"
    assert "day 1 of 43" in out[0]["subject"].lower() or "day 1 of 43" in out[0]["body"].lower()
    assert "/v1/public/checkin/" in out[0]["body"] and "/v1/public/stop/" in out[0]["body"]
    assert "not medical" in out[0]["body"]
    # Next local day is a new key.
    run(app_engine, w, NOW + timedelta(days=1))
    assert jobs(owner_engine) == 2


def test_two_channels_two_rows_and_no_prefs_means_nothing(api, auth, make_practice,
                                                          owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    api.put(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"],
            json={"whatsapp_opt_in": True})
    assert run(app_engine, w).created == 2
    assert {n["channel"] for n in outbox(api, w)} == {"email", "whatsapp"}
    w2 = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY,
            email_opt=False)
    assert run(app_engine, w2).created == 0


def test_consent_gates_and_withdrawal_stops_pending_send(api, auth, make_practice, owner_engine,
                                                         app_engine, clean):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY, consent=False)
    assert run(app_engine, w).created == 0  # opted in but no 'reminders' consent
    assert api.post(f"/v1/clients/{w['cid']}/consents", headers=w["h"], json={
        "purpose": "marketing", "notice_version": "v1"}).status_code == 201
    assert run(app_engine, w).created == 0  # marketing does not unlock reminders
    api.post(f"/v1/clients/{w['cid']}/consents", headers=w["h"],
             json={"purpose": "reminders", "notice_version": "v1"})
    assert run(app_engine, w).created == 1
    api.post(f"/v1/clients/{w['cid']}/consents/reminders/withdraw", headers=w["h"])
    reg = worker.default_registry(app_engine, None)
    assert worker.process_one(app_engine, reg, "t")
    assert clean.sent == []
    assert outbox(api, w)[0]["status"] == "skipped"
    assert outbox(api, w)[0]["skip_reason"] == "not_eligible"


def test_due_follows_practice_timezone(api, auth, make_practice, owner_engine, app_engine):
    # 20:00Z on 4 Nov is already 5 Nov in India but still 4 Nov in New York.
    late = datetime(2026, 11, 4, 20, 0, tzinfo=UTC)
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=date(2026, 11, 5),
           tz="Asia/Kolkata")
    s = run(app_engine, w, late, "Asia/Kolkata", 8)
    assert s.created == 1  # IST 01:30, 5 Nov: day 1, scheduled for 08:00 IST
    assert outbox(api, w)[0]["local_date"] == "2026-11-05"
    w2 = mk(api, auth, make_practice, owner_engine, policy="warn", start=date(2026, 11, 5),
            tz="America/New_York")
    assert run(app_engine, w2, late, "America/New_York", 8).created == 0  # plan not started yet
    assert run(app_engine, w2, late + timedelta(hours=12), "America/New_York", 8).created == 1


def test_scheduled_for_uses_dst_correct_instant(api, auth, make_practice, owner_engine,
                                                app_engine):
    ny = "America/New_York"
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=date(2026, 3, 8), tz=ny)
    run(app_engine, w, datetime(2026, 3, 8, 5, 5, tzinfo=UTC), ny, 8)  # 00:05 EST, day of change
    n = outbox(api, w)[0]
    assert n["local_date"] == "2026-03-08"
    assert datetime.fromisoformat(n["scheduled_for"]) == datetime(2026, 3, 8, 12, 0, tzinfo=UTC)


def test_quiet_hours_skip_stale_message(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    late = datetime(2026, 11, 4, 16, 30, tzinfo=UTC)  # 22:00 IST: quiet
    run(app_engine, w, late)
    n = outbox(api, w)[0]
    assert (n["status"], n["skip_reason"]) == ("skipped", "quiet_hours")
    assert jobs(owner_engine) == 0
    # A client with no quiet window gets it.
    api.put(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"],
            json={"quiet_start": "00:00", "quiet_end": "00:00"})
    run(app_engine, w, late + timedelta(days=1) - timedelta(hours=14))  # next day, daytime
    assert any(x["status"] == "pending" for x in outbox(api, w))


def test_done_today_suppresses_reminder(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    checkin(owner_engine, w, TODAY)
    assert run(app_engine, w).created == 0
    w2 = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    checkin(owner_engine, w2, TODAY, w2["items"][:1])  # only one of two items
    assert run(app_engine, w2).created == 1


def test_ending_soon_at_day_40_of_43_and_plan_complete(api, auth, make_practice, owner_engine,
                                                       app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=39))
    checkin(owner_engine, w, TODAY - timedelta(days=1))
    s = run(app_engine, w)
    assert s.by_kind.get("ending_soon") == 1 and s.by_kind.get("remedy_due") == 1
    body = [n for n in outbox(api, w) if n["kind"] == "ending_soon"][0]["body"]
    assert "day 40 of 43" in body and "3 days remain" in body
    w2 = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=43))
    s = run(app_engine, w2)
    assert s.by_kind == {"plan_complete": 1}
    run(app_engine, w2, NOW + timedelta(days=2))
    assert len([n for n in outbox(api, w2) if n["kind"] == "plan_complete"]) == 1
    ne = api.get("/v1/needs-you", headers=w2["h"]).json()
    assert [p["plan_id"] for p in ne["ended_plans"]] == [w2["plan"]["id"]]


def test_followup_reminder_day_before_and_hindi(api, auth, make_practice, owner_engine,
                                                app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=1),
           language="hi-IN")
    checkin(owner_engine, w, TODAY - timedelta(days=1))
    r = api.post(f"/v1/clients/{w['cid']}/consultations", headers=w["h"], json={
        "follow_up_date": "2026-11-05", "topic": "review"})
    assert r.status_code == 201 and r.json()["consultation"]["follow_up_date"] == "2026-11-05"
    s = run(app_engine, w)
    assert s.by_kind["followup_due"] == 1
    f = [n for n in outbox(api, w) if n["kind"] == "followup_due"][0]
    assert f["language"] == "hi" and "फ़ॉलो-अप" in f["body"] and "सलाह नहीं" in f["body"]
    run(app_engine, w)
    assert len([n for n in outbox(api, w) if n["kind"] == "followup_due"]) == 1


# ------------------------------------------------------------- missed-day policy
def _missed_setup(api, auth, make_practice, owner_engine, policy):
    w = mk(api, auth, make_practice, owner_engine, policy=policy, start=TODAY - timedelta(days=3))
    checkin(owner_engine, w, TODAY - timedelta(days=3))
    checkin(owner_engine, w, TODAY - timedelta(days=2))
    # TODAY-1 (3 Nov) is missed.
    return w


def test_policy_restart(api, auth, make_practice, owner_engine, app_engine):
    w = _missed_setup(api, auth, make_practice, owner_engine, "restart")
    s = run(app_engine, w)
    row = plan_row(app_engine, w)
    assert row["start_date"] == TODAY and row["restart_count"] == 1 and row["missed_days"] == 1
    assert row["last_missed_date"] == TODAY - timedelta(days=1)
    assert s.by_kind == {"remedy_missed": 1}  # replaces the due message that day
    n = outbox(api, w)[0]
    assert "begins again from today" in n["body"] and n["kind"] == "remedy_missed"
    plan = api.get(f"/v1/remedy-plans/{w['plan']['id']}", headers=w["h"]).json()["remedy_plan"]
    assert all(i["done_days"] == 0 for i in plan["items"])  # old days no longer count
    # Idempotent: no second restart, no second message.
    assert run(app_engine, w).created == 0
    assert plan_row(app_engine, w)["restart_count"] == 1
    # Needs-you surfaces it (it judges against the real clock, so move the miss to yesterday).
    with owner_engine.begin() as c:
        c.execute(text("UPDATE remedy_plan SET last_missed_date = (now() AT TIME ZONE "
                       "'Asia/Kolkata')::date - 1 WHERE id=:i"), {"i": w["plan"]["id"]})
    ne = api.get("/v1/needs-you", headers=w["h"]).json()
    assert ne["missed_remedies"][0]["policy"] == "restart"


def test_policy_extend(api, auth, make_practice, owner_engine, app_engine):
    w = _missed_setup(api, auth, make_practice, owner_engine, "extend")
    run(app_engine, w)
    row = plan_row(app_engine, w)
    assert (row["cycle_days"], row["extended_days"], row["missed_days"]) == (44, 1, 1)
    assert row["start_date"] == TODAY - timedelta(days=3)
    run(app_engine, w)
    assert plan_row(app_engine, w)["cycle_days"] == 44
    assert "extended by one day and now runs 44 days" in outbox(api, w)[0]["body"]


@pytest.mark.parametrize("policy", ["warn", "ignore"])
def test_policy_warn_and_ignore_change_nothing(api, auth, make_practice, owner_engine,
                                               app_engine, policy):
    w = _missed_setup(api, auth, make_practice, owner_engine, policy)
    run(app_engine, w)
    row = plan_row(app_engine, w)
    assert (row["cycle_days"], row["restart_count"], row["missed_days"]) == (43, 0, 1)
    assert row["start_date"] == TODAY - timedelta(days=3)
    assert "keep each day in sequence" in outbox(api, w)[0]["body"]


def test_policy_catches_up_after_downtime(api, auth, make_practice, owner_engine, app_engine):
    # Two missed days (1 and 2 Nov), only noticed on 4 Nov: extend adds 2, evaluated once.
    w = mk(api, auth, make_practice, owner_engine, policy="extend",
           start=TODAY - timedelta(days=3))
    checkin(owner_engine, w, TODAY - timedelta(days=1))
    with tenant_session(app_engine, w["pid"]) as db:
        p = db.get(RemedyPlan, uuid.UUID(w["plan"]["id"]))
        res = evaluate_plan(db, p, TODAY)
    assert len(res.missed_dates) == 2 and not res.missed_last_day
    assert plan_row(app_engine, w)["cycle_days"] == 45
    with tenant_session(app_engine, w["pid"]) as db:
        p = db.get(RemedyPlan, uuid.UUID(w["plan"]["id"]))
        assert evaluate_plan(db, p, TODAY).missed_dates == []


def test_fully_done_days_are_not_missed(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="restart", start=TODAY - timedelta(days=2))
    checkin(owner_engine, w, TODAY - timedelta(days=2))
    checkin(owner_engine, w, TODAY - timedelta(days=1))
    run(app_engine, w)
    row = plan_row(app_engine, w)
    assert (row["missed_days"], row["restart_count"]) == (0, 0)
    assert row["evaluated_through"] == TODAY - timedelta(days=1)


# --------------------------------------------------------------------- sending
def test_send_job_delivers_via_console_and_records(api, auth, make_practice, owner_engine,
                                                   app_engine, clean):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    run(app_engine, w)
    reg = worker.default_registry(app_engine, None)
    assert worker.process_one(app_engine, reg, "t")
    assert len(clean.sent) == 1 and clean.sent[0].to == "asha@example.test"
    assert clean.sent[0].unsubscribe_url and "Namaste Asha" in clean.sent[0].body
    n = outbox(api, w)[0]
    assert n["status"] == "sent" and n["provider"] == "console" and n["sent_at"]
    # Running the job again cannot double send.
    assert not worker.process_one(app_engine, reg, "t")


def test_failed_send_retries_then_fails_and_resend(api, auth, make_practice, owner_engine,
                                                   app_engine, clean, monkeypatch):
    monkeypatch.setattr(queue, "BACKOFF_BASE_SECONDS", 0.0)

    class Boom:
        kind, name = "email", "boom"

        def send(self, msg):
            raise channels.ChannelError("provider down")

    channels.set_channel("email", Boom())
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    run(app_engine, w)
    reg = worker.default_registry(app_engine, None)
    while worker.process_one(app_engine, reg, "t"):
        pass
    n = outbox(api, w)[0]
    assert n["status"] == "failed" and n["attempts"] == 5 and "ChannelError" in n["last_error"]
    ne = api.get("/v1/needs-you", headers=w["h"]).json()
    assert ne["failed_notifications"][0]["id"] == n["id"]
    channels.set_channel("email", clean)
    r = api.post(f"/v1/notifications/{n['id']}/resend", headers=w["h"])
    assert r.status_code == 200 and r.json()["notification"]["resend_count"] == 1
    assert api.post(f"/v1/notifications/{n['id']}/resend", headers=w["h"]).status_code == 409
    while worker.process_one(app_engine, reg, "t"):
        pass
    assert outbox(api, w)[0]["status"] == "sent" and len(clean.sent) == 1


def test_resend_needs_consent(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    run(app_engine, w)
    reg = worker.default_registry(app_engine, None)
    worker.process_one(app_engine, reg, "t")
    api.post(f"/v1/clients/{w['cid']}/consents/reminders/withdraw", headers=w["h"])
    nid = outbox(api, w)[0]["id"]
    r = api.post(f"/v1/notifications/{nid}/resend", headers=w["h"])
    assert r.status_code == 409 and r.json()["code"] == "consent_required"


def test_tick_job_runs_via_worker_and_ensure_is_not_piled_up(api, auth, make_practice,
                                                             owner_engine, app_engine):
    assert scheduler.ensure_tick_job(app_engine) is True
    assert scheduler.ensure_tick_job(app_engine) is False
    reg = worker.default_registry(app_engine, None)
    assert worker.process_one(app_engine, reg, "t")
    assert scheduler.ensure_tick_job(app_engine) is True


def test_run_tick_isolates_practices(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    stats = scheduler.run_tick(app_engine, NOW)
    assert stats.errors == 0 and stats.practices >= 1
    assert any(n["kind"] == "remedy_due" for n in outbox(api, w))
    api.put("/v1/notification-settings", headers=w["h"], json={"notify_enabled": False})
    w3 = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    api.put("/v1/notification-settings", headers=w3["h"], json={"notify_enabled": False})
    scheduler.run_tick(app_engine, NOW)
    assert outbox(api, w3) == []


# ------------------------------------------------------------------ public links
def _link_token(w, day=TODAY, now=NOW, purpose_url=links.checkin_url):
    url = purpose_url(w["pid"], w["cid"], w["plan"]["id"], day, "en", now)
    return url.rsplit("/", 1)[1]


def test_checkin_link_page_and_one_tap(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=1))
    tok = links.sign("checkin", {"p": w["pid"], "c": w["cid"], "pl": w["plan"]["id"],
                                 "d": TODAY.isoformat(), "l": "en"}, timedelta(hours=36))
    r = api.get(f"/v1/public/checkin/{tok}")  # no auth header
    assert r.status_code == 200 and "Feed crows" in r.text and "<form" in r.text
    with owner_engine.begin() as c:  # GET must not record anything
        assert c.scalar(text("SELECT count(*) FROM remedy_checkin")) >= 0
    before = _n_checkins(owner_engine, w)
    assert before == 0
    r = api.post(f"/v1/public/checkin/{tok}")
    assert r.status_code == 200 and "Thank you" in r.text
    assert _n_checkins(owner_engine, w) == 2
    api.post(f"/v1/public/checkin/{tok}")  # idempotent
    assert _n_checkins(owner_engine, w) == 2
    assert "already marked" in api.get(f"/v1/public/checkin/{tok}").text
    plan = api.get(f"/v1/remedy-plans/{w['plan']['id']}", headers=w["h"]).json()["remedy_plan"]
    assert all(i["done_days"] == 1 for i in plan["items"])


def _n_checkins(engine, w):
    with engine.begin() as c:
        return c.scalar(text("SELECT count(*) FROM remedy_checkin WHERE practice_id=:p"),
                        {"p": w["pid"]})


def test_checkin_link_expired_tampered_wrong_purpose(api, auth, make_practice, owner_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=1))
    old = datetime.now(tz=UTC) - timedelta(days=3)
    expired = links.sign("checkin", {"p": w["pid"], "c": w["cid"], "pl": w["plan"]["id"],
                                     "d": TODAY.isoformat()}, timedelta(hours=36), old)
    r = api.post(f"/v1/public/checkin/{expired}")
    assert r.status_code == 410 and _n_checkins(owner_engine, w) == 0
    good = links.sign("checkin", {"p": w["pid"], "c": w["cid"], "pl": w["plan"]["id"],
                                  "d": TODAY.isoformat()}, timedelta(hours=1))
    body, sig = good.split(".")
    assert api.post(f"/v1/public/checkin/{body}.{sig[:-3]}abc").status_code == 400
    assert api.post("/v1/public/checkin/nonsense").status_code == 400
    stop_tok = links.sign("stop", {"p": w["pid"], "c": w["cid"]}, timedelta(hours=1))
    assert api.post(f"/v1/public/checkin/{stop_tok}").status_code == 400
    assert _n_checkins(owner_engine, w) == 0


def test_checkin_link_other_practice_and_inactive_plan(api, auth, make_practice, owner_engine):
    a = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=1))
    b = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=1))
    # Token for practice B naming practice A's plan: RLS hides it, nothing recorded.
    tok = links.sign("checkin", {"p": b["pid"], "c": a["cid"], "pl": a["plan"]["id"],
                                 "d": TODAY.isoformat()}, timedelta(hours=1))
    assert api.post(f"/v1/public/checkin/{tok}").status_code == 410
    assert _n_checkins(owner_engine, a) == 0
    api.post(f"/v1/remedy-plans/{a['plan']['id']}/cancel", headers=a["h"])
    tok = links.sign("checkin", {"p": a["pid"], "c": a["cid"], "pl": a["plan"]["id"],
                                 "d": TODAY.isoformat()}, timedelta(hours=1))
    assert api.post(f"/v1/public/checkin/{tok}").status_code == 410


def test_checkin_link_rate_limited(api, auth, make_practice, owner_engine):
    from app import ratelimit

    ratelimit.clear(owner_engine)
    codes = [api.get("/v1/public/checkin/x").status_code for _ in range(35)]
    assert codes.count(429) >= 4 and codes[0] == 400
    ratelimit.clear(owner_engine)
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY - timedelta(days=1))
    tok = links.sign("checkin", {"p": w["pid"], "c": w["cid"], "pl": w["plan"]["id"],
                                 "d": TODAY.isoformat()}, timedelta(hours=1))
    codes = [api.post(f"/v1/public/checkin/{tok}").status_code for _ in range(8)]
    assert codes[:6] == [200] * 6 and codes[6:] == [429, 429]
    ratelimit.clear(owner_engine)


def test_stop_link_withdraws_everything(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    run(app_engine, w)
    tok = links.sign("stop", {"p": w["pid"], "c": w["cid"], "l": "hi"}, timedelta(days=1))
    page = api.get(f"/v1/public/stop/{tok}")
    assert page.status_code == 200 and "संदेश बंद करें" in page.text
    assert outbox(api, w)[0]["status"] == "pending"  # GET changed nothing
    assert api.post(f"/v1/public/stop/{tok}").status_code == 200
    prefs = api.get(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"]).json()
    assert prefs["email_opt_in"] is False and prefs["reminders_consent"] is False
    assert prefs["eligible_channels"] == []
    assert outbox(api, w)[0]["status"] == "cancelled"
    assert run(app_engine, w, NOW + timedelta(days=1)).created == 0


# ------------------------------------------------------------------------- API
def test_template_edit_preview_reset_and_sandbox(api, auth, make_practice, owner_engine,
                                                 app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    h = w["h"]
    listing = api.get("/v1/notification-templates", headers=h).json()
    assert len(listing["templates"]) == 10 and "name" in listing["variables"]
    bad = api.put("/v1/notification-templates", headers=h, json={
        "kind": "remedy_due", "language": "en", "body": "{{ name.__class__ }}"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_template"
    ok = api.put("/v1/notification-templates", headers=h, json={
        "kind": "remedy_due", "language": "en", "subject": "Day {{ day }}",
        "body": "Hello {{ name }}, do it: {{ link }}"})
    assert ok.status_code == 200 and ok.json()["source"] == "practice"
    pv = api.post("/v1/notification-preview", headers=h, json={
        "kind": "remedy_due", "client_id": w["cid"]}).json()
    assert pv["source"] == "practice" and pv["subject"] == "Day 12"
    assert pv["body"].startswith("Hello Asha") and "not medical" in pv["body"]
    draft = api.post("/v1/notification-preview", headers=h, json={
        "kind": "remedy_due", "body": "Draft {{ plan_title }}"}).json()
    assert draft["source"] == "draft" and draft["body"].startswith("Draft 43 day")
    assert api.post("/v1/notification-preview", headers=h, json={
        "kind": "remedy_due", "body": "{{ nope }}"}).status_code == 422
    # The tick now uses the edited template.
    run(app_engine, w)
    assert outbox(api, w)[0]["body"].startswith("Hello Asha")
    assert api.delete("/v1/notification-templates", headers=h, params={
        "kind": "remedy_due", "language": "en"}).status_code == 204
    assert api.delete("/v1/notification-templates", headers=h, params={
        "kind": "remedy_due", "language": "en"}).status_code == 404


def test_roles_and_settings_validation(api, auth, make_practice, owner_engine, add_member=None):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    h = w["h"]
    assert api.put("/v1/notification-settings", headers=h,
                   json={"timezone": "Mars/Base"}).status_code == 422
    assert api.put("/v1/notification-settings", headers=h,
                   json={"notify_hour": 25}).status_code == 422
    r = api.put("/v1/notification-settings", headers=h, json={"notify_hour": 7})
    assert r.json() == {"timezone": "Asia/Kolkata", "notify_hour": 7, "notify_enabled": True}
    assert api.get("/v1/notifications").status_code == 401
    assert api.get("/v1/needs-you").status_code == 401


def test_tenant_isolation_of_outbox_and_rls(api, auth, make_practice, owner_engine, app_engine):
    a = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    b = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    run(app_engine, a)
    assert outbox(api, b) == []
    nid = outbox(api, a)[0]["id"]
    assert api.post(f"/v1/notifications/{nid}/resend", headers=b["h"]).status_code == 404
    with tenant_session(app_engine, b["pid"]) as db:
        for t in ("notification", "notification_pref", "notification_template"):
            assert db.execute(text(f"SELECT count(*) FROM {t} WHERE practice_id=:p"),
                              {"p": a["pid"]}).scalar() == 0
    with app_engine.begin() as c:  # unbound session sees nothing
        assert c.scalar(text("SELECT count(*) FROM notification")) == 0


def test_needs_you_followups_and_done_followup_disappears(api, auth, make_practice,
                                                          owner_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    today = datetime.now(tz=UTC).date()
    due_day = (today - timedelta(days=2)).isoformat()
    api.post(f"/v1/clients/{w['cid']}/consultations", headers=w["h"],
             json={"follow_up_date": due_day, "consulted_at": (
                 datetime.now(tz=UTC) - timedelta(days=9)).isoformat()})
    ne = api.get("/v1/needs-you", headers=w["h"]).json()
    assert len(ne["followups"]) == 1 and ne["followups"][0]["days_overdue"] >= 1
    api.post(f"/v1/clients/{w['cid']}/consultations", headers=w["h"], json={})  # they came in
    assert api.get("/v1/needs-you", headers=w["h"]).json()["followups"] == []


def test_migration_head_chain_and_reminders_purpose(api, auth, make_practice, owner_engine):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config("alembic.ini"))
    head = script.get_current_head()
    # The notifications migration must sit on the single linear chain to head.
    assert "0004_notifications" in {r.revision for r in script.walk_revisions("base", head)}
    with owner_engine.begin() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == head
    pid, s = make_practice()
    cid = api.post("/v1/clients", json={"display_name": "X"}, headers=auth(s, pid)
                   ).json()["client"]["id"]
    st = api.get(f"/v1/clients/{cid}/consents", headers=auth(s, pid)).json()
    assert "reminders" in st["active"] or "reminders" in str(st)
