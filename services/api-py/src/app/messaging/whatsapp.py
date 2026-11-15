"""WhatsApp: Meta WhatsApp Cloud API (primary) and Gupshup (alternative).

Business-initiated messages (reminders) must use a template that Meta has approved;
free-form "session" messages work only inside the 24 hour window after the customer
last wrote to you. Both adapters send a template when one is mapped for the message
kind (WHATSAPP_TEMPLATES) and `Message.session` is false, otherwise a session text.

Every approved template is expected to have ONE body variable, {{1}}, which receives
the rendered reminder text (newlines are folded because Meta rejects them in
parameters). Register it as category UTILITY, one template per language.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from .base import (
    ChannelError,
    Http,
    InboundEvent,
    Message,
    SendResult,
    StatusEvent,
    http_error,
    phone_digits,
    safe_json,
)

# Meta error codes (https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes)
_META_RETRYABLE = {"130429", "131056", "80007", "131000", "131016", "368"}
_META_PERMANENT = {
    "131047": "outside the 24h window: needs an approved template",
    "131026": "recipient cannot receive WhatsApp messages",
    "131049": "Meta limited marketing delivery to this user",
    "132000": "template parameter count mismatch",
    "132001": "template does not exist in this language",
    "132005": "translated text too long",
    "132007": "template violates Meta policy",
    "132012": "template parameter format mismatch",
    "132015": "template is paused",
    "132016": "template is disabled",
    "190": "access token expired or invalid",
}


@dataclass(frozen=True)
class WaTemplate:
    name: str
    language: str  # the code Meta knows the template under ("en", "hi", "en_US")
    id: str | None = None  # Gupshup template UUID


class WaTemplates:
    """kind -> language -> template, from WHATSAPP_TEMPLATES JSON, e.g.
    {"remedy_due": {"en": {"name": "remedy_due_en", "language": "en"},
                    "hi": {"name": "remedy_due_hi", "language": "hi"}}}"""

    def __init__(self, mapping: dict | None = None) -> None:
        self.map: dict[str, dict[str, WaTemplate]] = {}
        for kind, langs in (mapping or {}).items():
            self.map[kind] = {
                lang: WaTemplate(v["name"], v.get("language", lang), v.get("id"))
                for lang, v in langs.items()}

    @classmethod
    def from_json(cls, raw: str | None) -> WaTemplates:
        if not raw:
            return cls()
        try:
            return cls(json.loads(raw))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise RuntimeError(f"WHATSAPP_TEMPLATES is not valid: {exc}") from exc

    def get(self, kind: str | None, language: str) -> WaTemplate | None:
        langs = self.map.get(kind or "")
        if not langs:
            return None
        return langs.get(language) or langs.get("en")


def fold(text: str) -> str:
    """One line, no runs of spaces: what Meta accepts as a template parameter."""
    text = re.sub(r"\s*\n+\s*", " | ", text.strip())
    return re.sub(r" {2,}", " ", text.replace("\t", " "))


class MetaWhatsApp:
    kind = "whatsapp"
    name = "meta"

    def __init__(self, token: str, phone_number_id: str, *, templates: WaTemplates | None = None,
                 graph_version: str = "v21.0", http: Http | None = None,
                 base_url: str = "https://graph.facebook.com") -> None:
        self.token, self.phone_number_id = token, phone_number_id
        self.templates = templates or WaTemplates()
        self.url = f"{base_url.rstrip('/')}/{graph_version}/{phone_number_id}/messages"
        self.http = http or Http()

    def payload(self, msg: Message) -> dict:
        base = {"messaging_product": "whatsapp", "recipient_type": "individual",
                "to": phone_digits(msg.to)}
        tpl = None if msg.session else self.templates.get(msg.kind, msg.language)
        if tpl is None:
            return {**base, "type": "text", "text": {"body": msg.body, "preview_url": False}}
        return {**base, "type": "template", "template": {
            "name": tpl.name, "language": {"code": tpl.language},
            "components": [{"type": "body",
                            "parameters": [{"type": "text", "text": fold(msg.body)}]}]}}

    def send(self, msg: Message) -> SendResult:
        resp = self.http.request("POST", self.url, json=self.payload(msg),
                                 headers={"Authorization": f"Bearer {self.token}"})
        data = safe_json(resp)
        if resp.status_code >= 300:
            err = data.get("error") or {}
            code = str(err.get("code", ""))
            if code in _META_PERMANENT:
                raise ChannelError(f"meta {code}: {_META_PERMANENT[code]}", retryable=False,
                                   code=code)
            exc = http_error("meta whatsapp", resp, str(err.get("message", "")), code or None)
            if code in _META_RETRYABLE:
                exc.retryable = True
            raise exc
        msgs = data.get("messages") or [{}]
        return SendResult(self.name, msgs[0].get("id"))


# ------------------------------------------------------------------ Meta webhooks
def verify_meta_signature(app_secret: str, raw_body: bytes, header: str | None) -> bool:
    """X-Hub-Signature-256: 'sha256=' + HMAC-SHA256(app secret, raw request body)."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):].strip())


def verify_meta_challenge(verify_token: str, mode: str | None, token: str | None,
                          challenge: str | None) -> str | None:
    """GET subscription handshake: echo hub.challenge when the verify token matches."""
    if (verify_token and mode == "subscribe" and token
            and hmac.compare_digest(token, verify_token)):
        return challenge
    return None


def parse_meta_webhook(payload: dict) -> tuple[list[StatusEvent], list[InboundEvent]]:
    statuses: list[StatusEvent] = []
    inbound: list[InboundEvent] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for s in value.get("statuses") or []:
                status = s.get("status")
                if status not in ("sent", "delivered", "read", "failed") or not s.get("id"):
                    continue  # e.g. "deleted", "warning"
                errs = s.get("errors") or []
                err = None
                if errs:
                    err = f"{errs[0].get('code', '')} {errs[0].get('title', '')}".strip()
                statuses.append(StatusEvent("meta", s["id"], status, err))
            for m in value.get("messages") or []:
                text = ""
                if m.get("type") == "text":
                    text = (m.get("text") or {}).get("body", "")
                elif m.get("type") == "button":
                    text = (m.get("button") or {}).get("text", "")
                elif m.get("type") == "interactive":
                    reply = (m.get("interactive") or {}).get("button_reply") or {}
                    text = reply.get("title", "")
                if m.get("from") and text:
                    inbound.append(InboundEvent("meta", m["from"], text))
    return statuses, inbound


# ------------------------------------------------------------------------ Gupshup
class GupshupWhatsApp:
    """Gupshup WhatsApp API (self-serve, https://api.gupshup.io/wa/api/v1)."""

    kind = "whatsapp"
    name = "gupshup"

    def __init__(self, api_key: str, source: str, app_name: str, *,
                 templates: WaTemplates | None = None, http: Http | None = None,
                 base_url: str = "https://api.gupshup.io") -> None:
        self.api_key, self.source, self.app_name = api_key, source, app_name
        self.templates = templates or WaTemplates()
        self.base = base_url.rstrip("/")
        self.http = http or Http()

    def form(self, msg: Message) -> tuple[str, dict]:
        data = {"channel": "whatsapp", "source": phone_digits(self.source),
                "destination": phone_digits(msg.to), "src.name": self.app_name}
        tpl = None if msg.session else self.templates.get(msg.kind, msg.language)
        if tpl is None or not tpl.id:
            data["message"] = json.dumps({"type": "text", "text": msg.body})
            return "/wa/api/v1/msg", data
        data["template"] = json.dumps({"id": tpl.id, "params": [fold(msg.body)]})
        return "/wa/api/v1/template/msg", data

    def send(self, msg: Message) -> SendResult:
        path, data = self.form(msg)
        resp = self.http.request("POST", self.base + path, data=data,
                                 headers={"apikey": self.api_key})
        body = safe_json(resp)
        if resp.status_code >= 300:
            raise http_error("gupshup", resp, str(body.get("message", "")))
        if body.get("status") not in ("submitted", "success"):
            raise ChannelError(f"gupshup rejected: {str(body.get('message', ''))[:160]}",
                               retryable=False)
        return SendResult(self.name, body.get("messageId"))


def verify_shared_token(expected: str, supplied: str | None) -> bool:
    """Gupshup, MSG91 and similar providers do not sign callbacks: the callback URL
    carries a long random token that we compare in constant time."""
    return bool(expected) and bool(supplied) and hmac.compare_digest(expected, supplied or "")


_GUPSHUP_STATUS = {"sent": "sent", "delivered": "delivered", "read": "read", "failed": "failed"}


def parse_gupshup_webhook(payload: dict) -> tuple[list[StatusEvent], list[InboundEvent]]:
    """Gupshup v2 callbacks: type 'message-event' (payload.type enqueued|sent|delivered|
    read|failed, payload.gsId / payload.id) and type 'message' (an inbound reply)."""
    statuses: list[StatusEvent] = []
    inbound: list[InboundEvent] = []
    inner = payload.get("payload") or {}
    if payload.get("type") == "message-event":
        status = _GUPSHUP_STATUS.get(str(inner.get("type", "")).lower())
        err = None
        if status == "failed":
            detail = inner.get("payload") or {}
            err = f"{detail.get('code', '')} {detail.get('reason', '')}".strip() or None
        # The id we stored is the one send() returned; Gupshup reports it as gsId or id
        # depending on the event, so emit both and let the lookup match whichever it knows.
        for mid in dict.fromkeys(x for x in (inner.get("gsId"), inner.get("id")) if x):
            if status:
                statuses.append(StatusEvent("gupshup", mid, status, err))
    elif payload.get("type") == "message":
        text = ((inner.get("payload") or {}).get("text")
                or (inner.get("payload") or {}).get("title") or "")
        if inner.get("source") and text:
            inbound.append(InboundEvent("gupshup", inner["source"], text))
    return statuses, inbound
