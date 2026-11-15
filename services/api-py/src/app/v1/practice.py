"""Consultations with notes, and remedy plans (cycle_days data, one active plan
per client) with start / complete / checkin."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.auth.deps import current_member
from app.tenancy.models import (
    Consultation,
    ConsultationNote,
    RemedyCheckin,
    RemedyItem,
    RemedyPlan,
    RemedyStatus,
)

from . import schemas as sc
from .common import (
    CLINICAL,
    STAFF,
    ProblemError,
    audit,
    idempotent,
    load_client,
    paginate,
)

router = APIRouter()

FACT_MARKER = re.compile(r"\{\{fact:([A-Za-z0-9_-]{1,16})\}\}")


def check_note_facts(body: str, facts: list[sc.NoteFact]) -> None:
    """Every {{fact:id}} marker in the body needs exactly one fact, and no fact may be unused."""
    ids = [f.id for f in facts]
    if len(set(ids)) != len(ids):
        raise ProblemError(422, "duplicate fact id", "validation_error")
    used = set(FACT_MARKER.findall(body))
    if used - set(ids):
        raise ProblemError(422, "note refers to a chart fact that was not supplied",
                           "validation_error")
    if set(ids) - used:
        raise ProblemError(422, "a pinned chart fact is not used in the note body",
                           "validation_error")


# ------------------------------------------------------------ consultations
def _consultation(db: Session, consultation_id: uuid.UUID) -> Consultation:
    c = db.scalar(select(Consultation).where(
        Consultation.id == consultation_id, Consultation.deleted_at.is_(None)))
    if c is None:
        raise ProblemError(404, "consultation not found", "not_found")
    return c


def _notes(db: Session, consultation_id: uuid.UUID) -> list[ConsultationNote]:
    return list(db.scalars(select(ConsultationNote).where(
        ConsultationNote.consultation_id == consultation_id,
        ConsultationNote.deleted_at.is_(None)).order_by(ConsultationNote.created_at)))


def _consultation_detail(db: Session, m: CurrentMember, c: Consultation) -> dict:
    base = sc.ConsultationOut.model_validate(c).model_dump()
    # Notes are clinical: assistants see consultations but not note bodies.
    base["notes"] = _notes(db, c.id) if m.role in CLINICAL else []
    return base


@router.post("/clients/{client_id}/consultations", status_code=201,
             response_model=sc.ConsultationEnvelope, tags=["consultations"],
             operation_id="createConsultation", summary="Record a consultation")
def create_consultation(client_id: uuid.UUID, body: sc.ConsultationIn, request: Request,
                        m: CurrentMember = Depends(require_roles(*CLINICAL)),
                        db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    c = Consultation(
        practice_id=m.practice_id, client_id=client.id, member_id=m.member_id,
        chart_artifact_id=body.chart_artifact_id,
        consulted_at=body.consulted_at or body.scheduled_at or datetime.now(tz=UTC),
        scheduled_at=body.scheduled_at, mode=body.mode, topic=body.topic, follow_up_date=body.follow_up_date,
        client_question=body.client_question)
    db.add(c)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise ProblemError(422, "chart_artifact_id does not exist in this practice",
                           "validation_error") from None
    if body.note:
        check_note_facts(body.note, body.note_facts)
        db.add(ConsultationNote(practice_id=m.practice_id, consultation_id=c.id,
                                author_member_id=m.member_id, body=body.note,
                                facts=[f.model_dump() for f in body.note_facts]))
        db.flush()
    audit(db, m, "consultation.created", "consultation", c.id, request,
          meta={"client_id": str(client.id)})
    db.refresh(c)
    return {"consultation": _consultation_detail(db, m, c)}


@router.get("/clients/{client_id}/consultations", response_model=sc.ConsultationPage,
            tags=["consultations"], operation_id="listConsultations",
            summary="Consultations for a client (newest first)")
def list_consultations(client_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200),
                       cursor: str | None = None,
                       m: CurrentMember = Depends(require_roles(*STAFF)),
                       db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    stmt = select(Consultation).where(Consultation.client_id == client.id,
                                      Consultation.deleted_at.is_(None))
    rows, nxt = paginate(db, stmt, Consultation, limit, cursor)
    return {"consultations": rows, "next_cursor": nxt}


@router.get("/consultations/{consultation_id}", response_model=sc.ConsultationEnvelope,
            tags=["consultations"], operation_id="getConsultation",
            summary="Consultation with notes (notes omitted for assistants)")
def get_consultation(consultation_id: uuid.UUID,
                     m: CurrentMember = Depends(require_roles(*STAFF)),
                     db: Session = Depends(tenant_db, scope="function")):
    c = _consultation(db, consultation_id)
    load_client(db, m, c.client_id)
    return {"consultation": _consultation_detail(db, m, c)}


@router.delete("/consultations/{consultation_id}", status_code=204, tags=["consultations"],
               operation_id="deleteConsultation", summary="Soft delete a consultation")
def delete_consultation(consultation_id: uuid.UUID, request: Request,
                        m: CurrentMember = Depends(require_roles(*CLINICAL)),
                        db: Session = Depends(tenant_db, scope="function")) -> None:
    c = _consultation(db, consultation_id)
    now = datetime.now(tz=UTC)
    c.deleted_at = now
    for n in _notes(db, c.id):
        n.deleted_at = now
    audit(db, m, "consultation.deleted", "consultation", c.id, request)


@router.post("/consultations/{consultation_id}/notes", status_code=201,
             response_model=sc.NoteEnvelope, tags=["consultations"],
             operation_id="addConsultationNote", summary="Add a note to a consultation")
def add_note(consultation_id: uuid.UUID, body: sc.NoteIn, request: Request,
             m: CurrentMember = Depends(require_roles(*CLINICAL)),
             db: Session = Depends(tenant_db, scope="function")):
    c = _consultation(db, consultation_id)
    check_note_facts(body.body, body.facts)
    note = ConsultationNote(practice_id=m.practice_id, consultation_id=c.id,
                            author_member_id=m.member_id, body=body.body,
                            facts=[f.model_dump() for f in body.facts])
    db.add(note)
    db.flush()
    audit(db, m, "consultation_note.created", "consultation_note", note.id, request,
          meta={"consultation_id": str(c.id)})
    db.refresh(note)
    return {"note": note}


@router.delete("/consultations/{consultation_id}/notes/{note_id}", status_code=204,
               tags=["consultations"], operation_id="deleteConsultationNote",
               summary="Soft delete a note")
def delete_note(consultation_id: uuid.UUID, note_id: uuid.UUID, request: Request,
                m: CurrentMember = Depends(require_roles(*CLINICAL)),
                db: Session = Depends(tenant_db, scope="function")) -> None:
    note = db.scalar(select(ConsultationNote).where(
        ConsultationNote.id == note_id, ConsultationNote.consultation_id == consultation_id,
        ConsultationNote.deleted_at.is_(None)))
    if note is None:
        raise ProblemError(404, "note not found", "not_found")
    note.deleted_at = datetime.now(tz=UTC)
    audit(db, m, "consultation_note.deleted", "consultation_note", note.id, request)


# ------------------------------------------------------------------ remedies
def _today() -> date:
    return datetime.now(tz=UTC).date()


def _plan(db: Session, m: CurrentMember, plan_id: uuid.UUID) -> RemedyPlan:
    plan = db.scalar(select(RemedyPlan).where(
        RemedyPlan.id == plan_id, RemedyPlan.deleted_at.is_(None)))
    if plan is None:
        raise ProblemError(404, "remedy plan not found", "not_found")
    try:
        load_client(db, m, plan.client_id)  # client role: own plans only
    except ProblemError:
        raise ProblemError(404, "remedy plan not found", "not_found") from None
    return plan


def _plan_json(db: Session, plan: RemedyPlan) -> dict:
    items = list(db.scalars(select(RemedyItem).where(
        RemedyItem.plan_id == plan.id, RemedyItem.deleted_at.is_(None))
        .order_by(RemedyItem.sort_order, RemedyItem.created_at)))
    done = dict(db.execute(
        select(RemedyCheckin.item_id, func.count()).where(
            RemedyCheckin.item_id.in_([i.id for i in items]), RemedyCheckin.done.is_(True),
            RemedyCheckin.checkin_date >= (plan.start_date or date.min))  # restart drops old days
        .group_by(RemedyCheckin.item_id)).all()) if items else {}
    today_done = set(db.scalars(select(RemedyCheckin.item_id).where(
        RemedyCheckin.item_id.in_([i.id for i in items]), RemedyCheckin.done.is_(True),
        RemedyCheckin.checkin_date == _today()))) if items else set()
    end = day = None
    if plan.start_date:
        end = plan.start_date + timedelta(days=plan.cycle_days - 1)
        if plan.status == RemedyStatus.active:
            day = (_today() - plan.start_date).days + 1
            day = day if day >= 1 else None
    out = sc.RemedyPlanOut.model_validate(plan).model_dump()
    out.update(end_date=end, day_number=day, items=[
        {**sc.RemedyItemOut.model_validate(i).model_dump(), "done_days": done.get(i.id, 0),
         "done_today": i.id in today_done}
        for i in items])
    return out


@router.post("/clients/{client_id}/remedy-plans", status_code=201,
             response_model=sc.RemedyPlanEnvelope, tags=["remedies"],
             operation_id="createRemedyPlan",
             summary="Create a draft remedy plan (cycle_days defaults to 43)")
def create_remedy_plan(client_id: uuid.UUID, body: sc.RemedyPlanIn, request: Request,
                       response: Response,
                       idempotency_key: str | None = Header(default=None,
                                                            alias="Idempotency-Key"),
                       m: CurrentMember = Depends(require_roles(*CLINICAL)),
                       db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)

    def run() -> tuple[int, dict]:
        plan = RemedyPlan(
            practice_id=m.practice_id, client_id=client.id, title=body.title,
            consultation_id=body.consultation_id, cycle_days=body.cycle_days,
            missed_day_policy=body.missed_day_policy, status=RemedyStatus.draft)
        db.add(plan)
        try:
            with db.begin_nested():
                db.flush()
        except IntegrityError:
            raise ProblemError(422, "consultation_id does not exist in this practice",
                               "validation_error") from None
        for item in body.items:
            db.add(RemedyItem(practice_id=m.practice_id, plan_id=plan.id,
                              **item.model_dump()))
        db.flush()
        audit(db, m, "remedy_plan.created", "remedy_plan", plan.id, request,
              meta={"client_id": str(client.id), "cycle_days": plan.cycle_days})
        db.refresh(plan)
        return 201, {"remedy_plan": _plan_json(db, plan)}

    status, out, _ = idempotent(db, m, f"POST /v1/clients/{client.id}/remedy-plans",
                                idempotency_key, body.model_dump(mode="json"), run)
    response.status_code = status
    return out


@router.get("/clients/{client_id}/remedy-plans", response_model=sc.RemedyPlanPage,
            tags=["remedies"], operation_id="listRemedyPlans",
            summary="Remedy plans for a client (newest first)")
def list_remedy_plans(client_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200),
                      cursor: str | None = None, m: CurrentMember = Depends(current_member),
                      db: Session = Depends(tenant_db, scope="function")):
    client = load_client(db, m, client_id)
    stmt = select(RemedyPlan).where(RemedyPlan.client_id == client.id,
                                    RemedyPlan.deleted_at.is_(None))
    rows, nxt = paginate(db, stmt, RemedyPlan, limit, cursor)
    return {"remedy_plans": [_plan_json(db, p) for p in rows], "next_cursor": nxt}


@router.get("/remedy-plans/{plan_id}", response_model=sc.RemedyPlanEnvelope, tags=["remedies"],
            operation_id="getRemedyPlan", summary="Remedy plan with items and progress")
def get_remedy_plan(plan_id: uuid.UUID, m: CurrentMember = Depends(current_member),
                    db: Session = Depends(tenant_db, scope="function")):
    return {"remedy_plan": _plan_json(db, _plan(db, m, plan_id))}


@router.post("/remedy-plans/{plan_id}/items", status_code=201,
             response_model=sc.RemedyItemEnvelope, tags=["remedies"],
             operation_id="addRemedyItem", summary="Add an item to a draft or active plan")
def add_remedy_item(plan_id: uuid.UUID, body: sc.RemedyItemIn, request: Request,
                    m: CurrentMember = Depends(require_roles(*CLINICAL)),
                    db: Session = Depends(tenant_db, scope="function")):
    plan = _plan(db, m, plan_id)
    if plan.status not in (RemedyStatus.draft, RemedyStatus.active):
        raise ProblemError(409, f"plan is {plan.status.value}", "invalid_state")
    item = RemedyItem(practice_id=m.practice_id, plan_id=plan.id, **body.model_dump())
    db.add(item)
    db.flush()
    audit(db, m, "remedy_item.created", "remedy_item", item.id, request,
          meta={"plan_id": str(plan.id)})
    db.refresh(item)
    return {"item": item}


@router.post("/remedy-plans/{plan_id}/start", response_model=sc.RemedyPlanEnvelope,
             tags=["remedies"], operation_id="startRemedyPlan",
             summary="Activate a draft plan; 409 if the client already has an active plan")
def start_remedy_plan(plan_id: uuid.UUID, request: Request,
                      body: sc.RemedyStartIn | None = None,
                      m: CurrentMember = Depends(require_roles(*CLINICAL)),
                      db: Session = Depends(tenant_db, scope="function")):
    plan = _plan(db, m, plan_id)
    if plan.status != RemedyStatus.draft:
        raise ProblemError(409, f"only a draft plan can start (plan is {plan.status.value})",
                           "invalid_state")
    n_items = db.scalar(select(func.count()).select_from(RemedyItem).where(
        RemedyItem.plan_id == plan.id, RemedyItem.deleted_at.is_(None)))
    if not n_items:
        raise ProblemError(409, "add at least one item before starting", "invalid_state")
    plan.status = RemedyStatus.active
    plan.start_date = (body.start_date if body and body.start_date else _today())
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise ProblemError(409, "the client already has an active remedy plan",
                           "active_plan_exists") from None
    audit(db, m, "remedy_plan.started", "remedy_plan", plan.id, request)
    db.refresh(plan)
    return {"remedy_plan": _plan_json(db, plan)}


@router.post("/remedy-plans/{plan_id}/complete", response_model=sc.RemedyPlanEnvelope,
             tags=["remedies"], operation_id="completeRemedyPlan",
             summary="Mark an active plan completed")
def complete_remedy_plan(plan_id: uuid.UUID, request: Request,
                         m: CurrentMember = Depends(require_roles(*CLINICAL)),
                         db: Session = Depends(tenant_db, scope="function")):
    plan = _plan(db, m, plan_id)
    if plan.status != RemedyStatus.active:
        raise ProblemError(409, f"only an active plan can complete (plan is "
                                f"{plan.status.value})", "invalid_state")
    plan.status = RemedyStatus.completed
    db.flush()
    audit(db, m, "remedy_plan.completed", "remedy_plan", plan.id, request)
    db.refresh(plan)
    return {"remedy_plan": _plan_json(db, plan)}


@router.post("/remedy-plans/{plan_id}/cancel", response_model=sc.RemedyPlanEnvelope,
             tags=["remedies"], operation_id="cancelRemedyPlan",
             summary="Cancel a draft or active plan (frees the active slot)")
def cancel_remedy_plan(plan_id: uuid.UUID, request: Request,
                       m: CurrentMember = Depends(require_roles(*CLINICAL)),
                       db: Session = Depends(tenant_db, scope="function")):
    plan = _plan(db, m, plan_id)
    if plan.status not in (RemedyStatus.draft, RemedyStatus.active):
        raise ProblemError(409, f"plan is {plan.status.value}", "invalid_state")
    plan.status = RemedyStatus.cancelled
    db.flush()
    audit(db, m, "remedy_plan.cancelled", "remedy_plan", plan.id, request)
    db.refresh(plan)
    return {"remedy_plan": _plan_json(db, plan)}


@router.post("/remedy-plans/{plan_id}/items/{item_id}/checkins",
             response_model=sc.CheckinEnvelope, tags=["remedies"],
             operation_id="checkinRemedyItem",
             summary="Record (or overwrite) the check-in for one day of an active plan")
def checkin(plan_id: uuid.UUID, item_id: uuid.UUID, body: sc.CheckinIn,
            m: CurrentMember = Depends(current_member), db: Session = Depends(tenant_db, scope="function")):
    plan = _plan(db, m, plan_id)
    if plan.status != RemedyStatus.active or plan.start_date is None:
        raise ProblemError(409, "check-ins are only accepted on an active plan",
                           "invalid_state")
    item = db.scalar(select(RemedyItem).where(
        RemedyItem.id == item_id, RemedyItem.plan_id == plan.id,
        RemedyItem.deleted_at.is_(None)))
    if item is None:
        raise ProblemError(404, "remedy item not found", "not_found")
    day = body.checkin_date or _today()
    last = plan.start_date + timedelta(days=plan.cycle_days - 1)
    if not plan.start_date <= day <= last:
        raise ProblemError(
            422, f"check-in date must fall in the cycle {plan.start_date}..{last}",
            "validation_error")
    if day > _today() + timedelta(days=1):  # one day of slack for client time zones
        raise ProblemError(422, "check-in date is in the future", "validation_error")
    row = db.scalar(select(RemedyCheckin).where(
        RemedyCheckin.item_id == item.id, RemedyCheckin.checkin_date == day))
    if row is None:
        row = RemedyCheckin(practice_id=m.practice_id, item_id=item.id, checkin_date=day,
                            done=body.done, note=body.note)
        db.add(row)
    else:
        row.done, row.note = body.done, body.note
    db.flush()
    db.refresh(row)
    return {"checkin": row}

