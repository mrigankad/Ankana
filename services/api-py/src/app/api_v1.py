"""Tenant-aware v1 routes (Postgres, JWT auth, RLS).

Legacy /api/v1 routes in workspace.py keep running on SQLite with the single
"ws_default" workspace until the web client is cut over; they are untouched.
These routes live under /v1 and never see another practice's rows: the DB
session is bound to the caller's practice (see app.auth.deps.tenant_db).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentMember, StubIssuer
from app.auth.deps import current_user_id, memberships
from app.billing.config import billing_enabled
from app.messaging.api import router as webhooks_router
from app.notify.api import router as notify_router
from app.notify.public import router as public_router
from app.tenancy.models import Member, Practice, Role
from app.tenancy.session import bind_practice
from app.v1.ai import router as ai_router
from app.v1.charts import router as charts_router
from app.v1.clients import router as clients_router
from app.v1.common import PROBLEM_RESPONSES, audit, register_problem_handlers
from app.v1.consult import router as consult_router
from app.v1.depth import router as depth_router
from app.v1.portal import router as portal_router
from app.v1.practice import router as practice_router
from app.v1.preview import router as preview_router
from app.v1.sensitivity import router as sensitivity_router
from app.v1.today import router as today_router


class PracticeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    gstin: str | None = Field(default=None, max_length=15)
    state: str | None = None


def build_v1_router() -> APIRouter:
    router = APIRouter(prefix="/v1", responses=PROBLEM_RESPONSES)  # type: ignore[arg-type]

    @router.post("/dev/token", tags=["platform"], operation_id="devToken", include_in_schema=False)
    def dev_token(request: Request, body: dict) -> dict:
        """Mint a token from the stub issuer. 404 unless the stub is active."""
        verifier = getattr(request.app.state.verifier, "external", request.app.state.verifier)
        if not isinstance(verifier, StubIssuer):
            raise HTTPException(404, "not found")
        subject = str(body.get("subject") or "")
        if not subject:
            raise HTTPException(422, "subject required")
        return {"access_token": verifier.issue(subject, body.get("email"), body.get("name"))}

    @router.get("/meta", tags=["platform"], operation_id="getMeta",
                summary="Public build info and source link (AGPL-3.0 section 13)")
    def meta() -> dict:
        import os

        from nakshatra_core.chart import ENGINE_VERSION
        from nakshatra_core.providers import get_provider

        return {
            "version": ENGINE_VERSION, "git_sha": os.getenv("ANKANA_GIT_SHA"),
            "source_url": os.getenv("ANKANA_SOURCE_URL", "https://github.com/mrigankad/Ankana"),
            "license": "AGPL-3.0-only", "ephemeris": get_provider().name,
            "billing": billing_enabled(),
        }

    @router.get("/me", tags=["platform"], operation_id="getMe", summary="Current user and memberships")
    def me(request: Request, user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        rows = memberships(request.app.state.pg_engine, user_id)
        return {"user_id": str(user_id), "memberships": [
            {"member_id": str(r["member_id"]), "practice_id": str(r["practice_id"]),
             "practice_name": r["practice_name"], "role": r["role"]} for r in rows]}

    @router.post("/practices", status_code=201, tags=["platform"], operation_id="createPractice",
                 summary="Bootstrap a practice; the caller becomes owner")
    def create_practice(body: PracticeIn, request: Request,
                        user_id: uuid.UUID = Depends(current_user_id)) -> dict:
        """Bootstrap: the caller becomes owner of a new practice. The id is
        generated here and bound before the insert so the RLS WITH CHECK passes."""
        if not request.app.state.auth.cfg.signup_enabled:
            raise HTTPException(403, "Creating practices is closed on this server.")
        practice_id = uuid.uuid4()
        with Session(request.app.state.pg_engine, expire_on_commit=False) as db:
            with db.begin():
                bind_practice(db, practice_id)
                db.add(Practice(id=practice_id, **body.model_dump()))
                db.flush()
                member = Member(practice_id=practice_id, user_id=user_id, role=Role.owner)
                db.add(member)
                db.flush()
                audit(db, CurrentMember(user_id, member.id, practice_id, Role.owner),
                      "practice.created", "practice", practice_id, request)
        return {"practice_id": str(practice_id), "member_id": str(member.id), "role": "owner"}

    for sub in (clients_router, charts_router, depth_router, sensitivity_router,
                practice_router, ai_router, notify_router, public_router, preview_router, portal_router,
                today_router, consult_router):
        router.include_router(sub)
    return router


def install_tenancy(app, pg_engine=None, verifier=None, auth_config=None, mailer=None,
                    sms=None, oidc_http=None) -> bool:
    """Mount /v1 when a Postgres engine is supplied or API_DATABASE_URL is set.
    Returns False (and mounts nothing) otherwise, so the legacy SQLite app
    and its tests keep working without Postgres."""
    from app.auth import build_verifier
    from app.settings import Settings
    from app.tenancy.session import make_pg_engine

    settings = Settings.from_env()
    if pg_engine is None:
        if not settings.database_url:
            return False
        pg_engine = make_pg_engine(settings.database_url)
    from app.auth.config import AuthConfig
    from app.auth.keys import Issuer
    from app.auth.mailer import build_mailer, build_sms
    from app.auth.oidc import OidcClient
    from app.auth.routes import build_auth_router, build_team_router, build_wellknown_router
    from app.auth.service import AuthService

    cfg = auth_config or AuthConfig.from_env()
    issuer = Issuer.from_config(cfg)
    app.state.pg_engine = pg_engine
    from app import metrics

    metrics.bind_engine(pg_engine)
    app.state.auth = AuthService(pg_engine, cfg, issuer, mailer or build_mailer(cfg),
                                 sms or build_sms(cfg))
    app.state.oidc = OidcClient(app.state.auth, oidc_http)
    if verifier is not None:  # injected verifier acts as the external issuer
        from app.auth.verifier import CompositeVerifier

        verifier = CompositeVerifier(issuer, issuer.issuer, verifier)
    app.state.verifier = verifier or build_verifier(settings, issuer)
    register_problem_handlers(app)
    app.include_router(build_wellknown_router())
    app.include_router(build_auth_router())
    app.include_router(build_team_router())
    app.include_router(build_v1_router())
    app.include_router(webhooks_router, prefix="/v1")
    return True
