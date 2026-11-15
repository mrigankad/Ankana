"""Lal Kitab routes. Mirrors the Fastify GET /api/v1/charts/jobs/:jobId/lal-kitab.

Exposed at both GET /v1/charts/{chart_id}/lal-kitab and (to match the rest of the
workspace surface) GET /api/v1/charts/jobs/{job_id}/lal-kitab. The chart id is the
chart job id used by the existing artifact lookup. Response keys: jobId, lalKitab
(snake_case inner keys, see ankana_lalkitab.models).
"""

import json

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from ankana_lalkitab import VARSHPHAL_MAX_AGE, lal_kitab_report
from ankana_lalkitab.i18n import localize_report
from nakshatra_i18n import normalize_lang

from .db import ChartArtifact, ChartRequest


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def build_lal_kitab_router(engine, legacy_v1: bool = True) -> APIRouter:
    router = APIRouter(deprecated=True)

    def handler(chart_id: str, origin: str | None, age: int | None, lang: str | None = None):
        with Session(engine) as session:
            job = session.get(ChartRequest, chart_id)
            stored = (
                session.exec(
                    select(ChartArtifact).where(ChartArtifact.chartRequestId == chart_id)
                ).first()
                if job is not None
                else None
            )
            if stored is None:
                return _error(
                    404, "chart_artifact_not_found", "Chart artifact was not found for this job."
                )
            artifact = json.loads(stored.artifactJson)
        if origin is not None and origin not in ("lagna_h1", "aries_h1"):
            return _error(400, "invalid_origin", "origin must be lagna_h1 or aries_h1.")
        if age is not None and not 1 <= age <= VARSHPHAL_MAX_AGE:
            return _error(
                400, "invalid_age", f"age must be an integer from 1 to {VARSHPHAL_MAX_AGE}."
            )
        report = lal_kitab_report(artifact, origin=origin, age=age)
        code = normalize_lang(lang)
        out = {"jobId": chart_id, "lalKitab": report.model_dump(by_alias=True, mode="json")}
        if code == "hi":
            out = localize_report(out, "hi")
            out["language"] = "hi"
            out["needsReviewHi"] = True
        return out

    def _age(age: str | None) -> int | None | JSONResponse:
        if age is None:
            return None
        try:
            return int(age)
        except ValueError:
            return _error(
                400, "invalid_age", f"age must be an integer from 1 to {VARSHPHAL_MAX_AGE}."
            )

    if legacy_v1:  # replaced by the tenant route in app.v1.charts when Postgres is mounted
        @router.get("/v1/charts/{chart_id}/lal-kitab")
        def lal_kitab_v1(chart_id: str, origin: str | None = None,
                         age: str | None = Query(None), lang: str | None = Query(None)):
            parsed = _age(age)
            if isinstance(parsed, JSONResponse):
                return parsed
            return handler(chart_id, origin, parsed, lang)

    @router.get("/api/v1/charts/jobs/{job_id}/lal-kitab")
    def lal_kitab_job(job_id: str, origin: str | None = None, age: str | None = Query(None),
                      lang: str | None = Query(None)):
        parsed = _age(age)
        if isinstance(parsed, JSONResponse):
            return parsed
        return handler(job_id, origin, parsed, lang)

    return router
