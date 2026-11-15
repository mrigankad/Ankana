"""Client portal summary and practice settings (small read/write helpers for the web app)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.auth.deps import current_member
from app.tenancy.models import (
    BirthRecord,
    ChartArtifact,
    Client,
    Consultation,
    Member,
    Practice,
    Report,
    Role,
)

from .common import STAFF, ProblemError, audit

router = APIRouter()
DOWNLOAD_TTL = 900


class PracticePatch(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _practice_json(p: Practice) -> dict:
    return {"id": str(p.id), "name": p.name, "timezone": p.timezone}


@router.get("/practice", tags=["practice"], operation_id="getPractice",
            summary="The practice name and time zone")
def get_practice(m: CurrentMember = Depends(require_roles(*STAFF)),
                 db: Session = Depends(tenant_db, scope="function")) -> dict:
    return _practice_json(db.get(Practice, m.practice_id))


@router.patch("/practice", tags=["practice"], operation_id="renamePractice",
              summary="Rename the practice (owner)")
def rename_practice(body: PracticePatch, request: Request,
                    m: CurrentMember = Depends(require_roles(Role.owner)),
                    db: Session = Depends(tenant_db, scope="function")) -> dict:
    name = " ".join(body.name.split())
    if not name:
        raise ProblemError(422, "The practice needs a name.", "validation_error")
    p = db.get(Practice, m.practice_id)
    p.name = name
    db.flush()
    audit(db, m, "practice.renamed", "practice", p.id, request)
    return _practice_json(p)


@router.get("/portal/summary", tags=["portal"], operation_id="getPortalSummary",
            summary="Everything a client-portal user sees on their home page")
def portal_summary(request: Request, m: CurrentMember = Depends(current_member),
                   db: Session = Depends(tenant_db, scope="function")) -> dict:
    if m.role != Role.client:
        raise ProblemError(403, "requires role: client", "forbidden")
    client_id = db.scalar(select(Member.client_id).where(Member.id == m.member_id))
    client = db.scalar(select(Client).where(Client.id == client_id, Client.deleted_at.is_(None))) \
        if client_id else None
    if client is None:
        raise ProblemError(404, "client not found", "not_found")
    practice = db.get(Practice, m.practice_id)
    today = datetime.now(tz=UTC).date()

    # The next thing on the calendar: a future consultation, else the latest follow-up date.
    consults = list(db.scalars(select(Consultation).where(
        Consultation.client_id == client.id, Consultation.deleted_at.is_(None))
        .order_by(Consultation.consulted_at.desc())))
    upcoming = None
    now = datetime.now(tz=UTC)
    future = [c for c in consults if c.consulted_at >= now]
    if future:
        c = min(future, key=lambda c: c.consulted_at)
        upcoming = {"id": str(c.id), "at": c.consulted_at.isoformat(), "date": None,
                    "mode": c.mode, "topic": c.topic, "kind": "consultation"}
    else:
        follow = [c for c in consults if c.follow_up_date and c.follow_up_date >= today]
        if follow:
            c = min(follow, key=lambda c: c.follow_up_date)
            upcoming = {"id": str(c.id), "at": None, "date": c.follow_up_date.isoformat(),
                        "mode": c.mode, "topic": c.topic, "kind": "follow_up"}

    rows = db.execute(
        select(Report).join(ChartArtifact, ChartArtifact.id == Report.chart_artifact_id)
        .join(BirthRecord, BirthRecord.id == ChartArtifact.birth_record_id)
        .where(BirthRecord.client_id == client.id, Report.deleted_at.is_(None),
               Report.status == "done").order_by(Report.created_at.desc()).limit(20)
    ).scalars()
    reports = []
    for r in rows:
        url = request.app.state.storage.signed_url(
            r.storage_key, DOWNLOAD_TTL, filename=f"report-{r.id}.pdf") if r.storage_key else None
        reports.append({"id": str(r.id), "template": r.template, "language": r.language,
                        "created_at": r.created_at.isoformat(), "size_bytes": r.size_bytes,
                        "download_url": url})
    audit(db, m, "portal.viewed", "client", client.id, request)
    return {"client_id": str(client.id), "display_name": client.display_name,
            "practice_name": practice.name, "next_appointment": upcoming, "reports": reports,
            "today": today.isoformat()}
