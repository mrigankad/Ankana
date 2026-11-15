"""Blind indexes for client email and phone, plus the lookup helper."""

from __future__ import annotations

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from . import crypto, orm

INDEXED = (
    ("contact_email", "contact_email_bidx", "client.contact_email", "email"),
    ("contact_phone", "contact_phone_bidx", "client.contact_phone", "phone"),
)


def set_indexes(target) -> None:
    for attr, bidx, label, kind in INDEXED:
        setattr(target, bidx, crypto.blind_index(
            target.practice_id, label, kind, getattr(target, attr)))


def register_blind_indexes(client_cls) -> None:
    def _before(mapper, connection, target) -> None:
        set_indexes(target)

    event.listen(client_cls, "before_insert", _before)
    event.listen(client_cls, "before_update", _before)


def find_clients(db: Session, *, email: str | None = None, phone: str | None = None):
    """Clients whose contact email and/or phone equal the given values (live rows
    only, practice scoped by RLS). Normalisation matches what is indexed:
    email case-insensitive, phone digits only (country code ignored)."""
    from app.tenancy.models import Client

    orm.prepare(db, create=False)
    pid = db.info.get("practice_id")
    stmt = select(Client).where(Client.deleted_at.is_(None))
    for value, attr, label, kind in ((email, Client.contact_email_bidx, "client.contact_email", "email"),
                                     (phone, Client.contact_phone_bidx, "client.contact_phone", "phone")):
        if value is None:
            continue
        digest = crypto.blind_index(pid, label, kind, value)
        if digest is None:
            return []
        stmt = stmt.where(attr == digest)
    if email is None and phone is None:
        return []
    return list(db.scalars(stmt))
