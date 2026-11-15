"""Billing on real Postgres: entitlements, webhook signature and idempotency,
GST split, invoice numbering across a financial year, RLS, PDF download."""

import json
import time
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.billing import service
from app.billing.gst import gstin_checksum
from app.billing.provider import MockProvider, sign_body
from app.db import make_engine
from app.main import create_app
from app.storage import LocalStorage
from app.tenancy.models import Practice
from app.tenancy.session import tenant_session

SECRET = "whsec_test"


def make_gstin(state: str) -> str:
    first14 = f"{state}AAPFU0939F1Z"
    return first14 + gstin_checksum(first14)


@pytest.fixture()
def bill(monkeypatch, app_engine, stub, tmp_path):
    monkeypatch.setenv("ANKANA_BILLING", "on")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("ANKANA_SUPPLIER_STATE_CODE", "29")
    storage = LocalStorage(tmp_path / "store", "k", "http://testserver")
    app = create_app(engine=make_engine("sqlite://"), pg_engine=app_engine, verifier=stub,
                     storage=storage)
    app.state.billing_provider = MockProvider()
    app.state.billing_pdf = lambda html, branding, title: b"%PDF-1.4 fake " + title.encode()
    return TestClient(app)


@pytest.fixture()
def owner(bill, auth):
    def _make(name="Studio One"):
        subject = f"user-{uuid.uuid4().hex[:10]}"
        r = bill.post("/v1/practices", json={"name": name}, headers=auth(subject))
        assert r.status_code == 201, r.text
        pid = r.json()["practice_id"]
        return pid, auth(subject, pid)

    return _make


def webhook(client, ev, event_id=None, sig=None, secret=SECRET):
    body = json.dumps(ev).encode()
    return client.post("/v1/billing/webhooks/razorpay", content=body, headers={
        "X-Razorpay-Signature": sig or sign_body(secret, body),
        "X-Razorpay-Event-Id": event_id or uuid.uuid4().hex,
        "Content-Type": "application/json"})


def ev(kind, sub_id, payment=None, start=None, end=None):
    ent = {"id": sub_id, "status": "active"}
    if start:
        ent["current_start"], ent["current_end"] = start, end
    payload = {"subscription": {"entity": ent}}
    if payment:
        payload["payment"] = {"entity": payment}
    return {"entity": "event", "event": kind, "contains": list(payload), "payload": payload,
            "created_at": int(time.time())}


def activate(bill, headers, plan="solo", interval="month", pay=None):
    r = bill.post("/v1/billing/checkout", json={"plan": plan, "interval": interval},
                  headers=headers)
    assert r.status_code == 201, r.text
    sub_id = bill.app.state.billing_provider.subscriptions[-1]["id"]
    now = int(time.time())
    assert webhook(bill, ev("subscription.activated", sub_id, start=now,
                            end=now + 30 * 86400)).json()["status"] == "applied"
    if pay:
        pay = {"id": pay, "amount": r.json()["amount_paise"], "status": "captured"}
        assert webhook(bill, ev("subscription.charged", sub_id, pay, now, now + 30 * 86400)
                       ).status_code == 200
    return sub_id


def seed_usage(owner_engine, pid, metric, value):
    with owner_engine.begin() as c:
        c.execute(text(
            "INSERT INTO usage_counter (practice_id, metric, period, value) VALUES "
            "(:p, :m, date_trunc('month', now())::date, :v)"), {"p": pid, "m": metric, "v": value})


# ---------------------------------------------------------------- entitlements
def test_billing_off_is_unlimited_and_routes_hidden(api, auth, make_practice, monkeypatch,
                                                    owner_engine):
    monkeypatch.delenv("ANKANA_BILLING", raising=False)
    pid, subject = make_practice()
    h = auth(subject, pid)
    for i in range(7):  # beyond the Free cap of 5
        assert api.post("/v1/clients", json={"display_name": f"C{i}"}, headers=h).status_code == 201
    seed_usage(owner_engine, pid, "ai_asks", 10_000)
    r = api.post(f"/v1/charts/{uuid.uuid4()}/ask", json={"question": "hi"}, headers=h)
    assert r.status_code == 404  # reached the handler: no entitlement block
    r = api.get("/v1/billing/plans", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "billing_disabled"
    assert api.get("/v1/meta").json()["billing"] is False


def test_free_client_cap_402_with_upgrade_hint(bill, owner):
    pid, h = owner()
    for i in range(5):
        assert bill.post("/v1/clients", json={"display_name": f"C{i}"}, headers=h
                         ).status_code == 201
    r = bill.post("/v1/clients", json={"display_name": "C6"}, headers=h)
    assert r.status_code == 402 and r.headers["content-type"].startswith("application/problem+json")
    b = r.json()
    assert b["code"] == "plan_limit_reached" and b["limit"] == 5 and b["used"] == 5
    assert b["upgrade_to"] == "solo" and b["upgrade_url"] == "/settings/billing"
    assert bill.get("/v1/meta").json()["billing"] is True


def test_ask_quota_402_and_report_feature_403(bill, owner, owner_engine):
    pid, h = owner()
    r = bill.post(f"/v1/charts/{uuid.uuid4()}/ask", json={"question": "hi"}, headers=h)
    assert r.status_code == 404  # under quota: reaches the handler
    seed_usage(owner_engine, pid, "ai_asks", 10)
    r = bill.post(f"/v1/charts/{uuid.uuid4()}/ask", json={"question": "hi"}, headers=h)
    assert r.status_code == 402 and r.json()["metric"] == "ai_asks"
    r = bill.post("/v1/reports", json={"chart_id": str(uuid.uuid4())}, headers=h)
    assert r.status_code == 403 and r.json()["code"] == "plan_feature_unavailable"
    assert r.json()["upgrade_to"] == "solo"


def test_paid_plan_raises_limits_and_usage_meter(bill, owner, owner_engine):
    pid, h = owner()
    seed_usage(owner_engine, pid, "ai_asks", 10)
    activate(bill, h, "solo")
    r = bill.post(f"/v1/charts/{uuid.uuid4()}/ask", json={"question": "hi"}, headers=h)
    assert r.status_code == 404  # 10 of 150 is fine now
    s = bill.get("/v1/billing/subscription", headers=h).json()
    assert s["plan"]["key"] == "solo" and s["subscription"]["status"] == "active"
    usage = {u["metric"]: u for u in s["usage"]}
    assert usage["ai_asks"]["used"] == 10 and usage["ai_asks"]["limit"] == 150
    assert usage["reports"]["limit"] == 5


def test_billing_routes_owner_only(bill, owner, auth, stub):
    pid, h = owner()
    assert bill.get("/v1/billing/plans", headers=h).status_code == 200
    assert bill.get("/v1/billing/plans").status_code == 401


# ------------------------------------------------------------------ checkout
def test_checkout_downgrade_and_cancel_rules(bill, owner):
    pid, h = owner()
    activate(bill, h, "studio")
    assert bill.post("/v1/billing/checkout", json={"plan": "studio"}, headers=h
                     ).json()["code"] == "already_subscribed"
    r = bill.post("/v1/billing/checkout", json={"plan": "solo"}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "downgrade_requires_cancel"
    assert bill.post("/v1/billing/checkout", json={"plan": "free"}, headers=h
                     ).json()["code"] == "invalid_plan"
    mock = bill.app.state.billing_provider
    r = bill.post("/v1/billing/cancel", headers=h)
    assert r.status_code == 200 and r.json()["cancel_at_period_end"] is True
    assert mock.cancelled[-1][1] is True  # at cycle end
    sub_id = mock.subscriptions[-1]["id"]
    assert webhook(bill, ev("subscription.cancelled", sub_id)).json()["status"] == "applied"
    s = bill.get("/v1/billing/subscription", headers=h).json()
    assert s["plan"]["key"] == "free" and s["subscription"] is None


def test_upgrade_cancels_old_subscription(bill, owner):
    pid, h = owner()
    solo = activate(bill, h, "solo")
    activate(bill, h, "studio")
    assert (solo, False) in bill.app.state.billing_provider.cancelled
    assert bill.get("/v1/billing/subscription", headers=h).json()["plan"]["key"] == "studio"


# ------------------------------------------------------------------ webhooks
def test_webhook_signature_required(bill, owner):
    pid, h = owner()
    sub = activate(bill, h)
    e = ev("subscription.cancelled", sub)
    assert webhook(bill, e, sig="0" * 64).status_code == 401
    assert webhook(bill, e, secret="wrong").json()["code"] == "invalid_signature"
    r = bill.post("/v1/billing/webhooks/razorpay", content=json.dumps(e))
    assert r.status_code == 401
    assert bill.get("/v1/billing/subscription", headers=h).json()["plan"]["key"] == "solo"


def test_webhook_503_without_secret(bill, monkeypatch):
    monkeypatch.delenv("RAZORPAY_WEBHOOK_SECRET")
    assert webhook(bill, ev("x", "y")).status_code == 503


def test_webhook_idempotent_one_invoice(bill, owner):
    pid, h = owner()
    sub = activate(bill, h)
    now = int(time.time())
    pay = {"id": "pay_dup1", "amount": 70_682}
    e = ev("subscription.charged", sub, pay, now, now + 86400 * 30)
    assert webhook(bill, e, event_id="evt_1").json()["status"] == "applied"
    assert webhook(bill, e, event_id="evt_1").json()["status"] == "duplicate"
    # a different event id carrying the same payment must not invoice twice either
    assert webhook(bill, e, event_id="evt_2").status_code == 200
    items = bill.get("/v1/billing/invoices", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["total_paise"] == 70_682


def test_unknown_subscription_acknowledged(bill):
    r = webhook(bill, ev("subscription.charged", "sub_nobody"))
    assert r.status_code == 200 and r.json()["status"] == "ignored_unmatched"


def test_payment_failed_grace_then_downgrade(bill, owner, owner_engine):
    pid, h = owner()
    sub = activate(bill, h)
    assert webhook(bill, ev("payment.failed", sub, {"id": "pay_f", "amount": 70_682})
                   ).json()["status"] == "applied"
    s = bill.get("/v1/billing/subscription", headers=h).json()
    assert s["in_grace"] and s["plan"]["key"] == "solo"
    assert s["subscription"]["status"] == "past_due" and s["subscription"]["grace_until"]
    assert webhook(bill, ev("subscription.halted", sub)).status_code == 200
    with owner_engine.begin() as c:
        c.execute(text("UPDATE subscription SET grace_until = now() - interval '1 day' "
                       "WHERE provider_subscription_id = :s"), {"s": sub})
    assert bill.get("/v1/billing/subscription", headers=h).json()["plan"]["key"] == "free"
    # a successful charge restores the plan and clears the grace
    now = int(time.time())
    webhook(bill, ev("subscription.charged", sub, {"id": "pay_ok", "amount": 70_682},
                     now, now + 86400 * 30))
    s = bill.get("/v1/billing/subscription", headers=h).json()
    assert s["plan"]["key"] == "solo" and not s["in_grace"]


def test_cancelled_subscription_not_revived(bill, owner):
    pid, h = owner()
    sub = activate(bill, h)
    webhook(bill, ev("subscription.cancelled", sub))
    now = int(time.time())
    webhook(bill, ev("subscription.activated", sub, start=now, end=now + 86400))
    assert bill.get("/v1/billing/subscription", headers=h).json()["plan"]["key"] == "free"


# ------------------------------------------------------------------- GST
@pytest.mark.parametrize("state, intra", [("29", True), ("27", False)])
def test_invoice_gst_split_by_place_of_supply(bill, owner, state, intra):
    pid, h = owner()
    r = bill.put("/v1/billing/profile", json={"gstin": make_gstin(state), "legal_name": "Acme"},
                 headers=h)
    assert r.status_code == 200 and r.json()["state_code"] == state
    activate(bill, h, "solo", pay=f"pay_{uuid.uuid4().hex[:8]}")
    inv = bill.get("/v1/billing/invoices", headers=h).json()["items"][0]
    assert inv["taxable_paise"] == 59_900 and inv["total_paise"] == 70_682
    assert inv["intra_state"] is intra and inv["place_of_supply"] == state
    if intra:
        assert (inv["cgst_paise"], inv["sgst_paise"], inv["igst_paise"]) == (5_391, 5_391, 0)
    else:
        assert (inv["cgst_paise"], inv["sgst_paise"], inv["igst_paise"]) == (0, 0, 10_782)
    assert inv["number"].startswith("AN/") and len(inv["number"]) <= 16


def test_unregistered_recipient_without_state_is_intra_state(bill, owner):
    pid, h = owner()
    activate(bill, h, pay="pay_nostate")
    inv = bill.get("/v1/billing/invoices", headers=h).json()["items"][0]
    assert inv["intra_state"] is True and inv["place_of_supply"] == "29"


def test_profile_validation(bill, owner):
    pid, h = owner()
    bad = bill.put("/v1/billing/profile", json={"gstin": "27AAPFU0939F1ZX"}, headers=h)
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_gst_details"
    mismatch = bill.put("/v1/billing/profile",
                        json={"gstin": make_gstin("29"), "state_code": "27"}, headers=h)
    assert mismatch.status_code == 422
    ok = bill.put("/v1/billing/profile", json={"state_code": "07", "legal_name": "Solo"},
                  headers=h)
    assert ok.status_code == 200 and ok.json()["state_code"] == "07"


# -------------------------------------------------------- invoice numbering
def test_numbering_sequential_and_resets_each_financial_year(app_engine, make_practice, api):
    pa, _ = make_practice("A")
    pb, _ = make_practice("B")

    def issue(pid, pay, at):
        with tenant_session(app_engine, pid) as db:
            inv = service.issue_invoice(
                db, practice=db.get(Practice, pid), subscription=None, payment_id=pay,
                amount_paise=70_682, plan_key="solo", interval="month", issued_at=at,
                period_start_=None, period_end_=None)
            return inv.number

    last_day = datetime(2031, 3, 31, 18, 29, tzinfo=UTC)  # 23:59 IST, FY 2030-31
    first_day = datetime(2031, 3, 31, 18, 31, tzinfo=UTC)  # 00:01 IST on 1 April
    u = uuid.uuid4().hex[:6]
    assert issue(pa, f"p1{u}", last_day) == "AN/3031/000001"
    assert issue(pb, f"p2{u}", last_day) == "AN/3031/000002"  # one series for all practices
    assert issue(pa, f"p3{u}", first_day) == "AN/3132/000001"  # new FY restarts
    assert issue(pb, f"p4{u}", first_day) == "AN/3132/000002"
    with tenant_session(app_engine, pa) as db:  # same payment again returns the same invoice
        again = service.issue_invoice(
            db, practice=db.get(Practice, pa), subscription=None, payment_id=f"p1{u}",
            amount_paise=70_682, plan_key="solo", interval="month", issued_at=first_day,
            period_start_=None, period_end_=None)
        assert again.number == "AN/3031/000001"


def test_failed_transaction_releases_the_number(app_engine, make_practice, api):
    pid, _ = make_practice("R")
    at = datetime(2032, 6, 1, tzinfo=UTC)
    with pytest.raises(RuntimeError), tenant_session(app_engine, pid) as db:
        service.next_invoice_number(db, at)
        raise RuntimeError("boom")
    with tenant_session(app_engine, pid) as db:
        assert service.next_invoice_number(db, at)[1] == "AN/3233/000001"


# ------------------------------------------------------------- RLS + PDF
def test_invoices_isolated_per_practice_and_download(bill, owner):
    pa, ha = owner("A")
    pb, hb = owner("B")
    activate(bill, ha, pay="pay_iso_a")
    inv = bill.get("/v1/billing/invoices", headers=ha).json()["items"][0]
    assert bill.get("/v1/billing/invoices", headers=hb).json()["items"] == []
    assert bill.get(f"/v1/billing/invoices/{inv['id']}/download", headers=hb).status_code == 404
    r = bill.get(f"/v1/billing/invoices/{inv['id']}/download", headers=ha)
    assert r.status_code == 200
    url = r.json()["download_url"].replace("http://testserver", "")
    assert bill.get(url).content.startswith(b"%PDF")
    assert r.json()["filename"].startswith("invoice-AN-")


def test_invoice_rows_cannot_be_edited_by_app_role(bill, owner, app_engine):
    pid, h = owner()
    activate(bill, h, pay="pay_immut")
    with pytest.raises(Exception, match="permission denied"), tenant_session(app_engine, pid) as db:
        db.execute(text("UPDATE invoice SET total_paise = 1"))
    with pytest.raises(Exception, match="permission denied"), tenant_session(app_engine, pid) as db:
        db.execute(text("DELETE FROM invoice"))


def test_invoice_html_content(bill, owner, app_engine):
    from sqlalchemy import select

    from app.billing.invoice import render_invoice_html
    from app.billing.models import Invoice, InvoiceLine

    pid, h = owner()
    bill.put("/v1/billing/profile", json={"gstin": make_gstin("27"), "legal_name": "Acme & Co"},
             headers=h)
    activate(bill, h, pay="pay_html")
    with tenant_session(app_engine, pid) as db:
        inv = db.scalar(select(Invoice))
        lines = list(db.scalars(select(InvoiceLine)))
        html = render_invoice_html(inv, lines)
    assert "Tax invoice" in html and inv.number in html and "998314" in html
    assert "IGST" in html and "706.82" in html and "Acme &amp; Co" in html
    assert "monospace" not in html and "—" not in html and "–" not in html
