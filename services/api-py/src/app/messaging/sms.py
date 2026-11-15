"""SMS: MSG91 (India, DLT) and Twilio (alternative).

India (TRAI) only delivers SMS that match a DLT-registered template, sent from a
registered header (sender id) by a registered entity. MSG91 therefore needs a sender id
and a DLT template id on every request, and the message text must match the registered
template (variables aside). Template ids come from MSG91_DLT_TEMPLATES (kind -> id) with
MSG91_DLT_TEMPLATE_ID as the fallback; sign-in codes use kind "otp".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import quote

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


class Msg91Sms:
    kind = "sms"
    name = "msg91"
    URL = "https://api.msg91.com/api/v2/sendsms"

    def __init__(self, auth_key: str, sender_id: str, *, default_template_id: str | None = None,
                 templates: dict[str, str] | None = None, route: str = "4",
                 country: str = "91", http: Http | None = None, url: str | None = None) -> None:
        if not auth_key or not sender_id:
            raise RuntimeError("msg91 needs MSG91_AUTH_KEY and MSG91_SENDER_ID")
        self.auth_key, self.sender_id, self.route, self.country = auth_key, sender_id, route, country
        self.default_template_id, self.templates = default_template_id, templates or {}
        self.http, self.url = http or Http(), url or self.URL

    def template_id(self, kind: str | None) -> str:
        tid = self.templates.get(kind or "") or self.default_template_id
        if not tid:
            raise ChannelError(f"no DLT template id for sms kind {kind!r}", retryable=False)
        return tid

    def payload(self, msg: Message) -> dict:
        return {"sender": self.sender_id, "route": self.route, "country": self.country,
                "DLT_TE_ID": self.template_id(msg.kind),
                "sms": [{"message": msg.body, "to": [phone_digits(msg.to, self.country)]}]}

    def send(self, msg: Message) -> SendResult:
        resp = self.http.request("POST", self.url, json=self.payload(msg),
                                 headers={"authkey": self.auth_key})
        data = safe_json(resp)
        if resp.status_code >= 300:
            raise http_error("msg91", resp, str(data.get("message", "")))
        # MSG91 answers 200 with {"type": "error"} for rejected requests
        if str(data.get("type", "")).lower() != "success":
            raise ChannelError(f"msg91 rejected: {str(data.get('message', ''))[:160]}",
                               retryable=False)
        return SendResult(self.name, str(data.get("message")) or None)


_MSG91_DELIVERED = {"1", "delivered"}
_MSG91_FAILED = {"2", "failed", "rejected", "blocked", "ndnc", "expired", "undelivered"}


def parse_msg91_report(payload: object) -> list[StatusEvent]:
    """MSG91 delivery-report push: a JSON object (or list of them) like
    {"requestId": "...", "report": [{"number": "91...", "status": "1", "desc": "DELIVERED"}]}.
    Status 1 / DELIVERED is delivered; 2 and the rejection family are failures. Unknown
    codes are ignored rather than guessed."""
    items = payload if isinstance(payload, list) else [payload]
    out: list[StatusEvent] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("requestId"):
            continue
        for row in item.get("report") or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("status", "")).strip().lower()
            desc = str(row.get("desc", "")).strip().lower()
            for token in (code, desc):
                if token in _MSG91_DELIVERED:
                    out.append(StatusEvent("msg91", str(item["requestId"]), "delivered"))
                    break
                if token in _MSG91_FAILED:
                    out.append(StatusEvent("msg91", str(item["requestId"]), "failed",
                                           (desc or code)[:120]))
                    break
    return out


class TwilioSms:
    kind = "sms"
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, *, from_number: str | None = None,
                 messaging_service_sid: str | None = None, status_callback: str | None = None,
                 http: Http | None = None, base_url: str = "https://api.twilio.com") -> None:
        if not account_sid or not auth_token or not (from_number or messaging_service_sid):
            raise RuntimeError("twilio needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and "
                               "TWILIO_FROM or TWILIO_MESSAGING_SERVICE_SID")
        self.sid, self.token = account_sid, auth_token
        self.from_number, self.service_sid = from_number, messaging_service_sid
        self.status_callback = status_callback
        self.url = f"{base_url.rstrip('/')}/2010-04-01/Accounts/{quote(account_sid)}/Messages.json"
        self.http = http or Http()

    def form(self, msg: Message) -> dict:
        data = {"To": "+" + phone_digits(msg.to), "Body": msg.body}
        if self.service_sid:
            data["MessagingServiceSid"] = self.service_sid
        else:
            data["From"] = self.from_number or ""
        if self.status_callback:
            data["StatusCallback"] = self.status_callback
        return data

    def send(self, msg: Message) -> SendResult:
        resp = self.http.request("POST", self.url, data=self.form(msg), auth=(self.sid, self.token))
        data = safe_json(resp)
        if resp.status_code >= 300:
            code = str(data.get("code", "")) or None
            exc = http_error("twilio", resp, str(data.get("message", "")), code)
            # 4xx other than 429 are permanent (invalid number 21211, opted out 21610, ...)
            raise exc
        return SendResult(self.name, data.get("sid"))


def twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """X-Twilio-Signature: base64(HMAC-SHA1(auth token, url + sorted key+value pairs))."""
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
                            ).decode()


def verify_twilio_signature(auth_token: str, url: str, params: dict[str, str],
                            header: str | None) -> bool:
    if not auth_token or not header:
        return False
    return hmac.compare_digest(twilio_signature(auth_token, url, params), header)


_TWILIO_STATUS = {"queued": "sent", "accepted": "sent", "sending": "sent", "sent": "sent",
                  "delivered": "delivered", "read": "read", "undelivered": "failed",
                  "failed": "failed"}


def parse_twilio_webhook(params: dict[str, str]) -> tuple[list[StatusEvent], list[InboundEvent]]:
    """Status callbacks carry MessageSid + MessageStatus; inbound replies carry From + Body
    (and no MessageStatus)."""
    sid, status = params.get("MessageSid") or params.get("SmsSid"), params.get("MessageStatus")
    if status and sid:
        mapped = _TWILIO_STATUS.get(status.lower())
        if mapped:
            err = params.get("ErrorCode") or None
            return [StatusEvent("twilio", sid, mapped, f"twilio {err}" if err else None)], []
        return [], []
    if params.get("From") and params.get("Body"):
        return [], [InboundEvent("twilio", params["From"].removeprefix("whatsapp:"), params["Body"])]
    return [], []


__all__ = ["Msg91Sms", "TwilioSms", "parse_msg91_report", "parse_twilio_webhook",
           "twilio_signature", "verify_twilio_signature"]
