"""Messaging on real Postgres: provider receipts on the outbox, signed webhooks, STOP replies,
permanent failures and quiet-hours deferral at send time. Providers are mocked HTTP."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import pytest
from sqlalchemy import text
from test_notify import TODAY, mk, outbox, run

from app import worker
from app.messaging import Http, MetaWhatsApp, WaTemplates
from app.messaging.sms import twilio_signature
from app.notify import channels, scheduler

SECRET = "meta-app-secret"


@pytest.fixture(autouse=True)
def clean(owner_engine, monkeypatch):
    with owner_engine.begin() as c:
        c.execute(text("DELETE FROM job"))
    monkeypatch.setenv("WHATSAPP_APP_SECRET", SECRET)
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")
    monkeypatch.setenv("MSG91_WEBHOOK_TOKEN", "msg91-token")
    monkeypatch.setenv("GUPSHUP_WEBHOOK_TOKEN", "gs-token")
    channels.set_channel("email", channels.ConsoleChannel("email"))
    yield
    for k in ("email", "whatsapp", "sms"):
        channels.set_channel(k, None)


def meta_channel(handler) -> MetaWhatsApp:
    h = Http(httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    return MetaWhatsApp("T", "1", templates=WaTemplates({"remedy_due": {
        "en": {"name": "remedy_due_en", "language": "en"}}}), http=h)


def send_whatsapp(api, auth, make_practice, owner_engine, app_engine, handler):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    api.put(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"],
            json={"whatsapp_opt_in": True,
                  # Empty quiet window so the test does not depend on the clock.
                  "quiet_start": "00:00", "quiet_end": "00:00"})
    channels.set_channel("whatsapp", meta_channel(handler))
    run(app_engine, w)
    reg = worker.default_registry(app_engine, None)
    while worker.process_one(app_engine, reg, "t"):
        pass
    return w


def signed(body: dict) -> tuple[bytes, dict]:
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}


def wa(outbox_rows):
    return next(n for n in outbox_rows if n["channel"] == "whatsapp")


def status_payload(mid, status, **extra):
    return {"entry": [{"changes": [{"value": {"statuses": [{"id": mid, "status": status,
                                                            **extra}]}}]}]}


def test_send_records_provider_id_and_receipts_move_forward(api, auth, make_practice,
                                                            owner_engine, app_engine):
    seen = []

    def handler(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.ABC"}]})

    w = send_whatsapp(api, auth, make_practice, owner_engine, app_engine, handler)
    row = wa(outbox(api, w))
    assert row["status"] == "sent" and row["provider"] == "meta"
    assert row["delivery_status"] == "sent" and seen[0]["template"]["name"] == "remedy_due_en"
    assert wa(outbox(api, w))["delivered_at"] is None

    for status, expect in (("delivered", "delivered"), ("read", "read")):
        raw, hdr = signed(status_payload("wamid.ABC", status))
        assert api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr).status_code == 200
        assert wa(outbox(api, w))["delivery_status"] == expect
    row = wa(outbox(api, w))
    assert row["delivered_at"] and row["read_at"]
    # a late or replayed 'delivered' cannot move it back
    raw, hdr = signed(status_payload("wamid.ABC", "delivered"))
    api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr)
    assert wa(outbox(api, w))["delivery_status"] == "read"
    # unknown id is accepted and ignored
    raw, hdr = signed(status_payload("wamid.NOPE", "failed"))
    assert api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr).status_code == 200


def test_failed_receipt_records_error(api, auth, make_practice, owner_engine, app_engine):
    w = send_whatsapp(api, auth, make_practice, owner_engine, app_engine,
                      lambda r: httpx.Response(200, json={"messages": [{"id": "wamid.F"}]}))
    raw, hdr = signed(status_payload("wamid.F", "failed",
                                     errors=[{"code": 131026, "title": "Undeliverable"}]))
    assert api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr).status_code == 200
    row = wa(outbox(api, w))
    assert row["delivery_status"] == "failed" and "131026" in row["delivery_error"]


def test_webhook_rejects_bad_signature_and_unconfigured_secret(api, monkeypatch):
    raw, hdr = signed(status_payload("x", "read"))
    assert api.post("/v1/webhooks/whatsapp/meta", content=raw).status_code == 403
    bad = {**hdr, "X-Hub-Signature-256": "sha256=" + "0" * 64}
    assert api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=bad).status_code == 403
    assert api.post("/v1/webhooks/whatsapp/meta", content=raw + b" ", headers=hdr
                    ).status_code == 403
    assert api.get("/v1/webhooks/whatsapp/meta", params={
        "hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "777"}
    ).text == "777"
    assert api.get("/v1/webhooks/whatsapp/meta", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "777"}
    ).status_code == 403
    monkeypatch.delenv("WHATSAPP_APP_SECRET")
    assert api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr).status_code == 503
    assert api.post("/v1/webhooks/whatsapp/gupshup?token=nope", json={}).status_code == 403
    assert api.post("/v1/webhooks/sms/msg91?token=nope", json=[]).status_code == 403
    assert api.post("/v1/webhooks/sms/twilio", data={"MessageSid": "x"}).status_code == 403


def test_twilio_and_msg91_receipts(api, auth, make_practice, owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    api.put(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"],
            json={"sms_opt_in": True})
    run(app_engine, w)
    with owner_engine.begin() as c:  # stand in for two sent messages
        c.execute(text("UPDATE notification SET status='sent', provider='twilio', "
                       "provider_message_id='SM1', delivery_status='sent' "
                       "WHERE practice_id=:p AND channel='sms'"), {"p": w["pid"]})
    params = {"MessageSid": "SM1", "MessageStatus": "delivered"}
    url = "http://testserver/v1/webhooks/sms/twilio"
    sig = twilio_signature("twilio-token", url, params)
    assert api.post("/v1/webhooks/sms/twilio", content=urlencode(params),
                    headers={"X-Twilio-Signature": sig,
                             "Content-Type": "application/x-www-form-urlencoded"}
                    ).status_code == 200
    sms = next(n for n in outbox(api, w) if n["channel"] == "sms")
    assert sms["delivery_status"] == "delivered"
    assert api.post("/v1/webhooks/sms/twilio", content=urlencode(params),
                    headers={"X-Twilio-Signature": "AAAA",
                             "Content-Type": "application/x-www-form-urlencoded"}
                    ).status_code == 403
    with owner_engine.begin() as c:
        c.execute(text("UPDATE notification SET provider='msg91', provider_message_id='R9', "
                       "delivery_status='sent' WHERE practice_id=:p AND channel='sms'"),
                  {"p": w["pid"]})
    r = api.post("/v1/webhooks/sms/msg91?token=msg91-token", json=[
        {"requestId": "R9", "report": [{"number": "91", "status": "2", "desc": "FAILED"}]}])
    assert r.status_code == 200
    sms = next(n for n in outbox(api, w) if n["channel"] == "sms")
    assert sms["delivery_status"] == "failed"


def test_stop_reply_switches_channel_off_and_cancels_pending(api, auth, make_practice,
                                                             owner_engine, app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY)
    api.put(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"],
            json={"whatsapp_opt_in": True})
    run(app_engine, w)  # one pending email, one pending whatsapp
    body = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "910000000000", "type": "text", "text": {"body": " Stop. "}}]}}]}]}
    raw, hdr = signed(body)
    assert api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr).status_code == 200
    prefs = api.get(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"]).json()
    assert prefs["whatsapp_opt_in"] is False and prefs["email_opt_in"] is True
    assert prefs["reminders_consent"] is True  # email is still wanted
    rows = {n["channel"]: n for n in outbox(api, w)}
    assert rows["whatsapp"]["status"] == "cancelled" and rows["email"]["status"] == "pending"
    # a non-keyword reply changes nothing
    raw, hdr = signed({"entry": [{"changes": [{"value": {"messages": [
        {"from": "910000000000", "type": "text", "text": {"body": "thanks"}}]}}]}]})
    api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr)
    # last channel off: consent is withdrawn too
    api.put(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"],
            json={"email_opt_in": False, "sms_opt_in": True})
    raw, hdr = signed(body)
    api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr)  # whatsapp again: no-op
    with owner_engine.begin() as c:
        n = c.scalar(text("SELECT count(*) FROM audit_event WHERE practice_id=:p AND "
                          "action='notification.stopped_by_reply'"), {"p": w["pid"]})
    assert n >= 1


def test_stop_on_last_channel_withdraws_consent(api, auth, make_practice, owner_engine,
                                                app_engine):
    w = mk(api, auth, make_practice, owner_engine, policy="warn", start=TODAY, email_opt=False)
    api.put(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"],
            json={"whatsapp_opt_in": True})
    raw, hdr = signed({"entry": [{"changes": [{"value": {"messages": [
        {"from": "+91 00000 00000", "type": "button", "button": {"text": "STOP"}}]}}]}]})
    api.post("/v1/webhooks/whatsapp/meta", content=raw, headers=hdr)
    prefs = api.get(f"/v1/clients/{w['cid']}/notification-prefs", headers=w["h"]).json()
    assert prefs["whatsapp_opt_in"] is False and prefs["reminders_consent"] is False
    assert prefs["eligible_channels"] == []


def test_permanent_provider_error_fails_the_notification_without_retry(
        api, auth, make_practice, owner_engine, app_engine):
    w = send_whatsapp(api, auth, make_practice, owner_engine, app_engine,
                      lambda r: httpx.Response(400, json={"error": {"code": 131047,
                                                                    "message": "window"}}))
    row = wa(outbox(api, w))
    assert row["status"] == "failed" and "131047" in row["last_error"]
    assert row["delivery_status"] is None
    with owner_engine.begin() as c:
        assert c.scalar(text("SELECT count(*) FROM job WHERE kind='notify_send' "
                             "AND status IN ('queued','running')")) == 0


def test_send_inside_quiet_hours_is_deferred(api, auth, make_practice, owner_engine,
                                             app_engine, monkeypatch):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(200, json={"messages": [{"id": "w"}]})

    monkeypatch.setattr(scheduler, "apply_quiet_hours",
                        lambda now, tz, s, e: now + timedelta(hours=5))
    w = send_whatsapp(api, auth, make_practice, owner_engine, app_engine, handler)
    assert calls == [] and wa(outbox(api, w))["status"] == "pending"
    with owner_engine.begin() as c:
        run_at = c.scalar(text("SELECT max(run_at) FROM job WHERE kind='notify_send' "
                               "AND status='queued'"))
    assert run_at > datetime.now(tz=UTC) + timedelta(hours=4)
