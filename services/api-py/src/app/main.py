"""Nakshatra FastAPI backend.

Plan D will port the full route surface (clients, jobs, persistence,
assistant). This first slice exposes health and stateless chart computation
so the Python engine is reachable end to end.
"""

import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_i18n import normalize_lang
from nakshatra_interpret import build_reading
from nakshatra_rules import evaluate_predictions_enriched, evaluate_remedies


class BirthDataInput(BaseModel):
    birthDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    birthTime: str = Field(pattern=r"^\d{2}:\d{2}$")
    timezoneName: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    placeLabel: str | None = None


def legacy_api_enabled(tenant: bool) -> bool:
    """The deprecated /api/v1 surface (SQLite, single workspace, no authentication) is for
    local development and the pre-cutover web client. On a production deployment that has the
    tenant layer it is off unless ANKANA_LEGACY_API=1 is set explicitly."""
    if not tenant or os.getenv("API_ENV", "dev") != "production":
        return True
    return os.getenv("ANKANA_LEGACY_API", "").strip().lower() in ("1", "true", "yes")


def _legacy_gate(request: Request) -> None:
    if not request.app.state.legacy_enabled:
        raise HTTPException(404, "Not Found")


def create_app(engine=None, pg_engine=None, verifier=None, ai_provider=None, storage=None,
               auth_config=None, mailer=None, oidc_http=None) -> FastAPI:
    from ankana_ai.api import build_ask_router
    from ankana_ai.providers import provider_from_env

    from .api_v1 import install_tenancy
    from .db import make_engine
    from .lal_kitab import build_lal_kitab_router
    from .locations import build_locations_router
    from .v1.common import register_problem_handlers
    from .workspace import build_router

    engine = engine or make_engine()
    app = FastAPI(title="Nakshatra API", version="0.1.0",
                  summary="Ankana practice API. /v1 is tenant-scoped (Postgres, RLS); "
                          "/api/v1 routes are deprecated legacy (SQLite, single workspace).")
    app.state.ai_provider_factory = (
        (lambda: ai_provider) if ai_provider is not None else provider_from_env)
    from .observability import setup_observability

    setup_observability(app)
    register_problem_handlers(app)
    tenant = install_tenancy(app, pg_engine=pg_engine, verifier=verifier, auth_config=auth_config,
                             mailer=mailer, oidc_http=oidc_http)
    from .reports.api import install_reports

    install_reports(app, storage=storage)
    from .billing.api import install_billing

    install_billing(app)
    from .privacy.api import install_privacy

    install_privacy(app, storage=storage)
    app.state.legacy_enabled = legacy_api_enabled(tenant)
    gate = [Depends(_legacy_gate)]
    app.include_router(build_router(engine), dependencies=gate)
    app.include_router(build_locations_router(), prefix="/v1")
    app.include_router(build_locations_router(), prefix="/api/v1", deprecated=True,
                       include_in_schema=False)
    app.include_router(build_lal_kitab_router(engine, legacy_v1=not tenant), dependencies=gate)
    ask_router = build_ask_router(engine, app.state.ai_provider_factory)
    if not tenant:  # with Postgres mounted, /v1 ask and lal-kitab are the tenant routes
        app.include_router(ask_router, prefix="/v1")
    app.include_router(ask_router, prefix="/api/v1", deprecated=True, dependencies=gate)
    _install_openapi(app)
    import os

    extra = [o.strip() for o in os.getenv("API_CORS_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[*(list(app.state.auth.cfg.allowed_origins) if tenant
                         else ["http://localhost:3000", "http://127.0.0.1:3000"]), *extra],
        # Any local dev port (web dev servers move around); never in production.
        allow_origin_regex=(None if os.getenv("API_ENV", "dev") == "production"
                            else r"^http://(localhost|127\.0\.0\.1):\d+$"),
        allow_credentials=True,  # the refresh cookie (see app.auth.routes)
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Location", "Idempotency-Key"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    def ready() -> dict:
        """Readiness probe: in production, 503 until the required env is complete
        (see app.preflight). Names only go to the log, never to the caller."""
        if os.getenv("API_ENV", "dev") != "production":
            return {"status": "ok"}
        from app import preflight

        bad = preflight.errors(preflight.check(role="api"))
        if bad:
            logging.getLogger("app.preflight").error(
                "not ready: %s", "; ".join(f"{p.var}: {p.message}" for p in bad))
            raise HTTPException(503, "misconfigured")
        return {"status": "ok"}

    @app.post("/api/v1/charts/compute", dependencies=gate)
    def compute_chart(body: BirthDataInput) -> dict:
        try:
            payload = body.model_dump()
            if payload.get("placeLabel") is None:
                payload.pop("placeLabel")
            return compute_vedic_chart_artifact(payload)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/v1/charts/reading", dependencies=gate)
    def compute_reading(body: BirthDataInput, lang: str | None = None) -> dict:
        try:
            payload = body.model_dump()
            if payload.get("placeLabel") is None:
                payload.pop("placeLabel")
            artifact = compute_vedic_chart_artifact(payload)
            code = normalize_lang(lang)
            return {"artifact": artifact, "language": code,
                    "reading": build_reading(artifact, lang=code)}
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    from .locations import PUBLIC_READ_LIMIT
    from .ratelimit import limit_dependency

    @app.get("/api/v1/panchang/today",
             dependencies=[*gate, Depends(limit_dependency(PUBLIC_READ_LIMIT))])
    def panchang_today(
        tz: str = "Asia/Kolkata", lat: float = 28.6139, lon: float = 77.209
    ) -> dict:
        from dataclasses import asdict
        from datetime import UTC, datetime
        from zoneinfo import ZoneInfo

        from nakshatra_core.ayanamsa import to_sidereal
        from nakshatra_core.ephemeris import tropical_longitude
        from nakshatra_core.panchang import compute_panchang
        from nakshatra_core.sunrise import last_sunrise_and_next_sunset

        now = datetime.now(tz=UTC)
        sunrise, _ = last_sunrise_and_next_sunset(now, lat, lon)
        weekday = (sunrise.astimezone(ZoneInfo(tz)).weekday() + 1) % 7
        panchang = compute_panchang(
            to_sidereal(tropical_longitude("sun", now), now),
            to_sidereal(tropical_longitude("moon", now), now),
            weekday,
        )
        return {"date": now.isoformat(), "timezone": tz, "panchang": asdict(panchang)}

    @app.post("/api/v1/charts/predictions", dependencies=gate)
    def compute_predictions(body: BirthDataInput, horizonYears: float = 5,
                            lang: str | None = None) -> dict:
        try:
            artifact = compute_vedic_chart_artifact(_payload(body))
            code = normalize_lang(lang)
            return {
                "language": code,
                "predictions": evaluate_predictions_enriched(
                    artifact, horizon_years=horizonYears, lang=code
                ),
            }
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/v1/charts/remedies", dependencies=gate)
    def compute_remedies(body: BirthDataInput, lang: str | None = None) -> dict:
        try:
            artifact = compute_vedic_chart_artifact(_payload(body))
            code = normalize_lang(lang)
            return {"language": code, "remedies": evaluate_remedies(artifact, code)}
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return app


def _install_openapi(app: FastAPI) -> None:
    from fastapi.openapi.utils import get_openapi

    from .v1.schemas import Problem

    def custom() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, summary=app.summary,
                             routes=app.routes)
        schema.setdefault("components", {}).setdefault("schemas", {})["Problem"] = (
            Problem.model_json_schema(ref_template="#/components/schemas/{model}"))
        schema["tags"] = [{"name": t} for t in (
            "platform", "clients", "consents", "birth-records", "charts", "lal-kitab",
            "assistant", "consultations", "remedies", "ai", "billing", "notifications",
            "public-links")]
        app.openapi_schema = schema
        return schema

    app.openapi = custom  # type: ignore[method-assign]


def _payload(body: BirthDataInput) -> dict:
    payload = body.model_dump()
    if payload.get("placeLabel") is None:
        payload.pop("placeLabel")
    return payload


app = create_app()
