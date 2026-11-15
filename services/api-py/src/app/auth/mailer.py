"""Sign-in codes and invitations: a thin adapter over `app.messaging`.

Mailers: console (dev, prints to the API log), SMTP, Azure Communication Services email.
SMS (phone codes): console in dev, MSG91 or Twilio via AUTH_SMS (credentials and the DLT
template id for kind "otp" come from the same env as the notification SMS backend, see
docs/deploy.md). Failures raise MailError; callers never leak the reason to the end user.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

from app.messaging import (
    AcsEmailChannel,
    ChannelError,
    ConsoleChannel,
    SmtpEmailChannel,
    build_channel,
)
from app.messaging import Message as ChannelMessage

from .config import AuthConfig

log = logging.getLogger("ankana.auth.mail")

MailError = ChannelError


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    html: str | None = None


class Mailer(Protocol):
    def send(self, message: Message) -> None: ...


class SmsSender(Protocol):
    def send(self, to: str, text: str) -> None: ...


class ChannelMailer:
    def __init__(self, channel) -> None:
        self.channel = channel

    def send(self, message: Message) -> None:
        self.channel.send(ChannelMessage(to=message.to, body=message.text,
                                         subject=message.subject, html=message.html,
                                         kind="auth"))


class ChannelSms:
    def __init__(self, channel) -> None:
        self.channel = channel

    def send(self, to: str, text: str) -> None:
        self.channel.send(ChannelMessage(to=to, body=text, kind="otp"))


def ConsoleMailer() -> Mailer:  # noqa: N802 - kept as the public name
    return ChannelMailer(ConsoleChannel("email", reveal=True))


def ConsoleSms() -> SmsSender:  # noqa: N802
    return ChannelSms(ConsoleChannel("sms", reveal=True))


def SmtpMailer(cfg: AuthConfig) -> Mailer:  # noqa: N802
    if not cfg.smtp_host:
        raise RuntimeError("AUTH_MAILER=smtp needs SMTP_HOST")
    return ChannelMailer(SmtpEmailChannel(cfg.smtp_host, cfg.smtp_port, cfg.smtp_user,
                                          cfg.smtp_password, cfg.mail_from, cfg.smtp_starttls))


def AcsMailer(cfg: AuthConfig) -> Mailer:  # noqa: N802
    if not cfg.acs_connection_string:
        raise RuntimeError("AUTH_MAILER=acs needs ACS_EMAIL_CONNECTION_STRING")
    return ChannelMailer(AcsEmailChannel(
        cfg.acs_connection_string, cfg.mail_from,
        use_sdk=os.getenv("ACS_EMAIL_USE_SDK", "").lower() in {"1", "true", "yes", "on"}))


def build_mailer(cfg: AuthConfig) -> Mailer:
    if cfg.mailer == "console":
        if cfg.production:
            raise RuntimeError("AUTH_MAILER=console is not allowed in production (set smtp or acs)")
        return ConsoleMailer()
    if cfg.mailer == "smtp":
        return SmtpMailer(cfg)
    if cfg.mailer == "acs":
        return AcsMailer(cfg)
    raise RuntimeError(f"unknown AUTH_MAILER {cfg.mailer!r} (console, smtp, acs)")


class NoSms:
    def send(self, to: str, text: str) -> None:
        raise MailError("SMS sign-in is not configured")


def sms_enabled(cfg: AuthConfig) -> bool:
    """Console SMS prints the code to the server log: dev only, never in production."""
    return cfg.sms != "none" and not (cfg.production and cfg.sms == "console")


def build_sms(cfg: AuthConfig) -> SmsSender:
    if cfg.sms == "none" or (cfg.production and cfg.sms == "console"):
        if cfg.production and cfg.sms == "console":
            log.warning("AUTH_SMS=console ignored in production; phone codes are disabled")
        return NoSms()
    if cfg.sms == "console":
        return ConsoleSms()
    if cfg.sms in ("msg91", "twilio"):
        return ChannelSms(build_channel("sms", cfg.sms, production=cfg.production))
    raise RuntimeError(f"unknown AUTH_SMS {cfg.sms!r} (none, console, msg91, twilio)")
