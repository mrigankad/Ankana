"""Shared plumbing for /v1: problem+json errors, cursor pagination, audit,
usage counters, idempotency replay and per-client access checks."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth import CurrentMember
from app.tenancy.models import (
    AuditEvent,
    Client,
    Consent,
    ConsentPurpose,
    IdempotencyKey,
    Member,
    Role,
    UsageCounter,
)

STAFF = (Role.owner, Role.astrologer, Role.assistant)
CLINICAL = (Role.owner, Role.astrologer)
PROBLEM_MEDIA = "application/problem+json"
PROBLEM_BASE = "https://ankana.app/problems/"


# ---------------------------------------------------------------- problems
class ProblemError(HTTPException):
    """HTTPException carrying a stable machine code (RFC 9457 `code` member)."""

    def __init__(self, status: int, detail: str, code: str, **extra: Any) -> None:
        super().__init__(status_code=status, detail=detail)
        self.code = code
        self.extra = extra


def problem_body(status: int, detail: Any, path: str, code: str | None = None,
                 extra: dict | None = None) -> dict:
    try:
        title = HTTPStatus(status).phrase
    except ValueError:
        title = "Error"
    code = code or title.lower().replace(" ", "_")
    body = {
        "type": PROBLEM_BASE + code, "title": title, "status": status,
        "detail": detail if isinstance(detail, str) else json.dumps(jsonable_encoder(detail)),
        "instance": path, "code": code,
    }
    body.update(extra or {})
    return body


def register_problem_handlers(app) -> None:
    """RFC 9457 envelope for everything under /v1. Other paths keep FastAPI's
    default {"detail": ...} so the legacy routes and their clients are unchanged."""

    def is_v1(request: Request) -> bool:
        return request.url.path.startswith("/v1/") or request.url.path == "/v1"

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        if not is_v1(request):
            return await http_exception_handler(request, exc)
        return JSONResponse(
            problem_body(exc.status_code, exc.detail, request.url.path,
                         getattr(exc, "code", None), getattr(exc, "extra", None)),
            status_code=exc.status_code, media_type=PROBLEM_MEDIA,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        if not is_v1(request):
            return await request_validation_exception_handler(request, exc)
        errors = [{"loc": [str(p) for p in e.get("loc", ())], "msg": e.get("msg"),
                   "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(
            problem_body(422, "Request validation failed", request.url.path,
                         "validation_error", {"errors": errors}),
            status_code=422, media_type=PROBLEM_MEDIA,
        )


def _problem_response(status: int) -> dict:
    return {"description": HTTPStatus(status).phrase,
            "content": {PROBLEM_MEDIA: {"schema": {"$ref": "#/components/schemas/Problem"}}}}


PROBLEM_RESPONSES: dict[int | str, dict] = {
    s: _problem_response(s) for s in (400, 401, 402, 403, 404, 409, 422)
}


# -------------------------------------------------------------- pagination
def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        pad = "=" * (-len(cursor) % 4)
        ts, rid = json.loads(base64.urlsafe_b64decode(cursor + pad))
        return datetime.fromisoformat(ts), uuid.UUID(rid)
    except Exception:
        raise ProblemError(400, "invalid cursor", "invalid_cursor") from None


def paginate(db: Session, stmt, model, limit: int, cursor: str | None):
    """Keyset pagination on (created_at DESC, id DESC). Returns (rows, next_cursor)."""
    if cursor:
        ts, rid = decode_cursor(cursor)
        stmt = stmt.where(tuple_(model.created_at, model.id) < tuple_(ts, rid))
    rows = list(db.scalars(
        stmt.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)))
    nxt = None
    if len(rows) > limit:
        rows = rows[:limit]
        nxt = encode_cursor(rows[-1].created_at, rows[-1].id)
    return rows, nxt


# ------------------------------------------------------------- audit/usage
def audit(db: Session, m: CurrentMember, action: str, entity: str, entity_id: object,
          request: Request, meta: dict | None = None) -> None:
    db.add(AuditEvent(
        practice_id=m.practice_id, actor_user_id=m.user_id, actor_member_id=m.member_id,
        action=action, entity_type=entity, entity_id=str(entity_id),
        ip=request.client.host if request.client else None,
        request_id=request.headers.get("x-request-id"), meta=meta,
    ))


def bump_usage(db: Session, practice_id: uuid.UUID, metric: str, n: int = 1) -> None:
    today = datetime.now(tz=UTC).date()
    period = date(today.year, today.month, 1)
    stmt = pg_insert(UsageCounter).values(
        practice_id=practice_id, metric=metric, period=period, value=n)
    db.execute(stmt.on_conflict_do_update(
        index_elements=["practice_id", "metric", "period"],
        set_={"value": UsageCounter.value + n, "updated_at": func.now()}))


# -------------------------------------------------------------- access
def load_client(db: Session, m: CurrentMember, client_id: uuid.UUID) -> Client:
    """Fetch a live client in the caller's practice. Client-portal members only
    ever see their own record; anything else is a 404 (no existence leak)."""
    if m.role == Role.client:
        own = db.scalar(select(Member.client_id).where(Member.id == m.member_id))
        if own != client_id:
            raise ProblemError(404, "client not found", "not_found")
    client = db.scalar(select(Client).where(Client.id == client_id, Client.deleted_at.is_(None)))
    if client is None:
        raise ProblemError(404, "client not found", "not_found")
    return client


def has_consent(db: Session, client_id: uuid.UUID, purpose: ConsentPurpose) -> bool:
    return db.scalar(select(Consent.id).where(
        Consent.client_id == client_id, Consent.purpose == purpose,
        Consent.withdrawn_at.is_(None)).limit(1)) is not None


def require_consent(db: Session, client_id: uuid.UUID, purpose: ConsentPurpose) -> None:
    if not has_consent(db, client_id, purpose):
        raise ProblemError(
            403, f"client has not granted consent for {purpose.value}", "consent_required",
            purpose=purpose.value)


# --------------------------------------------------------- idempotency
def request_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def idempotent(db: Session, m: CurrentMember, endpoint: str, key: str | None,
               payload: Any, run) -> tuple[int, dict, bool]:
    """Run `run() -> (status, body)` once per Idempotency-Key. Returns
    (status, body, replayed). Without a key it just runs."""
    if not key:
        status, body = run()
        return status, body, False
    if len(key) > 128:
        raise ProblemError(400, "Idempotency-Key too long", "invalid_idempotency_key")
    digest = request_hash(payload)
    row = db.scalar(select(IdempotencyKey).where(
        IdempotencyKey.endpoint == endpoint, IdempotencyKey.key == key))
    if row is not None:
        if row.request_hash != digest:
            raise ProblemError(422, "Idempotency-Key reused with a different request",
                               "idempotency_key_reuse")
        return row.status_code, row.response, True
    status, body = run()
    db.add(IdempotencyKey(practice_id=m.practice_id, key=key, endpoint=endpoint,
                          request_hash=digest, status_code=status,
                          response=jsonable_encoder(body)))
    try:
        db.flush()
    except IntegrityError:
        # A concurrent request with the same key committed first. Raising rolls back this
        # request's own work too (one transaction), so the caller retries and gets the replay.
        raise ProblemError(409, "A request with this Idempotency-Key is already being "
                                "processed; retry shortly", "idempotency_in_progress") from None
    return status, body, False
