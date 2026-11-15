"""Clients, consents and versioned birth records."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.auth.deps import current_member
from app.billing.entitlements import require_entitlement
from app.notify import due
from app.privacy import service as privacy
from app.privacy.blind import find_clients
from app.tenancy.models import (
    BirthRecord,
    Client,
    ClientTag,
    Consent,
    ConsentPurpose,
    Practice,
    TimeSource,
)
from nakshatra_core.time import local_time_status

from . import insight
from . import schemas as sc
from .common import (
    CLINICAL,
    STAFF,
    ProblemError,
    audit,
    load_client,
    paginate,
)

router = APIRouter()


# ----------------------------------------------------------------- clients
@router.post("/clients", status_code=201, response_model=sc.ClientEnvelope, tags=["clients"],
             dependencies=[Depends(require_entitlement("clients"))], operation_id="createClient", summary="Create a client")
def create_client(body: sc.ClientIn, request: Request,
                  m: CurrentMember = Depends(require_roles(*STAFF)),
                  db: Session = Depends(tenant_db, scope="function")):
    client = Client(practice_id=m.practice_id, created_by_member_id=m.member_id,
                    **body.model_dump())
    db.add(client)
    db.flush()
    audit(db, m, "client.created", "client", client.id, request)
    db.refresh(client)
    return {"client": client}


SORTS = ("recent", "name", "follow_up", "last_consult")
FOLLOW_UP_DAYS = 7


def _offset_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        pad = "=" * (-len(cursor) % 4)
        kind, n = json.loads(base64.urlsafe_b64decode(cursor + pad))
        if kind != "o" or not isinstance(n, int) or n < 0:
            raise ValueError
        return n
    except Exception:
        raise ProblemError(400, "invalid cursor", "invalid_cursor") from None


def _encode_offset(n: int) -> str:
    return base64.urlsafe_b64encode(json.dumps(["o", n]).encode()).decode().rstrip("=")


@router.get("/clients", response_model=sc.ClientPage, tags=["clients"],
            operation_id="listClients",
            summary="List clients with lagna, running dasha, last visit and next follow-up; "
                    "filter by tag, rectification and follow-up, and sort")
def list_clients(q: str | None = Query(default=None, max_length=100,
                                       description="Case-insensitive name search"),
                 email: str | None = Query(default=None, max_length=320,
                                           description="Exact contact email (blind index)"),
                 phone: str | None = Query(default=None, max_length=32,
                                           description="Exact contact phone (blind index)"),
                 tag: str | None = Query(default=None, max_length=40,
                                         description="Only clients carrying this tag"),
                 needs_rectify: bool | None = Query(
                     default=None, description="Birth time unsure or rectification open"),
                 follow_up_due: bool | None = Query(
                     default=None, description="Open follow-up due within 7 days (or overdue)"),
                 sort: Literal["recent", "name", "follow_up", "last_consult"] = Query(
                     default="recent", description="recent = newest first"),
                 limit: int = Query(default=50, ge=1, le=200),
                 cursor: str | None = None,
                 m: CurrentMember = Depends(require_roles(*STAFF)),
                 db: Session = Depends(tenant_db, scope="function")):
    now = datetime.now(tz=UTC)
    stmt = select(Client.id, Client.display_name, Client.created_at).where(
        Client.deleted_at.is_(None))
    if email is not None or phone is not None:
        ids = [c.id for c in find_clients(db, email=email, phone=phone)]
        stmt = stmt.where(Client.id.in_(ids))
    if q:
        like = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Client.display_name.ilike(f"%{like}%", escape="\\"))
    base = [tuple(r) for r in db.execute(stmt)]

    tags = insight.tags_by_client(db)
    flags = insight.rectify_flags(db)
    timing = insight.consultation_timing(db, now)
    practice = db.scalar(select(Practice))
    today = due.local_today(now, practice.timezone)
    horizon = today + timedelta(days=FOLLOW_UP_DAYS)

    def next_follow_up(cid):
        t = timing.get(cid)
        return t.next_follow_up if t else None

    def is_due(cid) -> bool:
        d = next_follow_up(cid)
        return d is not None and d <= horizon

    def unsure(cid) -> bool:
        return flags.get(cid, (False, None))[0]

    tag_key = tag.strip().casefold() if tag else None
    rows = []
    for cid, name, created in base:
        mine = tags.get(cid, [])
        if tag_key and tag_key not in {t.casefold() for t in mine}:
            continue
        if needs_rectify is not None and unsure(cid) != needs_rectify:
            continue
        if follow_up_due is not None and is_due(cid) != follow_up_due:
            continue
        rows.append((cid, name, created))

    if sort == "name":
        rows.sort(key=lambda r: (r[1].casefold(), str(r[0])))
    elif sort == "follow_up":
        rows.sort(key=lambda r: (next_follow_up(r[0]) or date.max, r[1].casefold(), str(r[0])))
    elif sort == "last_consult":
        def last_key(r):
            t = timing.get(r[0])
            return (0, -t.last.timestamp()) if t and t.last else (1, 0.0)
        rows.sort(key=lambda r: (*last_key(r), str(r[0])))
    else:
        rows.sort(key=lambda r: (r[2], str(r[0])), reverse=True)

    start = _offset_cursor(cursor)
    page = rows[start:start + limit]
    nxt = _encode_offset(start + limit) if start + limit < len(rows) else None
    ids = [r[0] for r in page]
    clients = {c.id: c for c in db.scalars(select(Client).where(Client.id.in_(ids)))}
    facts = insight.latest_chart_facts(db, ids, now)

    out = []
    for cid in ids:
        base_row = sc.ClientOut.model_validate(clients[cid]).model_dump()
        f, t = facts.get(cid), timing.get(cid)
        out.append({
            **base_row, "tags": tags.get(cid, []),
            "latest_chart_id": f.chart_id if f else None,
            "lagna_sign": f.lagna_sign if f else None,
            "lagna_degree": f.lagna_degree if f else None,
            "current_dasha": ({"maha": f.maha, "antar": f.antar, "antar_ends": f.antar_ends}
                              if f and f.maha else None),
            "last_consultation_at": t.last if t else None,
            "next_consultation_at": t.next_booked if t else None,
            "next_follow_up": t.next_follow_up if t else None,
            "needs_rectify": unsure(cid),
        })

    tag_counts: dict[str, int] = {}
    for cid, _name, _created in base:
        for tg in tags.get(cid, []):
            tag_counts[tg] = tag_counts.get(tg, 0) + 1
    facets = {
        "total": len(base),
        "needs_rectify": sum(1 for cid, *_ in base if unsure(cid)),
        "follow_up_due": sum(1 for cid, *_ in base if is_due(cid)),
        "tags": [{"tag": k, "count": v} for k, v in
                 sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0].casefold()))],
    }
    return {"clients": out, "next_cursor": nxt, "facets": facets}


# -------------------------------------------------------------------- tags
_TAG_BAD = re.compile(r"[\x00-\x1f\x7f]")


def _clean_tags(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        tag = " ".join(t.split())
        if not tag or len(tag) > 40 or _TAG_BAD.search(tag):
            raise ProblemError(422, "each tag must be 1 to 40 characters, no control characters",
                               "validation_error")
        if tag.casefold() not in seen:
            seen.add(tag.casefold())
            out.append(tag)
    return out


@router.get("/client-tags", response_model=sc.TagCountList, tags=["clients"],
            operation_id="listClientTags", summary="Every tag in use in the practice, with counts")
def list_client_tags(m: CurrentMember = Depends(require_roles(*STAFF)),
                     db: Session = Depends(tenant_db, scope="function")):
    rows = db.execute(select(ClientTag.tag, func.count()).join(
        Client, (Client.id == ClientTag.client_id) & (Client.practice_id == ClientTag.practice_id))
        .where(Client.deleted_at.is_(None)).group_by(ClientTag.tag)
        .order_by(func.count().desc(), ClientTag.tag))
    return {"tags": [{"tag": t, "count": n} for t, n in rows]}


@router.get("/clients/{client_id}/tags", response_model=sc.TagsOut, tags=["clients"],
            operation_id="getClientTags", summary="Tags on a client")
def get_client_tags(client_id: uuid.UUID, m: CurrentMember = Depends(require_roles(*STAFF)),
                    db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    return {"tags": insight.tags_by_client(db, [client.id]).get(client.id, [])}


@router.put("/clients/{client_id}/tags", response_model=sc.TagsOut, tags=["clients"],
            operation_id="setClientTags", summary="Replace the tags on a client")
def set_client_tags(client_id: uuid.UUID, body: sc.TagsIn, request: Request,
                    m: CurrentMember = Depends(require_roles(*STAFF)),
                    db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    wanted = _clean_tags(body.tags)
    existing = {t.tag: t for t in db.scalars(select(ClientTag).where(
        ClientTag.client_id == client.id))}
    keep = {t.casefold() for t in wanted}
    for tag, row in existing.items():
        if tag.casefold() not in keep:
            db.delete(row)
    have = {t.casefold() for t in existing}
    for tag in wanted:
        if tag.casefold() not in have:
            db.add(ClientTag(practice_id=m.practice_id, client_id=client.id, tag=tag))
    db.flush()
    audit(db, m, "client.tags_updated", "client", client.id, request,
          meta={"count": len(wanted)})
    return {"tags": insight.tags_by_client(db, [client.id]).get(client.id, [])}


@router.get("/clients/{client_id}", response_model=sc.ClientEnvelope, tags=["clients"],
            operation_id="getClient", summary="Get a client (client role: own record only)")
def get_client(client_id: uuid.UUID, m: CurrentMember = Depends(current_member),
               db: Session = Depends(tenant_db, scope="function")):
    return {"client": load_client(db, m, client_id)}


@router.patch("/clients/{client_id}", response_model=sc.ClientEnvelope, tags=["clients"],
              operation_id="updateClient", summary="Update a client")
def update_client(client_id: uuid.UUID, body: sc.ClientPatch, request: Request,
                  m: CurrentMember = Depends(require_roles(*STAFF)),
                  db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    changes = body.model_dump(exclude_unset=True)
    if "display_name" in changes and changes["display_name"] is None:
        raise ProblemError(422, "display_name cannot be null", "validation_error")
    before = {k: getattr(client, k) for k in changes}
    for key, value in changes.items():
        setattr(client, key, value)
    db.flush()
    privacy.log_corrections(
        db, practice_id=m.practice_id, client_id=client.id, entity_type="client",
        entity_id=client.id, member_id=m.member_id,
        reason=request.headers.get("x-correction-reason"),
        changes={k: (before[k], v) for k, v in changes.items()})
    audit(db, m, "client.updated", "client", client.id, request,
          meta={"fields": sorted(changes)})
    db.refresh(client)
    return {"client": client}


@router.delete("/clients/{client_id}", status_code=204, tags=["clients"],
               operation_id="deleteClient", summary="Soft delete a client")
def delete_client(client_id: uuid.UUID, request: Request,
                  m: CurrentMember = Depends(require_roles(*CLINICAL)),
                  db: Session = Depends(tenant_db, scope="function")) -> None:
    client = load_client(db, m, client_id)
    client.deleted_at = datetime.now(tz=UTC)
    audit(db, m, "client.deleted", "client", client.id, request)


# ---------------------------------------------------------------- consents
def _active(db: Session, client_id: uuid.UUID, purpose: ConsentPurpose) -> list[Consent]:
    return list(db.scalars(select(Consent).where(
        Consent.client_id == client_id, Consent.purpose == purpose,
        Consent.withdrawn_at.is_(None)).order_by(Consent.granted_at.desc())))


@router.post("/clients/{client_id}/consents", response_model=sc.ConsentEnvelope,
             tags=["consents"], operation_id="recordConsent", status_code=201,
             summary="Record consent for a purpose (200 with the existing row if the same "
                     "notice version is already active)")
def record_consent(client_id: uuid.UUID, body: sc.ConsentIn, request: Request,
                   response: Response, m: CurrentMember = Depends(current_member),
                   db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    existing = [c for c in _active(db, client.id, body.purpose)
                if c.notice_version == body.notice_version]
    if existing:
        response.status_code = 200
        return {"consent": existing[0]}
    consent = Consent(
        practice_id=m.practice_id, client_id=client.id, purpose=body.purpose,
        notice_version=body.notice_version, notice_text=body.notice_text,
        notice_text_sha256=(hashlib.sha256(body.notice_text.encode()).hexdigest()
                            if body.notice_text else None),
        notice_language=body.notice_language, channel=body.channel,
        granted_at=datetime.now(tz=UTC), collected_by_member_id=m.member_id)
    db.add(consent)
    db.flush()
    privacy.issue_receipt(db, consent, "granted", m.member_id)
    audit(db, m, "consent.granted", "consent", consent.id, request,
          meta={"purpose": body.purpose.value, "notice_version": body.notice_version,
                "client_id": str(client.id)})
    db.refresh(consent)
    return {"consent": consent}


@router.post("/clients/{client_id}/consents/{purpose}/withdraw",
             response_model=sc.ConsentList, tags=["consents"],
             operation_id="withdrawConsent",
             summary="Withdraw every active consent for a purpose")
def withdraw_consent(client_id: uuid.UUID, purpose: ConsentPurpose, request: Request,
                     m: CurrentMember = Depends(current_member),
                     db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    active = _active(db, client.id, purpose)
    if not active:
        raise ProblemError(404, "no active consent for that purpose", "not_found")
    now = datetime.now(tz=UTC)
    for c in active:
        c.withdrawn_at = now
    db.flush()
    for c in active:
        privacy.issue_receipt(db, c, "withdrawn", m.member_id)
    audit(db, m, "consent.withdrawn", "consent", active[0].id, request,
          meta={"purpose": purpose.value, "client_id": str(client.id)})
    return _consent_state(db, client.id)


def _consent_state(db: Session, client_id: uuid.UUID) -> dict:
    rows = list(db.scalars(select(Consent).where(Consent.client_id == client_id)
                           .order_by(Consent.granted_at.desc(), Consent.id)))
    active = {p.value: False for p in ConsentPurpose}
    for c in rows:
        if c.withdrawn_at is None:
            active[c.purpose.value] = True
    return {"consents": rows, "active": active}


@router.get("/clients/{client_id}/consents", response_model=sc.ConsentList,
            tags=["consents"], operation_id="listConsents",
            summary="Consent history and the currently active purposes")
def list_consents(client_id: uuid.UUID, m: CurrentMember = Depends(current_member),
                  db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    return _consent_state(db, client.id)


# ----------------------------------------------------------- birth records
@router.post("/clients/{client_id}/birth-records", status_code=201,
             response_model=sc.BirthRecordEnvelope, tags=["birth-records"],
             operation_id="createBirthRecord",
             summary="Add a birth record; an existing one is superseded, never overwritten")
def create_birth_record(client_id: uuid.UUID, body: sc.BirthRecordIn, request: Request,
                        m: CurrentMember = Depends(require_roles(*STAFF)),
                        db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    try:
        ZoneInfo(body.timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ProblemError(422, "unknown IANA timezone", "validation_error") from None
    if body.time_source == TimeSource.unknown:
        birth_time = None
    elif body.birth_time is None:
        raise ProblemError(422, "birth_time is required unless time_source is unknown",
                           "validation_error")
    else:
        birth_time = body.birth_time
    if birth_time is not None and local_time_status(
            body.birth_date.isoformat(), birth_time.strftime("%H:%M"),
            body.timezone_name) == "gap":
        raise ProblemError(422, "that local time does not exist in this time zone (clocks "
                                "skipped it); check the date, time and zone", "validation_error")
    latest = db.scalar(select(BirthRecord).where(BirthRecord.client_id == client.id)
                       .order_by(BirthRecord.version.desc()).limit(1))
    data = body.model_dump(exclude={"birth_time"})
    record = BirthRecord(
        practice_id=m.practice_id, client_id=client.id, birth_time=birth_time,
        version=(latest.version + 1) if latest else 1,
        supersedes_id=latest.id if latest else None, **data)
    db.add(record)
    try:
        db.flush()
    except IntegrityError:  # two concurrent edits picked the same next version
        raise ProblemError(409, "the birth record was changed at the same time; reload and "
                                "retry", "conflict") from None
    if latest is not None:
        privacy.log_corrections(
            db, practice_id=m.practice_id, client_id=client.id, entity_type="birth_record",
            entity_id=record.id, member_id=m.member_id,
            reason=request.headers.get("x-correction-reason"),
            changes={f: (getattr(latest, f), getattr(record, f)) for f in privacy.BIRTH_FIELDS})
    audit(db, m, "birth_record.created", "birth_record", record.id, request,
          meta={"version": record.version, "client_id": str(client.id)})
    db.refresh(record)
    return {"birth_record": record}


@router.get("/clients/{client_id}/birth-records", response_model=sc.BirthRecordPage,
            tags=["birth-records"], operation_id="listBirthRecords",
            summary="Birth record versions (newest first)")
def list_birth_records(client_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200),
                       cursor: str | None = None,
                       m: CurrentMember = Depends(current_member),
                       db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    stmt = select(BirthRecord).where(BirthRecord.client_id == client.id,
                                     BirthRecord.deleted_at.is_(None))
    rows, nxt = paginate(db, stmt, BirthRecord, limit, cursor)
    return {"birth_records": rows, "next_cursor": nxt}


def latest_birth_record(db: Session, client_id: uuid.UUID) -> BirthRecord | None:
    return db.scalar(select(BirthRecord).where(
        BirthRecord.client_id == client_id, BirthRecord.deleted_at.is_(None))
        .order_by(BirthRecord.version.desc()).limit(1))

