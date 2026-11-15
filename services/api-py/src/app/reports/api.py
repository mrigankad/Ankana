"""/v1/reports, /v1/practice/branding and the local signed-URL file route.

Mounted by install_reports(app); lives beside (not inside) api_v1.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentMember, require_roles, tenant_db
from app.billing.entitlements import require_entitlement
from app.billing.service import consume_if_new
from app.storage import LocalStorage, StorageError
from app.tenancy.models import AuditEvent, BirthRecord, ChartArtifact, Practice, Report, Role
from app.v1.common import load_client, paginate

from .branding import BrandingError, validate_color, validate_logo_url
from .html import ALL_SECTIONS, DEFAULT_SECTIONS, TEMPLATES
from .i18n import LANGUAGES
from .service import practice_branding, request_report

STAFF = (Role.owner, Role.astrologer, Role.assistant)
DOWNLOAD_TTL = 900

Section = Literal["summary", "kundali", "planets", "houses", "yogas", "dasha", "vargas",
                  "panchang", "reading", "lal_kitab", "remedies"]


class ReportIn(BaseModel):
    chart_id: uuid.UUID
    template: str = "standard"
    language: Literal["en", "hi"] = "en"
    sections: list[Section] | None = Field(
        default=None, description=f"default: {', '.join(DEFAULT_SECTIONS)}")
    lal_kitab: bool | None = Field(default=None, description="toggle the Lal Kitab section")
    remedies: bool | None = Field(default=None, description="toggle the remedies section")


class BrandingIn(BaseModel):
    logo_url: str | None = None
    brand_primary_color: str | None = None
    brand_accent_color: str | None = None
    brand_footer: str | None = Field(default=None, max_length=200)


class ReportItem(BaseModel):
    id: uuid.UUID
    chart_id: uuid.UUID
    status: str
    template: str
    template_version: str
    language: str
    sections: list[str] | None
    error: str | None
    created_at: datetime
    size_bytes: int | None
    checksum_sha256: str | None
    download_url: str | None
    download_expires_in: int | None


class ClientReportPage(BaseModel):
    reports: list[ReportItem]
    next_cursor: str | None = None


def _sections(body: ReportIn) -> list[str]:
    chosen = list(body.sections) if body.sections is not None else list(DEFAULT_SECTIONS)
    for key, flag in (("lal_kitab", body.lal_kitab), ("remedies", body.remedies)):
        if flag is True and key not in chosen:
            chosen.append(key)
        if flag is False and key in chosen:
            chosen.remove(key)
    if not chosen:
        raise HTTPException(422, "at least one section is required")
    return [s for s in ALL_SECTIONS if s in chosen]  # canonical order, deduplicated


def _report_json(request: Request, r: Report) -> dict:
    out = {
        "id": str(r.id), "chart_id": str(r.chart_artifact_id), "status": r.status,
        "template": r.template, "template_version": r.template_version,
        "language": r.language, "sections": (r.options or {}).get("sections"),
        "error": r.error, "created_at": r.created_at.isoformat(),
        "size_bytes": r.size_bytes, "checksum_sha256": r.checksum_sha256,
        "download_url": None, "download_expires_in": None,
    }
    if r.status == "done" and r.storage_key:
        out["download_url"] = request.app.state.storage.signed_url(
            r.storage_key, DOWNLOAD_TTL, filename=f"report-{r.id}.pdf")
        out["download_expires_in"] = DOWNLOAD_TTL
    return out


def build_reports_router() -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.post("/reports", status_code=202, tags=["reports"], operation_id="createReport",
                 dependencies=[Depends(require_entitlement("reports"))])
    def create_report(body: ReportIn, request: Request, response: Response,
                      m: CurrentMember = Depends(require_roles(*STAFF)),
                      db: Session = Depends(tenant_db, scope="function")) -> dict:
        if body.template not in TEMPLATES:
            raise HTTPException(422, f"template must be one of {sorted(TEMPLATES)}")
        if body.language not in LANGUAGES:
            raise HTTPException(422, "language must be en or hi")
        report = request_report(
            db, practice_id=m.practice_id, member_id=m.member_id, chart_id=body.chart_id,
            template=body.template, language=body.language, sections=_sections(body))
        if report is None:
            raise HTTPException(404, "chart not found")
        consume_if_new(db, m.practice_id, "reports", report.created_at)
        db.add(AuditEvent(practice_id=m.practice_id, actor_user_id=m.user_id,
                          actor_member_id=m.member_id, action="report.requested",
                          entity_type="report", entity_id=str(report.id),
                          ip=request.client.host if request.client else None))
        db.flush()
        response.headers["Location"] = f"/v1/reports/{report.id}"
        return _report_json(request, report)

    @router.get("/reports/{report_id}", tags=["reports"], operation_id="getReport")
    def get_report(report_id: uuid.UUID, request: Request,
                   m: CurrentMember = Depends(require_roles(*STAFF)),
                   db: Session = Depends(tenant_db, scope="function")) -> dict:
        report = db.scalar(select(Report).where(Report.id == report_id,
                                                Report.deleted_at.is_(None)))
        if report is None:
            raise HTTPException(404, "report not found")
        return _report_json(request, report)

    @router.get("/clients/{client_id}/reports", response_model=ClientReportPage,
                tags=["reports"], operation_id="listClientReports",
                summary="Reports generated for a client (newest first), with fresh download links")
    def list_client_reports(client_id: uuid.UUID, request: Request,
                            limit: int = Query(default=50, ge=1, le=200),
                            cursor: str | None = None,
                            m: CurrentMember = Depends(require_roles(*STAFF)),
                            db: Session = Depends(tenant_db, scope="function")) -> dict:
        client = load_client(db, m, client_id)
        stmt = select(Report).where(
            Report.deleted_at.is_(None),
            Report.chart_artifact_id.in_(
                select(ChartArtifact.id).join(
                    BirthRecord, (BirthRecord.id == ChartArtifact.birth_record_id)
                    & (BirthRecord.practice_id == ChartArtifact.practice_id))
                .where(BirthRecord.client_id == client.id)))
        rows, nxt = paginate(db, stmt, Report, limit, cursor)
        return {"reports": [_report_json(request, r) for r in rows], "next_cursor": nxt}

    @router.get("/practice/branding", tags=["practice"], operation_id="getPracticeBranding")
    def get_branding(m: CurrentMember = Depends(require_roles(*STAFF)),
                     db: Session = Depends(tenant_db, scope="function")) -> dict:
        b = practice_branding(db.get(Practice, m.practice_id))
        return {"name": b.name, "logo_url": b.logo_url, "brand_primary_color": b.primary,
                "brand_accent_color": b.accent, "brand_footer": b.footer}

    @router.put("/practice/branding", tags=["practice"], operation_id="updatePracticeBranding")
    def put_branding(body: BrandingIn, m: CurrentMember = Depends(require_roles(Role.owner)),
                     db: Session = Depends(tenant_db, scope="function")) -> dict:
        try:
            practice = db.get(Practice, m.practice_id)
            practice.logo_url = validate_logo_url(body.logo_url)
            practice.brand_primary_color = validate_color(body.brand_primary_color)
            practice.brand_accent_color = validate_color(body.brand_accent_color)
            practice.brand_footer = body.brand_footer
        except BrandingError as exc:
            raise HTTPException(422, str(exc)) from exc
        db.flush()
        return get_branding(m, db)

    @router.get("/storage/{key:path}", tags=["storage"], operation_id="downloadStoredFile")
    def local_file(key: str, request: Request, exp: int, sig: str,
                   filename: str | None = None):
        """Serves LocalStorage objects for HMAC-signed, expiring URLs only."""
        storage = request.app.state.storage
        if not isinstance(storage, LocalStorage):
            raise HTTPException(404, "not found")
        if not storage.verify(key, exp, sig):
            raise HTTPException(403, "invalid or expired link")
        try:
            path = storage._path(key)
        except StorageError:
            raise HTTPException(404, "not found") from None
        if not path.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(path, media_type="application/pdf",
                            filename=filename or path.name)

    return router


def install_reports(app, storage=None) -> bool:
    """Mount the report routes. No-op unless the tenancy layer is installed."""
    if not hasattr(app.state, "pg_engine"):
        return False
    from app.storage import storage_from_env

    app.state.storage = storage or storage_from_env()
    app.include_router(build_reports_router())
    return True
