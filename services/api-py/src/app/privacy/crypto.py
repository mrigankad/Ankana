"""Envelope encryption for field values.

value  --AES-256-GCM(DEK vN, aad = practice_id|label)-->  "enc1:<N>:<b64url(nonce||ct)>"
DEK    --wrapped by the master key-->  practice_key.wrapped (one row per version)

The AAD binds a ciphertext to its practice and column, so a value copied into
another row, column or tenant fails authentication instead of decrypting.

Blind index: HMAC-SHA256 under a per-practice blind key (separate random key,
never rotated with the DEK) over label + normalised value. Equality lookup only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text

from .keys import PrivacyError, get_master_provider

PREFIX = "enc1:"
KEY_TTL_SECONDS = 30.0

# The practice whose keys the current ORM operation may use; set by app.privacy.orm.
_scope: ContextVar[str | None] = ContextVar("ankana_privacy_scope", default=None)


def current_scope() -> str | None:
    return _scope.get()


def set_scope(practice_id) -> None:
    _scope.set(str(practice_id) if practice_id else None)


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _wrap_aad(practice_id: str, kind: str, version: int) -> bytes:
    return f"{practice_id}|{kind}|{version}".encode()


@dataclass
class _Entry:
    keys: dict[tuple[str, int], bytes] = field(default_factory=dict)
    active: int = 0
    loaded: float = field(default_factory=time.monotonic)


class KeyStore:
    """Per-process cache of unwrapped keys. Loads through the caller's connection
    so RLS applies: a session bound to practice A can only ever fetch A's keys."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    def forget(self, practice_id=None) -> None:
        with self._lock:
            if practice_id is None:
                self._entries.clear()
            else:
                self._entries.pop(str(practice_id), None)

    def peek(self, practice_id) -> _Entry | None:
        e = self._entries.get(str(practice_id))
        if e and time.monotonic() - e.loaded < KEY_TTL_SECONDS:
            return e
        return None

    def load(self, conn, practice_id, create: bool = False) -> _Entry | None:
        pid = str(practice_id)
        cached = self.peek(pid)
        if cached is not None:
            return cached
        rows = self._rows(conn, pid)
        if not any(r[0] == "dek" for r in rows) and create:
            practice_deleted = conn.execute(
                text("SELECT deleted_at IS NOT NULL FROM practice WHERE id = :p"),
                {"p": pid}).scalar()
            if not practice_deleted:
                self._create(conn, pid)
                rows = self._rows(conn, pid)
        if not rows:
            return None
        provider = get_master_provider()
        entry = _Entry()
        for kind, version, wrapped, mkid, status in rows:
            entry.keys[(kind, version)] = provider.unwrap(
                mkid, _b64d(wrapped), _wrap_aad(pid, kind, version))
            if kind == "dek" and status == "active":
                entry.active = max(entry.active, version)
        with self._lock:
            self._entries[pid] = entry
        return entry

    @staticmethod
    def _rows(conn, pid: str):
        return conn.execute(text(
            "SELECT kind, version, wrapped, master_key_id, status FROM practice_key "
            "WHERE practice_id = :p ORDER BY kind, version"), {"p": pid}).all()

    @staticmethod
    def _create(conn, pid: str) -> None:
        provider = get_master_provider()
        for kind in ("dek", "blind"):
            mkid, wrapped = provider.wrap(secrets.token_bytes(32), _wrap_aad(pid, kind, 1))
            conn.execute(text(
                "INSERT INTO practice_key (practice_id, kind, version, wrapped, master_key_id, "
                "status) VALUES (:p, :k, 1, :w, :m, 'active') ON CONFLICT DO NOTHING"),
                {"p": pid, "k": kind, "w": _b64e(wrapped), "m": mkid})


store = KeyStore()


def wrap_new_key(practice_id, kind: str, version: int) -> tuple[bytes, str, str]:
    """Generate a key and wrap it. Returns (plaintext, wrapped_b64, master_key_id)."""
    key = secrets.token_bytes(32)
    mkid, wrapped = get_master_provider().wrap(key, _wrap_aad(str(practice_id), kind, version))
    return key, _b64e(wrapped), mkid


def rewrap_key(practice_id, kind: str, version: int, wrapped_b64: str, mkid: str) -> tuple[str, str]:
    """Unwrap with the key it was wrapped under and wrap with the current master key."""
    provider = get_master_provider()
    aad = _wrap_aad(str(practice_id), kind, version)
    key = provider.unwrap(mkid, _b64d(wrapped_b64), aad)
    new_id, wrapped = provider.wrap(key, aad)
    return _b64e(wrapped), new_id


def _aad(practice_id: str, label: str) -> bytes:
    return f"{practice_id}|{label}".encode()


def encrypt_value(practice_id, label: str, plaintext: str, version: int | None = None) -> str:
    pid = str(practice_id)
    entry = store._entries.get(pid)
    if entry is None or not entry.active:
        raise PrivacyError("no active data key for this practice (not bound to a session?)")
    version = version or entry.active
    key = entry.keys[("dek", version)]
    nonce = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), _aad(pid, label))
    return f"{PREFIX}{version}:{_b64e(nonce + ct)}"


def is_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(PREFIX)


def decrypt_value(practice_id, label: str, value: str) -> str:
    if not value.startswith(PREFIX):
        return value  # legacy plaintext, waiting for the backfill
    pid = str(practice_id)
    _, ver, body = value.split(":", 2)
    entry = store._entries.get(pid)
    if entry is None or ("dek", int(ver)) not in entry.keys:
        raise PrivacyError(f"data key v{ver} not available for this practice")
    raw = _b64d(body)
    try:
        return AESGCM(entry.keys[("dek", int(ver))]).decrypt(
            raw[:12], raw[12:], _aad(pid, label)).decode()
    except InvalidTag:
        raise PrivacyError("ciphertext failed authentication (wrong practice, column or key)") \
            from None


def encryption_version(value: str) -> int | None:
    return int(value.split(":", 2)[1]) if is_encrypted(value) else None


# ------------------------------------------------------------ blind index
def normalise(kind: str, value: str) -> str:
    if kind == "email":
        return value.strip().lower()
    if kind == "phone":
        digits = re.sub(r"\D", "", value)
        return digits[-10:] if len(digits) > 10 else digits  # drop +91 / 0 prefixes
    return value.strip()


def blind_index(practice_id, label: str, kind: str, value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    entry = store._entries.get(str(practice_id))
    if entry is None or ("blind", 1) not in entry.keys:
        raise PrivacyError("no blind-index key loaded for this practice")
    msg = f"{label}\x00{normalise(kind, value)}".encode()
    return hmac.new(entry.keys[("blind", 1)], msg, hashlib.sha256).hexdigest()


def sign(practice_id, purpose: str, payload: bytes) -> str:
    """HMAC under the practice blind key, domain separated by `purpose`.
    Used for consent receipts and export manifests."""
    entry = store._entries.get(str(practice_id))
    if entry is None or ("blind", 1) not in entry.keys:
        raise PrivacyError("no signing key loaded for this practice")
    key = hmac.new(entry.keys[("blind", 1)], f"sign:{purpose}".encode(), hashlib.sha256).digest()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()
