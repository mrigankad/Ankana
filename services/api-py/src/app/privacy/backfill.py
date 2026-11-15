"""Bulk key operations on a SQLAlchemy Connection (used by the Alembic migration,
the rotation CLI and tests). Every function binds app.practice_id per practice, so
it works for a non-superuser owner under FORCE ROW LEVEL SECURITY.

Practices are enumerated through the SECURITY DEFINER function privacy_practices().
"""

from __future__ import annotations

import base64
import hashlib

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.notify import models as _notify_models  # noqa: F401  (notification.body/subject)
from app.tenancy.models import Base

from . import blind, crypto
from . import models as _models  # noqa: F401  (registers privacy tables in the metadata)
from .keys import PrivacyError, get_master_provider
from .types import EncryptedText

# client plaintext columns that feed the blind indexes
_CLIENT_BIDX = {"contact_email": ("contact_email_bidx", "client.contact_email", "email"),
                "contact_phone": ("contact_phone_bidx", "client.contact_phone", "phone")}


def encrypted_columns() -> list[tuple[str, str, str]]:
    """(table, column, label) for every EncryptedText column, from the metadata."""
    out = []
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if isinstance(col.type, EncryptedText):
                out.append((table.name, col.name, col.type.label))
    return out


def practice_ids(conn: Connection) -> list[str]:
    return [str(r[0]) for r in conn.execute(text("SELECT practice_id FROM privacy_practices()"))]


def bind(conn: Connection, practice_id) -> None:
    conn.execute(text("SELECT set_config('app.practice_id', :p, true)"), {"p": str(practice_id)})


def _entry(conn: Connection, pid: str, create: bool):
    crypto.store.forget(pid)
    entry = crypto.store.load(conn, pid, create=create)
    if entry is None:
        raise PrivacyError(f"no keys for practice {pid}")
    return entry


def reindex_clients(conn: Connection, pid: str) -> int:
    """Recompute blind indexes from the stored (encrypted or plaintext) contact values."""
    n = 0
    for cid, email, phone in conn.execute(text(
            "SELECT id, contact_email, contact_phone FROM client WHERE practice_id = :p"),
            {"p": pid}).all():
        vals = {}
        for (_attr, (bidx, label, kind)), raw in zip(_CLIENT_BIDX.items(), (email, phone)):
            plain = None if raw is None else crypto.decrypt_value(pid, label, raw)
            vals[bidx] = crypto.blind_index(pid, label, kind, plain)
        conn.execute(text("UPDATE client SET contact_email_bidx = :e, contact_phone_bidx = :t "
                          "WHERE id = :i"),
                     {"e": vals["contact_email_bidx"], "t": vals["contact_phone_bidx"], "i": cid})
        n += 1
    return n


def encrypt_existing(conn: Connection, practice_id=None,
                     only: set[tuple[str, str]] | None = None) -> int:
    """Encrypt plaintext values in every EncryptedText column (or just the `only`
    (table, column) pairs: a migration must not touch columns that do not exist yet
    at its revision), create practice keys when missing, and (re)build the client
    blind indexes. Idempotent."""
    total = 0
    for pid in ([str(practice_id)] if practice_id else practice_ids(conn)):
        bind(conn, pid)
        _entry(conn, pid, create=True)
        for table, col, label in encrypted_columns():
            if only is not None and (table, col) not in only:
                continue
            rows = conn.execute(text(
                f"SELECT id, {col} FROM {table} WHERE practice_id = :p AND {col} IS NOT NULL "
                f"AND {col} NOT LIKE 'enc1:%'"), {"p": pid}).all()
            for rid, plain in rows:
                conn.execute(text(f"UPDATE {table} SET {col} = :v WHERE id = :i"),
                             {"v": crypto.encrypt_value(pid, label, plain), "i": rid})
            total += len(rows)
        reindex_clients(conn, pid)
    return total


def decrypt_existing(conn: Connection, only: set[tuple[str, str]] | None = None) -> int:
    """Inverse of encrypt_existing (migration downgrade). `only` limits it to
    (table, column) pairs, so a later migration can undo just its own columns."""
    total = 0
    for pid in practice_ids(conn):
        bind(conn, pid)
        if crypto.store.load(conn, pid) is None:
            continue
        _entry(conn, pid, create=False)
        for table, col, label in encrypted_columns():
            if only is not None and (table, col) not in only:
                continue
            rows = conn.execute(text(
                f"SELECT id, {col} FROM {table} WHERE practice_id = :p AND {col} LIKE 'enc1:%'"),
                {"p": pid}).all()
            for rid, ct in rows:
                conn.execute(text(f"UPDATE {table} SET {col} = :v WHERE id = :i"),
                             {"v": crypto.decrypt_value(pid, label, ct), "i": rid})
            total += len(rows)
    return total


# ------------------------------------------------------------------ rotation
def rotate_master(conn: Connection) -> int:
    """Re-wrap every practice key under the current master key. Cheap: no data is
    re-encrypted. Needs the old master key(s) in ANKANA_MASTER_KEY_PREVIOUS."""
    current = get_master_provider().current_id
    n = 0
    for pid in practice_ids(conn):
        bind(conn, pid)
        rows = conn.execute(text(
            "SELECT id, kind, version, wrapped, master_key_id FROM practice_key "
            "WHERE practice_id = :p"), {"p": pid}).all()
        for kid, kind, version, wrapped, mkid in rows:
            if mkid == current:
                continue
            new_wrapped, new_mkid = crypto.rewrap_key(pid, kind, version, wrapped, mkid)
            conn.execute(text("UPDATE practice_key SET wrapped = :w, master_key_id = :m "
                              "WHERE id = :i"), {"w": new_wrapped, "m": new_mkid, "i": kid})
            n += 1
        crypto.store.forget(pid)
    return n


def rotate_data_key(conn: Connection, practice_id) -> dict:
    """New DEK version for one practice, re-encrypt every value under it, retire the
    old version. Old versions stay (status retired) until purge_retired."""
    pid = str(practice_id)
    bind(conn, pid)
    entry = _entry(conn, pid, create=True)
    old, new = entry.active, entry.active + 1
    _, wrapped, mkid = crypto.wrap_new_key(pid, "dek", new)
    conn.execute(text(
        "INSERT INTO practice_key (practice_id, kind, version, wrapped, master_key_id, status) "
        "VALUES (:p, 'dek', :v, :w, :m, 'active')"),
        {"p": pid, "v": new, "w": wrapped, "m": mkid})
    conn.execute(text("UPDATE practice_key SET status = 'retired', retired_at = now() "
                      "WHERE practice_id = :p AND kind = 'dek' AND version = :v"),
                 {"p": pid, "v": old})
    _entry(conn, pid, create=False)
    reencrypted = 0
    for table, col, label in encrypted_columns():
        rows = conn.execute(text(
            f"SELECT id, {col} FROM {table} WHERE practice_id = :p AND {col} LIKE 'enc1:%' "
            f"AND {col} NOT LIKE :pat"), {"p": pid, "pat": f"enc1:{new}:%"}).all()
        for rid, ct in rows:
            plain = crypto.decrypt_value(pid, label, ct)
            conn.execute(text(f"UPDATE {table} SET {col} = :v WHERE id = :i"),
                         {"v": crypto.encrypt_value(pid, label, plain, version=new), "i": rid})
        reencrypted += len(rows)
    return {"practice_id": pid, "old_version": old, "new_version": new,
            "reencrypted": reencrypted}


def purge_retired(conn: Connection, practice_id) -> int:
    """Delete retired DEK versions once nothing references them. Run only after
    every API process has refreshed its key cache (KEY_TTL_SECONDS)."""
    pid = str(practice_id)
    bind(conn, pid)
    entry = _entry(conn, pid, create=False)
    for table, col, _label in encrypted_columns():
        for (_, v) in [k for k in entry.keys if k[0] == "dek" and k[1] != entry.active]:
            left = conn.execute(text(
                f"SELECT count(*) FROM {table} WHERE practice_id = :p AND {col} LIKE :pat"),
                {"p": pid, "pat": f"enc1:{v}:%"}).scalar()
            if left:
                raise PrivacyError(f"{table}.{col} still has {left} values under key v{v}")
    n = conn.execute(text("DELETE FROM practice_key WHERE practice_id = :p AND kind = 'dek' "
                          "AND status = 'retired'"), {"p": pid}).rowcount
    crypto.store.forget(pid)
    return n


# ------------------------------------------------- ai_connection.api_key_enc
def _fernet(secret: str):
    from cryptography.fernet import Fernet

    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def rotate_ai_keys(conn: Connection, new_secret: str, old_secret: str, practice_id=None) -> int:
    """Re-encrypt ai_connection.api_key_enc (Fernet, key derived from
    ANKANA_SECRET_KEY, "v1:" prefix, see ankana_ai.connections) from the old secret
    to the new one. Tries the old secret first, then the new (already rotated rows)."""
    from cryptography.fernet import InvalidToken

    old_f, new_f = _fernet(old_secret), _fernet(new_secret)
    n = 0
    for pid in ([str(practice_id)] if practice_id else practice_ids(conn)):
        bind(conn, pid)
        for cid, token in conn.execute(text(
                "SELECT id, api_key_enc FROM ai_connection WHERE practice_id = :p "
                "AND api_key_enc IS NOT NULL"), {"p": pid}).all():
            raw = token.removeprefix("v1:").encode()
            try:
                plain = old_f.decrypt(raw)
            except InvalidToken:
                try:
                    new_f.decrypt(raw)  # already under the new secret
                except InvalidToken:
                    raise PrivacyError(
                        f"ai_connection {cid} matches neither ANKANA_SECRET_KEY_OLD nor "
                        "ANKANA_SECRET_KEY; nothing was changed") from None
                continue
            conn.execute(text("UPDATE ai_connection SET api_key_enc = :v WHERE id = :i"),
                         {"v": "v1:" + new_f.encrypt(plain).decode(), "i": cid})
            n += 1
    return n


__all__ = ["blind"]
