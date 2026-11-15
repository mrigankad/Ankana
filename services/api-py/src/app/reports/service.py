"""Report request + render job logic (no HTTP here)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import metrics
from app.jobs import Job, enqueue
from app.storage import Storage
from app.tenancy.models import BirthRecord, ChartArtifact, Client, Practice, Report
from app.tenancy.session import tenant_session

from .branding import Branding, BrandingError, logo_data_uri
from .html import TEMPLATE_VERSION, build_context, render_html

log = logging.getLogger(__name__)

RENDER_REPORT = "render_report"


def practice_branding(practice: Practice) -> Branding:
    from .branding import DEFAULT_ACCENT, DEFAULT_PRIMARY

    return Branding(practice.name, practice.logo_url,
                    practice.brand_primary_color or DEFAULT_PRIMARY,
                    practice.brand_accent_color or DEFAULT_ACCENT, practice.brand_footer)


def options_hash(template: str, language: str, sections: list[str], branding: Branding) -> str:
    blob = json.dumps({"t": template, "l": language, "s": sorted(sections),
                       "b": branding.snapshot()}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def storage_key(practice_id, artifact_id, options_hash_: str) -> str:
    return f"{practice_id}/reports/{artifact_id}/v{TEMPLATE_VERSION}-{options_hash_[:16]}.pdf"


def request_report(db: Session, *, practice_id: uuid.UUID, member_id: uuid.UUID,
                   chart_id: uuid.UUID, template: str, language: str,
                   sections: list[str]) -> Report | None:
    """Create (or reuse) a report row and enqueue its render job, in the
    caller's tenant transaction. Returns None when the chart is not visible."""
    artifact = db.scalar(select(ChartArtifact).where(ChartArtifact.id == chart_id))
    if artifact is None:
        return None
    practice = db.scalar(select(Practice).where(Practice.id == practice_id))
    branding = practice_branding(practice)
    ohash = options_hash(template, language, sections, branding)

    def existing() -> Report | None:
        return db.scalar(select(Report).where(
            Report.chart_artifact_id == chart_id, Report.template_version == TEMPLATE_VERSION,
            Report.options_hash == ohash, Report.deleted_at.is_(None)))

    report = existing()
    if report is None:
        report = Report(
            practice_id=practice_id, chart_artifact_id=chart_id, template=template,
            template_version=TEMPLATE_VERSION, language=language, status="queued",
            options={"sections": sections, "branding": branding.snapshot()},
            options_hash=ohash, generated_by_member_id=member_id)
        try:
            with db.begin_nested():
                db.add(report)
                db.flush()
        except IntegrityError:  # concurrent identical request won
            report = existing()
            if report is None:
                raise
            return report
    elif report.status != "failed":
        return report  # idempotent: queued, rendering or done
    else:
        # Retrying a failed report: lock the row so two concurrent retries enqueue one job.
        db.refresh(report, with_for_update=True)
        if report.status != "failed":
            return report
    report.status = "queued"
    report.error = None
    report.job_id = enqueue(db, RENDER_REPORT, {"report_id": str(report.id)},
                            practice_id=practice_id)
    db.flush()
    return report


def _load_inputs(engine: Engine, practice_id: uuid.UUID, report_id: uuid.UUID) -> dict | None:
    with tenant_session(engine, practice_id) as db:
        report = db.get(Report, report_id)
        if report is None or report.deleted_at is not None:
            return None
        if report.status == "done":
            return {"done": True}
        report.status = "rendering"
        artifact = db.get(ChartArtifact, report.chart_artifact_id)
        birth = db.get(BirthRecord, artifact.birth_record_id)
        client = db.get(Client, birth.client_id)
        return {
            "done": False, "artifact": artifact.payload, "client_name": client.display_name,
            "language": report.language, "template": report.template,
            "options": report.options, "key": storage_key(
                practice_id, report.chart_artifact_id, report.options_hash),
            "created_at": report.created_at,
        }


def build_html(inputs: dict, now: datetime | None = None) -> str:
    """Compose the report HTML from loaded inputs (pure; used by tests)."""
    from nakshatra_interpret import build_reading
    from nakshatra_rules import evaluate_remedies

    options = inputs["options"]
    sections = options["sections"]
    branding = Branding.from_snapshot(options["branding"])
    artifact = inputs["artifact"]
    now = now or inputs["created_at"]
    try:
        logo = logo_data_uri(branding.logo_url)
    except BrandingError as exc:
        log.warning("report logo skipped: %s", exc)
        logo = None
    reading = build_reading(artifact, now, lang=inputs["language"]) if {"reading", "vargas"} & set(sections) else None
    remedies = evaluate_remedies(artifact, inputs["language"]) if "remedies" in sections else None
    lal = None
    if "lal_kitab" in sections:
        from ankana_lalkitab.report import lal_kitab_report

        lal = lal_kitab_report(artifact, now=now).model_dump(by_alias=True, mode="json")
        from ankana_lalkitab.i18n import localize_report

        lal = localize_report(lal, inputs["language"])
    ctx = build_context(
        artifact=artifact, client_name=inputs["client_name"], branding=branding,
        language=inputs["language"], sections=sections, generated_at=now,
        logo_data_uri=logo, reading=reading, remedies=remedies, lal_kitab=lal)
    return render_html(inputs["template"], ctx)


def render_report_job(job: Job, engine: Engine, storage: Storage, html_to_pdf=None) -> dict:
    """Worker handler. Idempotent: a finished report is not re-rendered."""
    from .i18n import LABELS
    from .pdf import html_to_pdf as default_pdf

    html_to_pdf = html_to_pdf or default_pdf
    report_id = uuid.UUID(job.payload["report_id"])
    inputs = _load_inputs(engine, job.practice_id, report_id)
    if inputs is None:
        return {"skipped": "report missing"}
    if inputs["done"]:
        return {"skipped": "already done"}

    html = build_html(inputs)
    branding = Branding.from_snapshot(inputs["options"]["branding"])
    t0 = time.perf_counter()
    try:
        pdf = html_to_pdf(html, branding, LABELS[inputs["language"]]["title"])
    except Exception:
        metrics.report_render_duration.record(time.perf_counter() - t0, {"outcome": "error"})
        raise
    metrics.report_render_duration.record(time.perf_counter() - t0, {"outcome": "ok"})
    storage.put(inputs["key"], pdf, "application/pdf")
    checksum = hashlib.sha256(pdf).hexdigest()
    with tenant_session(engine, job.practice_id) as db:
        report = db.get(Report, report_id)
        report.status = "done"
        report.storage_key = inputs["key"]
        report.checksum_sha256 = checksum
        report.size_bytes = len(pdf)
        report.error = None
        period = datetime.now(UTC).date().replace(day=1)
        db.execute(text(
            "INSERT INTO usage_counter (id, practice_id, metric, period, value) "
            "VALUES (gen_random_uuid(), :p, 'reports', :d, 1) "
            "ON CONFLICT (practice_id, metric, period) "
            "DO UPDATE SET value = usage_counter.value + 1, updated_at = now()"),
            {"p": job.practice_id, "d": period})
    return {"bytes": len(pdf), "sha256": checksum}


def render_report_failed(job: Job, engine: Engine, error: str, final: bool) -> None:
    """Keep the report row in step with the job: retrying -> queued, exhausted -> failed."""
    try:
        report_id = uuid.UUID(job.payload["report_id"])
        with tenant_session(engine, job.practice_id) as db:
            report = db.get(Report, report_id)
            if report is not None and report.status != "done":
                report.status = "failed" if final else "queued"
                report.error = error[:500]
    except Exception:  # never mask the original failure
        log.exception("could not record report failure")
