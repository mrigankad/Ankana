"""Payment provider interface, Razorpay implementation and an in-memory mock.

RazorpayProvider talks to https://api.razorpay.com/v1 with HTTP basic auth
(key id : key secret). Endpoints used, per Razorpay's Subscriptions docs:
  POST /customers, POST /plans, POST /subscriptions, POST /subscriptions/{id}/cancel
Everything here is unverified against a live account: needs a Razorpay test
key pair before launch (see the Phase 2 billing report).

Webhooks: Razorpay signs the raw request body with HMAC SHA256 using the
webhook secret and sends the hex digest in X-Razorpay-Signature.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

RAZORPAY_API = "https://api.razorpay.com/v1"


class ProviderError(RuntimeError):
    """The payment provider rejected or failed a call."""


@dataclass(frozen=True)
class ProviderSubscription:
    id: str
    checkout_url: str
    status: str


class BillingProvider(Protocol):
    name: str

    def create_customer(self, *, name: str, email: str | None, gstin: str | None,
                        notes: dict[str, str]) -> str: ...

    def create_subscription(self, *, customer_id: str, plan_key: str, interval: str,
                            amount_paise: int, notes: dict[str, str]) -> ProviderSubscription: ...

    def cancel_subscription(self, subscription_id: str, *, at_cycle_end: bool) -> None: ...


def sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """Constant-time check. An empty secret or missing header never verifies."""
    if not secret or not signature:
        return False
    return hmac.compare_digest(sign_body(secret, body), signature.strip())


class RazorpayProvider:
    name = "razorpay"

    def __init__(self, key_id: str, key_secret: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=RAZORPAY_API, auth=(key_id, key_secret), timeout=15.0)
        self._plan_ids: dict[tuple[str, str], str] = {}

    def _post(self, path: str, payload: dict[str, Any]) -> dict:
        try:
            r = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"razorpay unreachable: {exc}") from exc
        if r.status_code >= 400:
            try:
                msg = r.json().get("error", {}).get("description") or r.text
            except ValueError:
                msg = r.text
            raise ProviderError(f"razorpay {r.status_code}: {msg[:300]}")
        return r.json()

    def create_customer(self, *, name, email, gstin, notes) -> str:
        body: dict[str, Any] = {"name": name, "fail_existing": "0", "notes": notes}
        if email:
            body["email"] = email
        if gstin:
            body["gstin"] = gstin
        return self._post("/customers", body)["id"]

    def _plan_id(self, plan_key: str, interval: str, amount_paise: int) -> str:
        """Plans are normally created once in the dashboard: RAZORPAY_PLAN_<KEY>_<INTERVAL>
        (e.g. RAZORPAY_PLAN_SOLO_MONTH). Otherwise one is created on first use."""
        env = os.getenv(f"RAZORPAY_PLAN_{plan_key.upper()}_{interval.upper()}")
        if env:
            return env
        cache_key = (plan_key, interval)
        if cache_key not in self._plan_ids:
            body = {"period": "yearly" if interval == "year" else "monthly", "interval": 1,
                    "item": {"name": f"Ankana {plan_key} ({interval})", "amount": amount_paise,
                             "currency": "INR"},
                    "notes": {"plan_key": plan_key, "interval": interval}}
            self._plan_ids[cache_key] = self._post("/plans", body)["id"]
        return self._plan_ids[cache_key]

    def create_subscription(self, *, customer_id, plan_key, interval, amount_paise, notes):
        body = {"plan_id": self._plan_id(plan_key, interval, amount_paise),
                "total_count": 10 if interval == "year" else 120, "quantity": 1,
                "customer_notify": 1, "notes": {**notes, "customer_id": customer_id}}
        data = self._post("/subscriptions", body)
        return ProviderSubscription(data["id"], data["short_url"], data.get("status", "created"))

    def cancel_subscription(self, subscription_id, *, at_cycle_end):
        self._post(f"/subscriptions/{subscription_id}/cancel",
                   {"cancel_at_cycle_end": 1 if at_cycle_end else 0})


@dataclass
class MockProvider:
    """Deterministic in-memory provider for tests and local development."""

    name: str = "mock"
    customers: list[dict] = field(default_factory=list)
    subscriptions: list[dict] = field(default_factory=list)
    cancelled: list[tuple[str, bool]] = field(default_factory=list)

    def create_customer(self, *, name, email, gstin, notes) -> str:
        cid = f"cust_mock_{uuid.uuid4().hex[:12]}"
        self.customers.append({"id": cid, "name": name, "email": email, "gstin": gstin})
        return cid

    def create_subscription(self, *, customer_id, plan_key, interval, amount_paise, notes):
        sid = f"sub_mock_{uuid.uuid4().hex[:12]}"
        self.subscriptions.append({"id": sid, "customer_id": customer_id, "plan_key": plan_key,
                                   "interval": interval, "amount_paise": amount_paise,
                                   "notes": notes})
        return ProviderSubscription(sid, f"https://checkout.mock.invalid/{sid}", "created")

    def cancel_subscription(self, subscription_id, *, at_cycle_end):
        self.cancelled.append((subscription_id, at_cycle_end))


def provider_from_env() -> BillingProvider:
    """Razorpay when both keys are set, otherwise the mock (never silently live)."""
    kind = os.getenv("ANKANA_BILLING_PROVIDER", "").lower()
    key_id, secret = os.getenv("RAZORPAY_KEY_ID", ""), os.getenv("RAZORPAY_KEY_SECRET", "")
    if kind == "razorpay" or (not kind and key_id and secret):
        if not (key_id and secret):
            raise ProviderError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required")
        return RazorpayProvider(key_id, secret)
    return MockProvider()
