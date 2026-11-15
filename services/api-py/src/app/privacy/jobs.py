"""Queue handler for `privacy_request` jobs (export, erasure, retention, practice
export, account deletion). Handlers are idempotent: a retried job that finds the
request already done returns immediately."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from app.jobs import Job
from app.storage import Storage
from app.tenancy.session import tenant_session

from . import service
from .models import PrivacyRequest

log = logging.getLogger(__name__)


def run_request(job: Job, engine: Engine, storage: Storage) -> dict | None:
    rid = uuid.UUID(job.payload["request_id"])
    with tenant_session(engine, job.practice_id) as db:
        req = db.get(PrivacyRequest, rid)
        if req is None:
            return {"status": "missing"}
        if req.status in ("done", "blocked"):
            return {"status": req.status}
        pid = req.practice_id
        try:
            if req.kind == "client_export":
                client = service.get_client_any(db, req.client_id)
                if client is None or client.erased_at is not None:
                    raise service.AlreadyErasedError("client has been erased")
                data, summary = service.export_client(db, pid, client, storage)
                service.store_export(db, storage, req, data)
                req.result = summary
            elif req.kind == "client_erase":
                req.result = {"counts": service.erase_client(
                    db, pid, req.client_id, storage, member_id=req.requested_by_member_id)}
            elif req.kind == "practice_export":
                data, summary = service.export_practice(db, pid, storage)
                service.store_export(db, storage, req, data)
                req.result = summary
            elif req.kind == "practice_delete":
                req.result = {"counts": service.delete_practice(
                    db, pid, storage, member_id=req.requested_by_member_id)}
            elif req.kind in ("retention_dry_run", "retention_apply"):
                req.result = service.run_retention(
                    db, pid, storage, apply=req.kind == "retention_apply",
                    member_id=req.requested_by_member_id)
            else:
                raise ValueError(f"unknown privacy request kind {req.kind!r}")
        except (service.LegalHoldError, service.AlreadyErasedError) as exc:
            req.status = "blocked"
            req.error = str(exc)
            req.completed_at = datetime.now(UTC)
            return {"status": "blocked"}
        req.status = "done"
        req.completed_at = datetime.now(UTC)
        return {"status": "done", "kind": req.kind}


def request_failed(job: Job, engine: Engine, error: str, final: bool) -> None:
    if not final or job.practice_id is None:
        return
    try:
        with tenant_session(engine, job.practice_id) as db:
            req = db.get(PrivacyRequest, uuid.UUID(job.payload["request_id"]))
            if req is not None and req.status not in ("done", "blocked"):
                req.status = "failed"
                req.error = error[:500]
                req.completed_at = datetime.now(UTC)
    except Exception:
        log.exception("could not mark privacy request failed")
