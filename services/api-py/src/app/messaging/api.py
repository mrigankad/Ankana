"""Public provider webhooks: delivery receipts and inbound replies.

Every endpoint fails closed: when the secret for a provider is not configured it answers
503, and a missing or wrong signature or token answers 403 before the body is parsed.
Responses never echo provider data.

    GET/POST /v1/webhooks/whatsapp/meta     X-Hub-Signature-256, WHATSAPP_APP_SECRET,
                                            GET handshake WHATSAPP_VERIFY_TOKEN
    POST     /v1/webhooks/whatsapp/gupshup  ?token= GUPSHUP_WEBHOOK_TOKEN
    POST     /v1/webhooks/sms/twilio        X-Twilio-Signature, TWILIO_AUTH_TOKEN
    POST     /v1/webhooks/sms/msg91         ?token= MSG91_WEBHOOK_TOKEN
"""

from __future__ import annotations

import json
import logging
import os
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .base import InboundEvent, StatusEvent
from .inbound import apply_opt_out, apply_status
from .sms import parse_msg91_report, parse_twilio_webhook, verify_twilio_signature
from .whatsapp import (
    parse_gupshup_webhook,
    parse_meta_webhook,
    verify_meta_challenge,
    verify_meta_signature,
    verify_shared_token,
)

log = logging.getLogger("app.messaging.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)


def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise HTTPException(503, "webhook not configured")
    return value


def _process(request: Request, statuses: list[StatusEvent],
             inbound: list[InboundEvent]) -> dict:
    engine = request.app.state.pg_engine
    updated = sum(apply_status(engine, s) for s in statuses)
    stopped = sum(apply_opt_out(engine, i) for i in inbound)
    log.info("webhook statuses=%d updated=%d inbound=%d opted_out=%d",
             len(statuses), updated, len(inbound), stopped)
    return {"ok": True}


def _json(raw: bytes) -> dict:
    try:
        data = json.loads(raw or b"{}")
    except ValueError as exc:
        raise HTTPException(400, "invalid json") from exc
    return data if isinstance(data, dict) else {}


@router.get("/whatsapp/meta")
def meta_handshake(request: Request) -> PlainTextResponse:
    q = request.query_params
    challenge = verify_meta_challenge(_secret("WHATSAPP_VERIFY_TOKEN"), q.get("hub.mode"),
                                      q.get("hub.verify_token"), q.get("hub.challenge"))
    if challenge is None:
        raise HTTPException(403, "verification failed")
    return PlainTextResponse(challenge)


@router.post("/whatsapp/meta")
async def meta_webhook(request: Request) -> dict:
    raw = await request.body()
    if not verify_meta_signature(_secret("WHATSAPP_APP_SECRET"), raw,
                                 request.headers.get("x-hub-signature-256")):
        raise HTTPException(403, "bad signature")
    return _process(request, *parse_meta_webhook(_json(raw)))


@router.post("/whatsapp/gupshup")
async def gupshup_webhook(request: Request) -> dict:
    raw = await request.body()
    if not verify_shared_token(_secret("GUPSHUP_WEBHOOK_TOKEN"), request.query_params.get("token")):
        raise HTTPException(403, "bad token")
    return _process(request, *parse_gupshup_webhook(_json(raw)))


def _public_url(request: Request, path: str) -> str:
    base = os.getenv("MESSAGING_PUBLIC_BASE_URL", "").rstrip("/")
    if base:
        url = base + path
        return url + (f"?{request.url.query}" if request.url.query else "")
    return str(request.url)


@router.post("/sms/twilio")
async def twilio_webhook(request: Request) -> dict:
    raw = await request.body()
    params = dict(parse_qsl(raw.decode("utf-8", "replace"), keep_blank_values=True))
    url = _public_url(request, "/v1/webhooks/sms/twilio")
    if not verify_twilio_signature(_secret("TWILIO_AUTH_TOKEN"), url, params,
                                   request.headers.get("x-twilio-signature")):
        raise HTTPException(403, "bad signature")
    return _process(request, *parse_twilio_webhook(params))


@router.post("/sms/msg91")
async def msg91_webhook(request: Request) -> dict:
    raw = await request.body()
    if not verify_shared_token(_secret("MSG91_WEBHOOK_TOKEN"), request.query_params.get("token")):
        raise HTTPException(403, "bad token")
    try:
        payload = json.loads(raw or b"[]")
    except ValueError as exc:
        raise HTTPException(400, "invalid json") from exc
    return _process(request, parse_msg91_report(payload), [])
