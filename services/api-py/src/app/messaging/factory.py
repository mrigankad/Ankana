"""Backend selection from the environment.

    NOTIFY_EMAIL_BACKEND     console | smtp | acs
    NOTIFY_WHATSAPP_BACKEND  console | meta | gupshup
    NOTIFY_SMS_BACKEND       console | msg91 | twilio

Credentials and options are read from the variables listed in docs/deploy.md. In
production (API_ENV=production) the console backend is refused for SMS and WhatsApp,
because it would swallow real reminders silently.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

from .base import CHANNEL_KINDS, Channel, ChannelError, Http, Message, SendResult, is_production
from .console import ConsoleChannel
from .mail import AcsEmailChannel, SmtpEmailChannel
from .sms import Msg91Sms, TwilioSms
from .whatsapp import GupshupWhatsApp, MetaWhatsApp, WaTemplates

BACKENDS = {
    "email": ("console", "smtp", "acs"),
    "whatsapp": ("console", "meta", "gupshup"),
    "sms": ("console", "msg91", "twilio"),
}


class OffChannel:
    """NOTIFY_<KIND>_BACKEND=off: nothing is sent and every attempt fails permanently, so
    the outbox shows why instead of silently dropping the reminder."""

    name = "off"

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def send(self, msg: Message) -> SendResult:
        raise ChannelError(f"{self.kind} channel is switched off", retryable=False)


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    return default if raw in (None, "") else raw.lower() in {"1", "true", "yes", "on"}


def _need(env: Mapping[str, str], backend_var: str, *names: str) -> list[str]:
    values = [env.get(n, "") for n in names]
    missing = [n for n, v in zip(names, values, strict=True) if not v]
    if missing:
        raise RuntimeError(f"{backend_var} needs {', '.join(missing)}")
    return values


def refuse_console_in_production(kind: str, backend: str, production: bool | None = None) -> None:
    prod = is_production() if production is None else production
    if prod and backend == "console" and kind in ("sms", "whatsapp"):
        raise RuntimeError(
            f"NOTIFY_{kind.upper()}_BACKEND=console is not allowed in production "
            f"(use one of {', '.join(b for b in BACKENDS[kind] if b != 'console')})")


def build_channel(kind: str, backend: str, env: Mapping[str, str] | None = None, *,
                  http: Http | None = None, production: bool | None = None) -> Channel:
    """One channel for `kind` and `backend`. `http` is injected by tests."""
    env = os.environ if env is None else env
    if kind not in CHANNEL_KINDS or backend not in (*BACKENDS[kind], "off"):
        raise RuntimeError(f"unsupported {kind} backend: {backend}")
    if backend == "off":
        return OffChannel(kind)
    refuse_console_in_production(kind, backend, production)
    var = f"NOTIFY_{kind.upper()}_BACKEND"
    if backend == "console":
        return ConsoleChannel(kind)
    if kind == "email":
        if backend == "smtp":
            (host,) = _need(env, f"{var}=smtp", "SMTP_HOST")
            return SmtpEmailChannel(
                host, int(env.get("SMTP_PORT") or 587), env.get("SMTP_USER") or None,
                env.get("SMTP_PASSWORD") or None,
                env.get("NOTIFY_EMAIL_FROM") or "reminders@localhost",
                _flag(env, "SMTP_STARTTLS", True))
        conn = env.get("ACS_EMAIL_CONNECTION_STRING") or env.get("ACS_CONNECTION_STRING") or ""
        sender = env.get("ACS_EMAIL_FROM") or env.get("NOTIFY_EMAIL_FROM") or ""
        if not conn or not sender:
            raise RuntimeError(f"{var}=acs needs ACS_EMAIL_CONNECTION_STRING "
                               "and ACS_EMAIL_FROM")
        return AcsEmailChannel(conn, sender, http=http,
                               use_sdk=_flag(env, "ACS_EMAIL_USE_SDK", False))
    if kind == "whatsapp":
        templates = WaTemplates.from_json(env.get("WHATSAPP_TEMPLATES"))
        if backend == "meta":
            token, pnid = _need(env, f"{var}=meta", "WHATSAPP_CLOUD_TOKEN",
                                "WHATSAPP_PHONE_NUMBER_ID")
            return MetaWhatsApp(token, pnid, templates=templates, http=http,
                                graph_version=env.get("WHATSAPP_GRAPH_VERSION") or "v21.0")
        key, source, app = _need(env, f"{var}=gupshup", "GUPSHUP_API_KEY", "GUPSHUP_SOURCE",
                                 "GUPSHUP_APP_NAME")
        return GupshupWhatsApp(key, source, app, templates=templates, http=http)
    if backend == "msg91":
        key, sender = _need(env, f"{var}=msg91", "MSG91_AUTH_KEY", "MSG91_SENDER_ID")
        try:
            per_kind = json.loads(env.get("MSG91_DLT_TEMPLATES") or "{}")
        except ValueError as exc:
            raise RuntimeError("MSG91_DLT_TEMPLATES is not valid JSON") from exc
        return Msg91Sms(key, sender, default_template_id=env.get("MSG91_DLT_TEMPLATE_ID") or None,
                        templates=per_kind, http=http)
    sid, token = _need(env, f"{var}=twilio", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN")
    return TwilioSms(sid, token, from_number=env.get("TWILIO_FROM") or None,
                     messaging_service_sid=env.get("TWILIO_MESSAGING_SERVICE_SID") or None,
                     status_callback=env.get("TWILIO_STATUS_CALLBACK_URL") or None, http=http)


def assert_production_ready(env: Mapping[str, str] | None = None) -> None:
    """Startup check for the worker: in production, sms and whatsapp must name a real
    backend (or `off`, which sends nothing and fails those notifications)."""
    env = os.environ if env is None else env
    if not is_production():
        return
    for kind in ("sms", "whatsapp"):
        backend = env.get(f"NOTIFY_{kind.upper()}_BACKEND", "console").lower()
        if backend != "off":
            refuse_console_in_production(kind, backend, True)
            build_channel(kind, backend, env, production=True)
