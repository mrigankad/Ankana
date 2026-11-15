"""/v1 privacy routes: data principal rights, legal hold, retention, receipts.

Mounted by install_privacy(app) after the tenancy layer.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.auth.deps import current_member
from app.tenancy.models import Client, Practice, Role
from app.v1.common import CLINICAL, ProblemError, audit

from . import service
from .models import ConsentReceipt, CorrectionLog, PrivacyRequest

DOWNLOAD_TTL = 900


class EraseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500,
                        description="Why the client is being erased (kept encrypted)")


class LegalHoldIn(BaseModel):
    hold: bool
    reason: str | None = Field(default=None, max_length=500)


class SettingsIn(BaseModel):
    retention_inactive_years: int | None = Field(default=None, ge=1, le=50)
    retention_auto_apply: bool = False


class PracticeDeleteIn(BaseModel):
    confirm_name: str = Field(description="Must equal the practice name exactly")
    reason: str | None = Field(default=None, max_length=500)


class RetentionApplyIn(BaseModel):
    confirm: bool


def _rights_client(db: Session, m: CurrentMember, client_id: uuid.UUID) -> Client:
    """The client for a rights request (soft-deleted clients included). Portal
    members only ever reach their own record; staff outside CLINICAL are refused."""
    if m.role == Role.client:
        from app.tenancy.models import Member

        if db.scalar(select(Member.client_id).where(Member.id == m.member_id)) != client_id:
            raise ProblemError(404, "client not found", "not_found")
    elif m.role not in CLINICAL:
        raise ProblemError(403, "requires role: owner, astrologer", "forbidden")
    client = service.get_client_any(db, client_id)
    if client is None:
        raise ProblemError(404, "client not found", "not_found")
    return client


def _request_json(request: Request, r: PrivacyRequest) -> dict:
    out = {
        "id": str(r.id), "kind": r.kind, "status": r.status, "client_id":
        str(r.client_id) if r.client_id else None, "result": r.result, "error": r.error,
        "created_at": r.created_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "download_url": None, "download_expires_in": None,
    }
    if r.status == "done" and r.result_key:
        out["download_url"] = request.app.state.storage.signed_url(
            r.result_key, DOWNLOAD_TTL, filename=f"export-{r.id}.zip")
        out["download_expires_in"] = DOWNLOAD_TTL
    return out


def build_privacy_router() -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["privacy"])
    owner = require_roles(Role.owner)
    clinical = require_roles(*CLINICAL)

    # ----------------------------------------------------- client rights
    @router.post("/clients/{client_id}/export", status_code=202, operation_id="exportClient",
                 summary="Export everything held about a client (async, signed ZIP)")
    def export_client(client_id: uuid.UUID, request: Request,
                      m: CurrentMember = Depends(current_member),
                      db: Session = Depends(tenant_db, scope="function")) -> dict:
        client = _rights_client(db, m, client_id)
        if client.erased_at is not None:
            raise ProblemError(409, "client has been erased; nothing to export", "erased")
        req = service.create_request(db, practice_id=m.practice_id, kind="client_export",
                                     client_id=client.id, member_id=m.member_id)
        return _request_json(request, req)

    @router.post("/clients/{client_id}/erase", status_code=202, operation_id="eraseClient",
                 summary="Erase a client (crypto/overwrite, cascade, tombstone); refused under "
                         "legal hold")
    def erase_client(client_id: uuid.UUID, body: EraseIn, request: Request,
                     m: CurrentMember = Depends(clinical),
                     db: Session = Depends(tenant_db, scope="function")) -> dict:
        client = _rights_client(db, m, client_id)
        if client.erased_at is not None:
            raise ProblemError(409, "client already erased", "already_erased")
        if client.legal_hold:
            raise ProblemError(409, "client is under legal hold", "legal_hold")
        req = service.create_request(db, practice_id=m.practice_id, kind="client_erase",
                                     client_id=client.id, reason=body.reason,
                                     member_id=m.member_id)
        return _request_json(request, req)

    @router.put("/clients/{client_id}/legal-hold", operation_id="setLegalHold",
                summary="Place or release a legal hold on a client")
    def legal_hold(client_id: uuid.UUID, body: LegalHoldIn,
                   m: CurrentMember = Depends(clinical),
                   db: Session = Depends(tenant_db, scope="function")) -> dict:
        client = _rights_client(db, m, client_id)
        try:
            service.set_legal_hold(db, m.practice_id, client, body.hold, body.reason, m.member_id)
        except service.AlreadyErasedError:
            raise ProblemError(409, "client already erased", "already_erased") from None
        return {"client_id": str(client.id), "legal_hold": client.legal_hold,
                "legal_hold_at": client.legal_hold_at.isoformat() if client.legal_hold_at else None}

    @router.get("/clients/{client_id}/corrections", operation_id="listCorrections",
                summary="Log of corrections made to the client's personal data")
    def corrections(client_id: uuid.UUID, m: CurrentMember = Depends(current_member),
                    db: Session = Depends(tenant_db, scope="function")) -> dict:
        if m.role == Role.client or m.role in CLINICAL:
            client = _rights_client(db, m, client_id)
        else:
            raise ProblemError(403, "requires role: owner, astrologer", "forbidden")
        rows = db.scalars(select(CorrectionLog).where(CorrectionLog.client_id == client.id)
                          .order_by(CorrectionLog.created_at))
        return {"corrections": [{
            "id": str(r.id), "entity_type": r.entity_type, "entity_id": r.entity_id,
            "field": r.field, "old_value": r.old_value, "new_value": r.new_value,
            "reason": r.reason, "created_at": r.created_at.isoformat()} for r in rows]}

    @router.get("/clients/{client_id}/consent-receipts", operation_id="listConsentReceipts",
                summary="Immutable receipts for every consent grant and withdrawal")
    def receipts(client_id: uuid.UUID, m: CurrentMember = Depends(current_member),
                 db: Session = Depends(tenant_db, scope="function")) -> dict:
        from app.v1.common import load_client

        client = load_client(db, m, client_id)
        rows = db.scalars(select(ConsentReceipt).where(ConsentReceipt.client_id == client.id)
                          .order_by(ConsentReceipt.occurred_at, ConsentReceipt.id))
        return {"receipts": [service.receipt_json(db, r) for r in rows]}

    @router.get("/clients/{client_id}/consent-receipts/{receipt_id}",
                operation_id="getConsentReceipt", summary="One consent receipt, with verification")
    def receipt(client_id: uuid.UUID, receipt_id: uuid.UUID,
                m: CurrentMember = Depends(current_member),
                db: Session = Depends(tenant_db, scope="function")) -> dict:
        from app.v1.common import load_client

        client = load_client(db, m, client_id)
        r = db.scalar(select(ConsentReceipt).where(
            ConsentReceipt.id == receipt_id, ConsentReceipt.client_id == client.id))
        if r is None:
            raise ProblemError(404, "receipt not found", "not_found")
        return service.receipt_json(db, r)

    # ---------------------------------------------------------- requests
    @router.get("/privacy/requests/{request_id}", operation_id="getPrivacyRequest",
                summary="Status of an export/erasure/retention request (signed download link "
                        "when ready)")
    def get_request(request_id: uuid.UUID, request: Request,
                    m: CurrentMember = Depends(current_member),
                    db: Session = Depends(tenant_db, scope="function")) -> dict:
        r = db.get(PrivacyRequest, request_id)
        if r is None:
            raise ProblemError(404, "request not found", "not_found")
        if m.role == Role.client:
            from app.tenancy.models import Member

            own = db.scalar(select(Member.client_id).where(Member.id == m.member_id))
            if r.client_id != own:
                raise ProblemError(404, "request not found", "not_found")
        elif m.role not in CLINICAL:
            raise ProblemError(403, "requires role: owner, astrologer", "forbidden")
        return _request_json(request, r)

    @router.get("/privacy/requests", operation_id="listPrivacyRequests",
                summary="Recent privacy requests for the practice")
    def list_requests(request: Request, m: CurrentMember = Depends(clinical),
                      db: Session = Depends(tenant_db, scope="function")) -> dict:
        rows = db.scalars(select(PrivacyRequest).order_by(PrivacyRequest.created_at.desc())
                          .limit(100))
        return {"requests": [_request_json(request, r) for r in rows]}

    # ---------------------------------------------------------- practice
    @router.post("/practice/export", status_code=202, operation_id="exportPractice",
                 summary="Export all practice data (async, signed ZIP)")
    def export_practice(request: Request, m: CurrentMember = Depends(owner),
                        db: Session = Depends(tenant_db, scope="function")) -> dict:
        req = service.create_request(db, practice_id=m.practice_id, kind="practice_export",
                                     member_id=m.member_id)
        return _request_json(request, req)

    @router.post("/practice/delete", status_code=202, operation_id="deletePractice",
                 summary="Delete the practice account: erase all clients, destroy keys")
    def delete_practice(body: PracticeDeleteIn, request: Request,
                        m: CurrentMember = Depends(owner),
                        db: Session = Depends(tenant_db, scope="function")) -> dict:
        practice = db.get(Practice, m.practice_id)
        if body.confirm_name != practice.name:
            raise ProblemError(422, "confirm_name does not match the practice name",
                               "confirmation_mismatch")
        if service.held_clients(db):
            raise ProblemError(409, "clients under legal hold must be released first",
                               "legal_hold")
        req = service.create_request(db, practice_id=m.practice_id, kind="practice_delete",
                                     reason=body.reason, member_id=m.member_id)
        return _request_json(request, req)

    @router.get("/practice/privacy-settings", operation_id="getPrivacySettings")
    def get_settings(m: CurrentMember = Depends(clinical),
                     db: Session = Depends(tenant_db, scope="function")) -> dict:
        s = service.get_settings(db, m.practice_id)
        return {"retention_inactive_years": s.retention_inactive_years,
                "retention_auto_apply": s.retention_auto_apply}

    @router.put("/practice/privacy-settings", operation_id="updatePrivacySettings",
                summary="Configure retention (delete clients inactive for N years)")
    def put_settings(body: SettingsIn, request: Request, m: CurrentMember = Depends(owner),
                     db: Session = Depends(tenant_db, scope="function")) -> dict:
        if body.retention_auto_apply and body.retention_inactive_years is None:
            raise ProblemError(422, "retention_auto_apply needs retention_inactive_years",
                               "validation_error")
        s = service.get_settings(db, m.practice_id)
        s.retention_inactive_years = body.retention_inactive_years
        s.retention_auto_apply = body.retention_auto_apply
        db.flush()
        audit(db, m, "privacy.settings.updated", "privacy_settings", m.practice_id, request,
              meta=body.model_dump())
        return get_settings(m, db)

    @router.post("/practice/retention/dry-run", status_code=202, operation_id="retentionDryRun",
                 summary="Report which clients retention would erase, without erasing")
    def retention_dry_run(request: Request, m: CurrentMember = Depends(owner),
                          db: Session = Depends(tenant_db, scope="function")) -> dict:
        s = service.get_settings(db, m.practice_id)
        if s.retention_inactive_years is None:
            raise ProblemError(409, "retention is not configured", "retention_not_configured")
        req = service.create_request(db, practice_id=m.practice_id, kind="retention_dry_run",
                                     member_id=m.member_id)
        return _request_json(request, req)

    @router.post("/practice/retention/apply", status_code=202, operation_id="retentionApply",
                 summary="Erase the clients a dry run would erase (needs confirm=true)")
    def retention_apply(body: RetentionApplyIn, request: Request,
                        m: CurrentMember = Depends(owner),
                        db: Session = Depends(tenant_db, scope="function")) -> dict:
        if not body.confirm:
            raise ProblemError(422, "confirm must be true", "confirmation_required")
        s = service.get_settings(db, m.practice_id)
        if s.retention_inactive_years is None:
            raise ProblemError(409, "retention is not configured", "retention_not_configured")
        req = service.create_request(db, practice_id=m.practice_id, kind="retention_apply",
                                     member_id=m.member_id)
        return _request_json(request, req)

    return router


def install_privacy(app, storage=None) -> bool:
    """Mount the privacy routes. No-op unless the tenancy layer is installed."""
    if not hasattr(app.state, "pg_engine"):
        return False
    if not hasattr(app.state, "storage"):
        from app.storage import storage_from_env

        app.state.storage = storage or storage_from_env()
    app.include_router(build_privacy_router())
    return True
