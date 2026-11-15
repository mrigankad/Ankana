"""Outbound channels for reminders, now provided by `app.messaging`.

This module keeps the import surface the notify code and tests use (Message, SendResult,
ChannelError, ConsoleChannel, SmtpEmailChannel, get_channel, set_channel) and picks the
backend per channel from the environment:

    NOTIFY_EMAIL_BACKEND     console (default) | smtp | acs
    NOTIFY_WHATSAPP_BACKEND  console (default) | meta | gupshup | off
    NOTIFY_SMS_BACKEND       console (default) | msg91 | twilio | off

In production the console backend is refused for whatsapp and sms. See docs/deploy.md
for the credentials each backend needs. Nothing sends in tests: the default is console.
"""

from __future__ import annotations

import os

from app.messaging import (
    CHANNEL_KINDS,
    Channel,
    ChannelError,
    ConsoleChannel,
    Message,
    SendResult,
    SmtpEmailChannel,
    build_channel,
    mask,
)

_cache: dict[str, Channel] = {}
_override: dict[str, Channel] = {}


def get_channel(kind: str) -> Channel:
    """The configured channel for `kind`. Channels are process-wide singletons (console
    channels keep `.sent` for tests)."""
    if kind in _override:
        return _override[kind]
    backend = os.getenv(f"NOTIFY_{kind.upper()}_BACKEND", "console").lower()
    key = f"{kind}:{backend}"
    if key not in _cache:
        _cache[key] = build_channel(kind, backend)
    return _cache[key]


def set_channel(kind: str, channel: Channel | None) -> None:
    """Test hook: force a channel (or None to clear)."""
    if channel is None:
        _override.pop(kind, None)
    else:
        _override[kind] = channel


__all__ = ["CHANNEL_KINDS", "Channel", "ChannelError", "ConsoleChannel", "Message",
           "SendResult", "SmtpEmailChannel", "get_channel", "mask", "set_channel"]
