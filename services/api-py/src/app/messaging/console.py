"""Console backends: never leave the process. Dev and tests only."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from .base import Message, SendResult, mask

log = logging.getLogger("app.notify.channels")


@dataclass
class ConsoleChannel:
    """Logs a redacted line and records the message in memory."""

    kind: str = "email"
    name: str = "console"
    reveal: bool = False  # print the full text (sign-in codes in dev); never in production
    sent: list[Message] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def send(self, msg: Message) -> SendResult:
        with self._lock:
            self.sent.append(msg)
            n = len(self.sent)
        if self.reveal:
            log.warning("%s to=%s subject=%s\n%s", self.kind.upper(), msg.to, msg.subject,
                        msg.body)
            print(f"\n--- ankana {self.kind} to {msg.to}: {msg.subject or ''}\n{msg.body}\n---",
                  flush=True)
        else:
            log.info("console %s to=%s chars=%d", self.kind, mask(msg.to), len(msg.body))
        return SendResult(self.name, f"console-{n}")
