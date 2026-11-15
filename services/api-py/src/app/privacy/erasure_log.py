"""Durable erasure log (ids only) and replay after a database restore.

A database backup cannot be edited, so a restore brings erased people back. Every erasure
therefore writes a tiny event, BEFORE it deletes anything, to two places:

  * object storage, one immutable JSON blob per event under `_erasure_log/` (this survives a
    database restore, because it does not live in the database; put a time-based
    immutability policy on that prefix, see docs/operations.md), and
  * the `erasure_log` table (append-only under RLS), which a restore rolls back with the
    rest of the data, and which `export-erasure-log` can dump from a live server.

An event holds `event_id`, `kind` (client | practice), `practice_id`, `client_id`, `via` and
`at`. No names, contacts or reasons. After a restore, `python -m app.privacy.cli
replay-erasures --since <restore point>` reads the events newer than the restore point and
re-applies each one (the same delete-and-overwrite cascade, legal hold overridden because the
original erasure already happened lawfully). Replay is idempotent: erased clients are
skipped, clients that did not exist in the backup are reported as unknown.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.storage import Storage
from app.tenancy.session import tenant_session

from . import crypto

log = logging.getLogger("ankana.erasure_log")

PREFIX = "_erasure_log/"
KINDS = ("client", "practice")


@dataclass(frozen=True)
class Event:
    event_id: str
    kind: str
    practice_id: str
    client_id: str | None
    via: str
    at: datetime

    def to_json(self) -> bytes:
        d = asdict(self)
        d["at"] = self.at.astimezone(UTC).isoformat()
        d["v"] = 1
        return json.dumps(d, sort_keys=True).encode()

    @staticmethod
    def from_dict(d: dict) -> Event:
        if d.get("kind") not in KINDS:
            raise ValueError(f"unknown erasure event kind {d.get('kind')!r}")
        at = datetime.fromisoformat(d["at"])
        return Event(str(uuid.UUID(d["event_id"])), d["kind"], str(uuid.UUID(d["practice_id"])),
                     str(uuid.UUID(d["client_id"])) if d.get("client_id") else None,
                     str(d.get("via") or "request"), at if at.tzinfo else at.replace(tzinfo=UTC))

    @property
    def key(self) -> str:
        return f"{PREFIX}{self.at.astimezone(UTC):%Y%m%dT%H%M%S%fZ}-{self.event_id}.json"


def new_event(kind: str, practice_id, client_id=None, via: str = "request") -> Event:
    return Event(str(uuid.uuid4()), kind, str(practice_id),
                 str(client_id) if client_id else None, via, datetime.now(UTC))


_INSERT = text("""
    INSERT INTO erasure_log (event_id, kind, practice_id, client_id, via, erased_at)
    VALUES (:e, :k, :p, :c, :v, :t) ON CONFLICT (event_id) DO NOTHING
""")


def record(db: Session, storage: Storage | None, ev: Event, *, publish: bool = True) -> None:
    """Write the event durably. Storage first: if it fails the erasure does not start (the
    job retries), so no erasure ever happens without a log entry that outlives a restore."""
    if publish and storage is not None:
        storage.put(ev.key, ev.to_json(), "application/json")
    db.execute(_INSERT, {"e": ev.event_id, "k": ev.kind, "p": ev.practice_id,
                         "c": ev.client_id, "v": ev.via, "t": ev.at})


# ---------------------------------------------------------------- readers
def read_storage(storage: Storage, since: datetime) -> list[Event]:
    stamp = f"{PREFIX}{since.astimezone(UTC):%Y%m%dT%H%M%S%fZ}"
    events = []
    for key in sorted(storage.list_keys(PREFIX)):
        if key < stamp:  # names start with a sortable UTC stamp
            continue
        events.append(Event.from_dict(json.loads(storage.get(key))))
    return sorted(events, key=lambda e: e.at)


def read_db(engine: Engine, since: datetime) -> list[Event]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT event_id, kind, practice_id, client_id, via, erased_at "
                                 "FROM privacy_erasure_events(:s)"), {"s": since}).all()
    return [Event(str(r[0]), r[1], str(r[2]), str(r[3]) if r[3] else None, r[4] or "request", r[5])
            for r in rows]


def read_file(path: str | Path, since: datetime) -> list[Event]:
    events = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            ev = Event.from_dict(json.loads(line))
            if ev.at >= since:
                events.append(ev)
    return sorted(events, key=lambda e: e.at)


def write_file(path: str | Path, events: list[Event]) -> int:
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.to_json().decode() + "\n")
    return len(events)


# ----------------------------------------------------------------- replay
def replay(engine: Engine, storage: Storage, events: list[Event], *,
           dry_run: bool = False) -> dict:
    """Re-apply erasures to a restored database. Returns counts and the ids of failures."""
    from . import service

    out = {"applied": 0, "already_erased": 0, "unknown": 0, "errors": 0, "failed_events": [],
           "dry_run": dry_run}
    for ev in sorted(events, key=lambda e: e.at):
        try:
            # the restored database may hold different key rows than this process cached
            crypto.store.forget(ev.practice_id)
            with tenant_session(engine, ev.practice_id) as db:
                if ev.kind == "client":
                    client = service.get_client_any(db, ev.client_id)
                    if client is None:
                        out["unknown"] += 1
                        continue
                    if client.erased_at is not None:
                        record(db, None, ev, publish=False)
                        out["already_erased"] += 1
                        continue
                    if not dry_run:
                        service.erase_client(db, ev.practice_id, ev.client_id, storage,
                                             via="replay", event=ev, ignore_hold=True)
                    out["applied"] += 1
                else:
                    row = db.execute(text("SELECT deleted_at FROM practice WHERE id = :p"),
                                     {"p": ev.practice_id}).first()
                    if row is None:
                        out["unknown"] += 1
                        continue
                    if row[0] is not None:
                        record(db, None, ev, publish=False)
                        out["already_erased"] += 1
                        continue
                    if not dry_run:
                        service.delete_practice(db, ev.practice_id, storage, via="replay",
                                                event=ev, ignore_hold=True)
                    out["applied"] += 1
        except Exception as exc:
            log.error("replay of erasure event %s failed: %s", ev.event_id, exc.__class__.__name__,
                      exc_info=True)
            out["errors"] += 1
            out["failed_events"].append(ev.event_id)
    return out
