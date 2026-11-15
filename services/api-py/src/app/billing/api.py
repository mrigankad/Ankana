"""/v1/billing routes. Owner only, except the provider webhook (signature
verified, no user). Every route answers 404 unless ANKANA_BILLING is on."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.reports.pdf import html_to_pdf
from app.tenancy.models import Practice, Role, UserAccount
from app.tenancy.session import bind_practice
from app.v1.common import ProblemError, audit, paginate

from . import service
from .config import billing_enabled, webhook_secret
from .gst import GstError, validate_gstin, validate_state_code
from .invoice import invoice_filename, render_invoice_html
from .models import Invoice, InvoiceLine, Subscription
from .plans import GST_RATE_BP, catalogue, get_plan
from .provider import BillingProvider, provider_from_env, verify_signature

log = logging.getLogger(__name__)
OWNER = Depends(require_roles(Role.owner))
DOWNLOAD_TTL = 900


class CheckoutIn(BaseModel):
    plan: str = Field(min_length=1, max_length=32)
    interval: Literal["month", "year"] = "month"


class ProfileIn(BaseModel):
    legal_name: str | None = Field(default=None, max_length=200)
    gstin: str | None = Field(default=None, max_length=15)
    state_code: str | None = Field(default=None, max_length=2,
                                   description="GST state code; derived from the GSTIN if omitted")
    address: str | None = Field(default=None, max_length=500)


def _require_billing() -> None:
    if not billing_enabled():
        raise ProblemError(404, "billing is not enabled on this deployment", "billing_disabled")


def _provider(request: Request) -> BillingProvider:
    prov = getattr(request.app.state, "billing_provider", None)
    if prov is None:
        try:
            prov = provider_from_env()
        except Exception as exc:
            raise ProblemError(503, str(exc), "billing_unconfigured") from exc
        request.app.state.billing_provider = prov
    return prov


def _plan_json(key: str) -> dict:
    p = get_plan(key)
    return {"key": p.key, "name": p.name, "limits": p.limits, "features": list(p.features),
            "price_month_paise": p.price_month_paise, "price_year_paise": p.price_year_paise,
            "total_month_paise": p.total_paise("month"), "total_year_paise": p.total_paise("year"),
            "gst_rate_bp": GST_RATE_BP, "price_excludes_gst": True}


def _sub_json(s: Subscription | None) -> dict | None:
    if s is None:
        return None
    return {"id": str(s.id), "plan": s.plan_key, "interval": s.interval, "status": s.status,
            "current_period_end": s.current_period_end, "grace_until": s.grace_until,
            "cancel_at_period_end": s.cancel_at_period_end, "checkout_url": s.checkout_url
            if s.status == "created" else None}


def _invoice_json(i: Invoice) -> dict:
    return {"id": str(i.id), "number": i.number, "issued_at": i.issued_at,
            "total_paise": i.total_paise, "taxable_paise": i.taxable_paise,
            "cgst_paise": i.cgst_paise, "sgst_paise": i.sgst_paise, "igst_paise": i.igst_paise,
            "intra_state": i.intra_state, "place_of_supply": i.place_of_supply,
            "currency": i.currency, "period_start": i.period_start, "period_end": i.period_end}


def _profile_json(p: Practice) -> dict:
    rec = service.recipient_snapshot(p)
    return {"legal_name": p.billing_legal_name, "gstin": p.gstin, "state_code": rec["state_code"],
            "address": p.billing_address}


def build_billing_router() -> APIRouter:
    router = APIRouter(prefix="/v1/billing", tags=["billing"], dependencies=[Depends(_require_billing)])

    @router.get("/plans", operation_id="listPlans", summary="Plan catalogue (prices ex-GST)")
    def list_plans(m: CurrentMember = OWNER) -> dict:
        return {"plans": [_plan_json(k) for k in catalogue()],
                "sac": "998314", "gst_rate_bp": GST_RATE_BP}

    @router.get("/subscription", operation_id="getSubscription",
                summary="Current plan, subscription state and usage meter")
    def get_subscription(m: CurrentMember = OWNER, db: Session = Depends(tenant_db, scope="function")) -> dict:
        sub = service.effective_subscription(db, m.practice_id)
        key = sub.plan_key if sub else "free"
        pending = db.scalar(select(Subscription).where(
            Subscription.practice_id == m.practice_id, Subscription.status == "created")
            .order_by(Subscription.created_at.desc()).limit(1))
        return {"plan": _plan_json(key), "subscription": _sub_json(sub),
                "in_grace": bool(sub and sub.status in ("past_due", "halted")),
                "pending_checkout": _sub_json(pending),
                "usage": service.usage_meter(db, m.practice_id, key)}

    @router.get("/profile", operation_id="getBillingProfile",
                summary="GST invoice details of the practice")
    def get_profile(m: CurrentMember = OWNER, db: Session = Depends(tenant_db, scope="function")) -> dict:
        return _profile_json(db.get(Practice, m.practice_id))

    @router.put("/profile", operation_id="updateBillingProfile",
                summary="Set the GSTIN, legal name, state and address printed on invoices")
    def put_profile(body: ProfileIn, request: Request, m: CurrentMember = OWNER,
                    db: Session = Depends(tenant_db, scope="function")) -> dict:
        try:
            gstin = validate_gstin(body.gstin) if body.gstin else None
            state = validate_state_code(body.state_code) if body.state_code else None
            if gstin and state and gstin[:2] != state:
                raise GstError("state code does not match the GSTIN prefix")
            state = state or (gstin[:2] if gstin else None)
        except GstError as exc:
            raise ProblemError(422, str(exc), "invalid_gst_details") from exc
        p = db.get(Practice, m.practice_id)
        p.gstin, p.billing_state_code = gstin, state
        p.billing_legal_name, p.billing_address = body.legal_name, body.address
        db.flush()
        audit(db, m, "billing.profile_updated", "practice", m.practice_id, request)
        return _profile_json(p)

    @router.post("/checkout", status_code=201, operation_id="startCheckout",
                 summary="Start a hosted checkout for a paid plan; returns the payment link")
    def checkout(body: CheckoutIn, request: Request, m: CurrentMember = OWNER,
                 db: Session = Depends(tenant_db, scope="function")) -> dict:
        if body.plan not in catalogue():
            raise ProblemError(422, "unknown plan", "invalid_plan")
        email = db.scalar(select(UserAccount.email).where(UserAccount.id == m.user_id))
        sub = service.start_checkout(db, _provider(request), m.practice_id, body.plan,
                                     body.interval, email)
        audit(db, m, "billing.checkout_started", "subscription", sub.id, request,
              {"plan": body.plan, "interval": body.interval})
        return {"subscription_id": str(sub.id), "checkout_url": sub.checkout_url,
                "plan": sub.plan_key, "interval": sub.interval,
                "amount_paise": get_plan(sub.plan_key).total_paise(sub.interval)}

    @router.post("/cancel", operation_id="cancelSubscription",
                 summary="Cancel at the end of the paid period (immediately when payment failed)")
    def cancel(request: Request, m: CurrentMember = OWNER,
               db: Session = Depends(tenant_db, scope="function")) -> dict:
        sub = service.cancel(db, _provider(request), m.practice_id)
        audit(db, m, "billing.cancelled", "subscription", sub.id, request)
        return _sub_json(sub) or {}

    @router.get("/invoices", operation_id="listInvoices", summary="GST invoices, newest first")
    def list_invoices(limit: int = 50, cursor: str | None = None, m: CurrentMember = OWNER,
                      db: Session = Depends(tenant_db, scope="function")) -> dict:
        rows, nxt = paginate(db, select(Invoice), Invoice, max(1, min(limit, 200)), cursor)
        return {"items": [_invoice_json(i) for i in rows], "next_cursor": nxt}

    @router.get("/invoices/{invoice_id}/download", operation_id="downloadInvoice",
                summary="Signed, expiring link to the invoice PDF (rendered on first request)")
    def download_invoice(invoice_id: uuid.UUID, request: Request, m: CurrentMember = OWNER,
                         db: Session = Depends(tenant_db, scope="function")) -> dict:
        inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id))
        if inv is None:
            raise ProblemError(404, "invoice not found", "not_found")
        storage = request.app.state.storage
        if not (inv.pdf_storage_key and storage.exists(inv.pdf_storage_key)):
            lines = list(db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
                                    .order_by(InvoiceLine.position)))
            render = getattr(request.app.state, "billing_pdf", None) or html_to_pdf
            from .invoice import BRANDING

            pdf = render(render_invoice_html(inv, lines), BRANDING, f"Tax invoice {inv.number}")
            key = f"{m.practice_id}/invoices/{inv.number.replace('/', '-')}.pdf"
            storage.put(key, pdf, "application/pdf")
            inv.pdf_storage_key = key
            db.flush()
        return {"download_url": storage.signed_url(
            inv.pdf_storage_key, DOWNLOAD_TTL, filename=invoice_filename(inv.number)),
            "expires_in": DOWNLOAD_TTL, "filename": invoice_filename(inv.number)}

    @router.post("/webhooks/razorpay", operation_id="razorpayWebhook",
                 summary="Razorpay webhook (HMAC SHA256 signature, idempotent by event id)")
    async def razorpay_webhook(request: Request) -> dict:
        body = await request.body()
        secret = webhook_secret()
        if not secret:
            raise ProblemError(503, "webhook secret is not configured", "webhook_unconfigured")
        if not verify_signature(secret, body, request.headers.get("x-razorpay-signature")):
            raise ProblemError(401, "invalid webhook signature", "invalid_signature")
        try:
            event = json.loads(body)
        except ValueError:
            raise ProblemError(400, "body is not JSON", "invalid_body") from None
        event_id = request.headers.get("x-razorpay-event-id") or "sha256:" + _digest(body)
        provider = _provider(request)
        outcome = await run_in_threadpool(
            _process, request.app.state.pg_engine, provider, event_id, event)
        return {"status": outcome}

    return router


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _process(engine, provider: BillingProvider, event_id: str, event: dict) -> str:
    """One transaction: resolve practice, claim the event id, apply. A failure
    rolls the claim back too, so the provider's retry is processed again."""
    with Session(engine, expire_on_commit=False) as db, db.begin():
        practice_id = service.resolve_practice(db, event)
        if not service.record_event(db, event_id, provider.name, event.get("event", ""),
                                    practice_id):
            return "duplicate"
        if practice_id is None:
            return "ignored_unmatched"
        bind_practice(db, practice_id)
        return service.apply_event(db, provider, practice_id, event)


def install_billing(app) -> bool:
    """Mount /v1/billing. No-op unless the tenancy layer is installed."""
    if not hasattr(app.state, "pg_engine"):
        return False
    app.include_router(build_billing_router())
    return True

