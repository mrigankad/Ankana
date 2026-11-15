"""Minimal Postgres job queue.

Why not procrastinate / pgqueuer: both ship their own schema and migration
tooling (conflicts with our single Alembic history), want dedicated
LISTEN/NOTIFY connections, and bring their own role/grant model that we would
have to reconcile with RLS. Our needs are small (two job kinds, tens of jobs a
minute) and `FOR UPDATE SKIP LOCKED` is the same primitive they use. About 100
lines we fully own and test. If volume grows, swap pgqueuer or Service Bus in
behind these five functions.

Semantics: at-least-once. A job is claimed (status=running, attempts+1). On
failure it is re-queued with exponential backoff until max_attempts, then
marked failed. A worker that dies leaves a running row; reap_stale() returns
those to the queue (or fails them when attempts are exhausted).
Handlers must therefore be idempotent. complete() and fail() only act on the run that
claimed the job (status running and the same attempt number), so a worker that was reaped
as lost cannot overwrite the outcome of the run that replaced it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

BACKOFF_BASE_SECONDS = 5.0


@dataclass(frozen=True)
class Job:
    id: uuid.UUID
    kind: str
    practice_id: uuid.UUID | None
    payload: dict[str, Any]
    attempts: int
    max_attempts: int

    @property
    def final_attempt(self) -> bool:
        return self.attempts >= self.max_attempts


def enqueue(db: Session | Connection, kind: str, payload: dict[str, Any] | None = None, *,
            practice_id: uuid.UUID | None = None, max_attempts: int = 3,
            delay_seconds: float = 0) -> uuid.UUID:
    """Insert a job using the caller's session, so it commits atomically with
    the business row that caused it."""
    job_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO job (id, kind, practice_id, payload, max_attempts, run_at) "
             "VALUES (:id, :kind, :pid, CAST(:payload AS jsonb), :max, "
             "now() + make_interval(secs => :delay))"),
        {"id": job_id, "kind": kind, "pid": practice_id,
         "payload": json.dumps(payload or {}), "max": max_attempts, "delay": delay_seconds},
    )
    return job_id


_CLAIM = text("""
UPDATE job SET status = 'running', attempts = attempts + 1, locked_at = now(),
               locked_by = :worker, updated_at = now()
WHERE id = (
    SELECT id FROM job
    WHERE status = 'queued' AND run_at <= now()
      AND (CAST(:kinds AS text[]) IS NULL OR kind = ANY(CAST(:kinds AS text[])))
    ORDER BY run_at, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, kind, practice_id, payload, attempts, max_attempts
""")


def claim_next(engine: Engine, worker_id: str, kinds: list[str] | None = None) -> Job | None:
    with engine.begin() as conn:
        row = conn.execute(_CLAIM, {"worker": worker_id, "kinds": kinds}).mappings().first()
    if row is None:
        return None
    return Job(row["id"], row["kind"], row["practice_id"], row["payload"] or {},
               row["attempts"], row["max_attempts"])


def complete(engine: Engine, job: Job, result: dict | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE job SET status='done', finished_at=now(), updated_at=now(), "
                 "locked_at=NULL, locked_by=NULL, result=CAST(:r AS jsonb) "
                 "WHERE id=:id AND status='running' AND attempts=:att"),
            {"id": job.id, "att": job.attempts,
             "r": json.dumps(result) if result is not None else None},
        )


def fail(engine: Engine, job: Job, error: str) -> bool:
    """Record a failure. Returns True when the job is now terminally failed."""
    error = error[:2000]
    with engine.begin() as conn:
        if job.final_attempt:
            conn.execute(
                text("UPDATE job SET status='failed', finished_at=now(), updated_at=now(), "
                     "locked_at=NULL, locked_by=NULL, last_error=:e "
                     "WHERE id=:id AND status='running' AND attempts=:att"),
                {"id": job.id, "e": error, "att": job.attempts},
            )
            return True
        conn.execute(
            text("UPDATE job SET status='queued', updated_at=now(), locked_at=NULL, "
                 "locked_by=NULL, last_error=:e, "
                 "run_at = now() + make_interval(secs => :delay) "
                 "WHERE id=:id AND status='running' AND attempts=:att"),
            {"id": job.id, "e": error, "att": job.attempts,
             "delay": BACKOFF_BASE_SECONDS * 2 ** (job.attempts - 1)},
        )
    return False


def reap_stale(engine: Engine, visibility_timeout_seconds: float = 900) -> list[Job]:
    """Recover jobs whose worker vanished. Returns the ones that became terminally failed."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE job SET status='queued', locked_at=NULL, locked_by=NULL, "
                 "updated_at=now(), last_error='worker lost' "
                 "WHERE status='running' AND attempts < max_attempts "
                 "AND locked_at < now() - make_interval(secs => :t)"),
            {"t": visibility_timeout_seconds},
        )
        rows = conn.execute(
            text("UPDATE job SET status='failed', finished_at=now(), updated_at=now(), "
                 "locked_at=NULL, locked_by=NULL, last_error='worker lost' "
                 "WHERE status='running' AND attempts >= max_attempts "
                 "AND locked_at < now() - make_interval(secs => :t) "
                 "RETURNING id, kind, practice_id, payload, attempts, max_attempts"),
            {"t": visibility_timeout_seconds},
        ).all()
    return [Job(r[0], r[1], r[2], r[3] or {}, r[4], r[5]) for r in rows]
