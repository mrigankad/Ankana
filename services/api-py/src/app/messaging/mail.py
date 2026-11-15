"""Email backends: SMTP, and Azure Communication Services (REST, or the optional SDK)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from urllib.parse import urlparse

from .base import ChannelError, Http, Message, SendResult, http_error


def bare_address(sender: str) -> str:
    """'Name <addr>' or a bare address -> the address."""
    return sender.rsplit("<", 1)[-1].rstrip(">").strip()


class SmtpEmailChannel:
    kind = "email"
    name = "smtp"

    def __init__(self, host: str, port: int = 587, user: str | None = None,
                 password: str | None = None, sender: str = "reminders@localhost",
                 starttls: bool = True) -> None:
        self.host, self.port, self.user, self.password = host, port, user, password
        self.sender, self.starttls = sender, starttls

    def build(self, msg: Message) -> EmailMessage:
        m = EmailMessage()
        try:  # CR/LF in a header value is refused by the stdlib: a failed message, not a 500
            m["From"], m["To"], m["Subject"] = self.sender, msg.to, msg.subject or "Reminder"
            if msg.unsubscribe_url:
                m["List-Unsubscribe"] = f"<{msg.unsubscribe_url}>"
            m.set_content(msg.body)
            if msg.html:
                m.add_alternative(msg.html, subtype="html")
        except ValueError as exc:
            raise ChannelError(f"invalid message: {exc}", retryable=False) from exc
        return m

    def send(self, msg: Message) -> SendResult:
        built = self.build(msg)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as s:
                if self.starttls:
                    s.starttls()
                if self.user:
                    s.login(self.user, self.password or "")
                s.send_message(built)
        except (OSError, smtplib.SMTPException) as exc:
            raise ChannelError(f"smtp: {type(exc).__name__}: {exc}") from exc
        return SendResult(self.name)


class AcsEmailChannel:
    """POST {endpoint}/emails:send with the ACS HMAC-SHA256 scheme (no SDK needed).
    `use_sdk=True` sends through `azure-communication-email` instead (optional extra
    `azure-email`)."""

    kind = "email"
    name = "acs"
    API = "2023-03-31"

    def __init__(self, connection_string: str, sender: str, *, http: Http | None = None,
                 use_sdk: bool = False) -> None:
        self.connection_string, self.use_sdk = connection_string, use_sdk
        parts = dict(p.split("=", 1) for p in connection_string.split(";") if "=" in p)
        try:
            self.endpoint = parts["endpoint"].rstrip("/")
            self.key = base64.b64decode(parts["accesskey"])
        except (KeyError, ValueError) as exc:
            raise RuntimeError("ACS connection string needs endpoint= and accesskey=") from exc
        self.sender = bare_address(sender)
        self.http = http or Http()

    def payload(self, msg: Message) -> dict:
        content = {"subject": msg.subject or "Reminder", "plainText": msg.body}
        if msg.html:
            content["html"] = msg.html
        payload: dict = {"senderAddress": self.sender,
                         "recipients": {"to": [{"address": msg.to}]}, "content": content}
        if msg.unsubscribe_url:
            payload["headers"] = {"List-Unsubscribe": f"<{msg.unsubscribe_url}>"}
        return payload

    def send(self, msg: Message) -> SendResult:
        if self.use_sdk:
            return self._send_sdk(msg)
        body = json.dumps(self.payload(msg)).encode()
        path = f"/emails:send?api-version={self.API}"
        host = urlparse(self.endpoint).netloc
        date = datetime.now(tz=UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
        content_hash = base64.b64encode(hashlib.sha256(body).digest()).decode()
        to_sign = f"POST\n{path}\n{date};{host};{content_hash}"
        sig = base64.b64encode(hmac.new(self.key, to_sign.encode(), hashlib.sha256).digest()).decode()
        headers = {
            "x-ms-date": date, "x-ms-content-sha256": content_hash,
            "Content-Type": "application/json",
            "Authorization": "HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256"
                             f"&Signature={sig}",
        }
        resp = self.http.request("POST", self.endpoint + path, content=body, headers=headers)
        if resp.status_code >= 300:
            raise http_error("ACS email", resp)
        try:
            mid = resp.json().get("id")
        except (ValueError, AttributeError):
            mid = None
        return SendResult(self.name, mid)

    def _send_sdk(self, msg: Message) -> SendResult:
        try:
            from azure.communication.email import EmailClient
        except ImportError as exc:
            raise ChannelError("azure-communication-email is not installed "
                               "(pip install 'nakshatra-api[azure-email]')",
                               retryable=False) from exc
        try:
            poller = EmailClient.from_connection_string(self.connection_string) \
                .begin_send(self.payload(msg))
            result = poller.result()
        except Exception as exc:  # the SDK raises several types
            raise ChannelError(f"acs: {type(exc).__name__}") from exc
        return SendResult(self.name, str(result.get("id")) if isinstance(result, dict) else None)
