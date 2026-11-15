"""One outbound messaging package for auth (codes, invites) and notifications.

    Channel.send(Message) -> SendResult         raises ChannelError(retryable=...)

email:     console, smtp, acs (REST, or the azure-communication-email SDK)
whatsapp:  meta (WhatsApp Cloud API), gupshup
sms:       msg91 (India DLT), twilio
webhooks:  messaging.api (signature-verified delivery receipts and STOP replies)
"""

from .base import (
    CHANNEL_KINDS,
    DELIVERY_STATUSES,
    Channel,
    ChannelError,
    Http,
    InboundEvent,
    Message,
    SendResult,
    StatusEvent,
    is_production,
    mask,
    should_apply,
)
from .console import ConsoleChannel
from .factory import BACKENDS, OffChannel, assert_production_ready, build_channel
from .mail import AcsEmailChannel, SmtpEmailChannel
from .sms import Msg91Sms, TwilioSms
from .whatsapp import GupshupWhatsApp, MetaWhatsApp, WaTemplates

__all__ = [
    "BACKENDS", "CHANNEL_KINDS", "DELIVERY_STATUSES", "AcsEmailChannel", "Channel",
    "ChannelError", "ConsoleChannel", "GupshupWhatsApp", "Http", "InboundEvent", "Message",
    "MetaWhatsApp", "Msg91Sms", "OffChannel", "SendResult", "SmtpEmailChannel", "StatusEvent",
    "TwilioSms", "WaTemplates", "assert_production_ready", "build_channel", "is_production",
    "mask", "should_apply",
]
