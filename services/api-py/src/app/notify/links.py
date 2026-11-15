"""Signed, expiring links for the public one-tap pages.

Token = base64url(json payload) + "." + base64url(HMAC-SHA256). The MAC covers the
purpose, so a check-in token cannot be replayed as a stop token. The payload carries
ids and an expiry only (no PII). Secret: NOTIFY_LINK_SECRET (required when
API_ENV=production; a fixed dev value otherwise).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta

_DEV_SECRET = b"ankana-dev-only-notify-link-secret"


class LinkError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code  # malformed | bad_signature | expired | wrong_purpose


def _secret() -> bytes:
    raw = os.getenv("NOTIFY_LINK_SECRET")
    if raw:
        return raw.encode()
    if os.getenv("API_ENV", "dev") == "production":
        raise RuntimeError("NOTIFY_LINK_SECRET must be set when API_ENV=production")
    return _DEV_SECRET


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(purpose: str, body: str) -> str:
    return _b64(hmac.new(_secret(), f"{purpose}.{body}".encode(), hashlib.sha256).digest())


def sign(purpose: str, data: dict, ttl: timedelta, now: datetime | None = None) -> str:
    now = now or datetime.now(tz=UTC)
    payload = {**data, "exp": int((now + ttl).timestamp())}
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    return f"{body}.{_mac(purpose, body)}"


def verify(token: str, purpose: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(tz=UTC)
    body, dot, sig = token.partition(".")
    if not dot or not body or not sig or len(token) > 1024:
        raise LinkError("malformed")
    if not hmac.compare_digest(sig, _mac(purpose, body)):
        raise LinkError("bad_signature")
    try:
        payload = json.loads(_unb64(body))
        exp = int(payload["exp"])
    except Exception:
        raise LinkError("malformed") from None
    if now.timestamp() > exp:
        raise LinkError("expired")
    return payload


def public_base_url() -> str:
    return os.getenv("NOTIFY_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


CHECKIN_TTL = timedelta(hours=36)
STOP_TTL = timedelta(days=365)


def checkin_url(practice_id, client_id, plan_id, day, language: str = "en",
                now: datetime | None = None) -> str:
    token = sign("checkin", {"p": str(practice_id), "c": str(client_id), "pl": str(plan_id),
                             "d": day.isoformat(), "l": language}, CHECKIN_TTL, now)
    return f"{public_base_url()}/v1/public/checkin/{token}"


def stop_url(practice_id, client_id, language: str = "en", now: datetime | None = None) -> str:
    token = sign("stop", {"p": str(practice_id), "c": str(client_id), "l": language},
                 STOP_TTL, now)
    return f"{public_base_url()}/v1/public/stop/{token}"
