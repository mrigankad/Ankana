"""Shared types for every outbound channel (email, WhatsApp, SMS)."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

CHANNEL_KINDS = ("email", "whatsapp", "sms")
DELIVERY_STATUSES = ("sent", "delivered", "read", "failed")
_RANK = {"sent": 1, "delivered": 2, "read": 3}


@dataclass(frozen=True)
class Message:
    """One outbound message. `kind` is the notification kind ("remedy_due", "otp", ...):
    WhatsApp and SMS use it to pick the approved template. `session=True` asks WhatsApp
    for a free-form session message (only valid inside the 24h customer-care window)."""

    to: str
    body: str
    subject: str | None = None
    language: str = "en"
    unsubscribe_url: str | None = None
    html: str | None = None
    kind: str | None = None
    session: bool = False


@dataclass(frozen=True)
class SendResult:
    provider: str
    message_id: str | None = None


@dataclass(frozen=True)
class StatusEvent:
    """A delivery receipt from a provider webhook."""

    provider: str
    message_id: str
    status: str  # sent | delivered | read | failed
    error: str | None = None


@dataclass(frozen=True)
class InboundEvent:
    """A reply sent by the end user to the business number."""

    provider: str
    sender: str
    text: str


class ChannelError(Exception):
    """A send that failed. `retryable` tells the job queue whether a retry can help
    (rate limit, provider outage) or not (bad number, unapproved template)."""

    def __init__(self, message: str, *, retryable: bool = True, code: str | None = None) -> None:
        super().__init__(message)
        self.retryable, self.code = retryable, code


class Channel(Protocol):
    kind: str
    name: str

    def send(self, msg: Message) -> SendResult: ...


def mask(to: str) -> str:
    if "@" in to:
        local, _, domain = to.partition("@")
        return f"{local[:1]}***@{domain}"
    return "***" + to[-3:] if len(to) > 3 else "***"


def is_production() -> bool:
    return os.getenv("API_ENV", "dev").lower() == "production"


def should_apply(current: str | None, new: str) -> bool:
    """Webhooks arrive out of order and are redelivered: only move a status forward.
    `failed` beats `sent` (or nothing) but never overwrites delivered/read."""
    if new == "failed":
        return current in (None, "sent")
    return _RANK.get(new, 0) > _RANK.get(current or "", 0)


def phone_digits(phone: str, default_cc: str | None = None) -> str:
    """Digits only, with the country code. A bare 10 digit national number gets
    `default_cc` (MESSAGING_DEFAULT_COUNTRY_CODE, 91 for India)."""
    cc = os.getenv("MESSAGING_DEFAULT_COUNTRY_CODE", "91") if default_cc is None else default_cc
    digits = re.sub(r"\D", "", phone)
    if phone.strip().startswith("00"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if cc and len(digits) == 10:
        digits = cc + digits
    return digits


class Http:
    """httpx wrapper with bounded retries and `Retry-After`. Only failures where the
    provider cannot have accepted the message are retried (connect errors, 429, 502,
    503, 504); a read timeout is not, because a retry could send twice."""

    RETRY_STATUS = frozenset({429, 502, 503, 504})

    def __init__(self, client: httpx.Client | None = None, *, retries: int = 2,
                 backoff: float = 0.5, timeout: float = 15.0, sleep=time.sleep) -> None:
        self.client = client or httpx.Client(timeout=timeout)
        self.retries, self.backoff, self.sleep = retries, backoff, sleep

    def request(self, method: str, url: str, **kw) -> httpx.Response:
        for attempt in range(self.retries + 1):
            last = attempt == self.retries
            try:
                resp = self.client.request(method, url, **kw)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if last:
                    raise ChannelError(f"connection failed: {type(exc).__name__}") from exc
                self.sleep(self.backoff * 2 ** attempt)
                continue
            except httpx.HTTPError as exc:
                raise ChannelError(f"http error: {type(exc).__name__}") from exc
            if resp.status_code in self.RETRY_STATUS and not last:
                wait = self.backoff * 2 ** attempt
                ra = resp.headers.get("Retry-After", "")
                if ra.isdigit():
                    wait = min(float(ra), 30.0)
                self.sleep(wait)
                continue
            return resp
        raise AssertionError("unreachable")  # pragma: no cover


def http_error(provider: str, resp: httpx.Response, detail: str | None = None,
               code: str | None = None) -> ChannelError:
    retry = resp.status_code == 429 or resp.status_code >= 500
    suffix = f": {detail[:160]}" if detail else ""
    return ChannelError(f"{provider} returned {resp.status_code}{suffix}", retryable=retry,
                        code=code)


def safe_json(resp: httpx.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
