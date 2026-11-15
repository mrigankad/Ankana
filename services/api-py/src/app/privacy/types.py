"""EncryptedText: a Text column whose values are AES-GCM envelopes at rest and
plain str in Python. Needs the practice scope that app.privacy.orm sets."""

from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from . import crypto, orm  # noqa: F401  (orm registers the Session hooks)
from .keys import PrivacyError


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        pid = crypto.current_scope()
        if pid is None:
            raise PrivacyError(
                f"cannot encrypt {self.label}: session is not bound to a practice")
        if crypto.is_encrypted(value):  # already an envelope (backfill, rotation)
            return value
        return crypto.encrypt_value(pid, self.label, value)

    def process_result_value(self, value, dialect):
        if value is None or not crypto.is_encrypted(value):
            return value
        pid = crypto.current_scope()
        if pid is None:
            return value  # never plaintext without a scope; ciphertext is harmless
        return crypto.decrypt_value(pid, self.label, value)
