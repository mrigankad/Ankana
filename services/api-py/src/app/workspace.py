"""Stateful workspace routes: clients, birth records, chart jobs, audit,
dashboard. Mirrors the Fastify module surface; exact envelope parity with the
web client is verified during the Phase 5 cutover."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_core.transits import compute_transit_snapshot
from nakshatra_i18n import normalize_lang
from nakshatra_interpret import build_reading
from nakshatra_rules import evaluate_predictions_enriched, evaluate_remedies

from .db import AuditEvent, BirthRecord, ChartArtifact, ChartRequest, Client


class ClientIn(BaseModel):
    fullName: str = Field(min_length=1)
    preferredName: str | None = None
    email: str | None = None
    phone: str | None = None
    timezone: str | None = None


class BirthRecordIn(BaseModel):
    birthDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    birthTime: str = Field(pattern=r"^\d{2}:\d{2}$")
    timezoneName: str
    placeLabel: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class GenerateIn(BaseModel):
    clientId: str
    birthRecordId: str


def build_router(engine) -> APIRouter:
    router = APIRouter(prefix="/api/v1", deprecated=True)

    def audit(session: Session, action: str, subject_type: str, subject_id: str,
              meta: dict | None = None) -> None:
        session.add(
            AuditEvent(
                action=action,
                subjectType=subject_type,
                subjectId=subject_id,
                metaJson=json.dumps(meta) if meta else None,
            )
        )

    @router.post("/clients")
    def create_client(body: ClientIn) -> dict:
        with Session(engine) as session:
            client = Client(**body.model_dump())
            session.add(client)
            audit(session, "client.created", "client", client.id)
            session.commit()
            session.refresh(client)
            return {"client": client.model_dump(mode="json")}

    @router.get("/clients")
    def list_clients() -> dict:
        with Session(engine) as session:
            clients = session.exec(
                select(Client).order_by(Client.createdAt.desc())
            ).all()
            return {"clients": [c.model_dump(mode="json") for c in clients]}

    @router.get("/clients/{client_id}")
    def get_client(client_id: str) -> dict:
        with Session(engine) as session:
            client = session.get(Client, client_id)
            if client is None:
                raise HTTPException(status_code=404, detail="client not found")
            records = session.exec(
                select(BirthRecord).where(BirthRecord.clientId == client_id)
            ).all()
            jobs = session.exec(
                select(ChartRequest).where(ChartRequest.clientId == client_id)
            ).all()
            return {
                "client": client.model_dump(mode="json"),
                "birthRecords": [r.model_dump(mode="json") for r in records],
                "chartRequests": [j.model_dump(mode="json") for j in jobs],
            }

    @router.post("/clients/{client_id}/birth-records")
    def create_birth_record(client_id: str, body: BirthRecordIn) -> dict:
        with Session(engine) as session:
            if session.get(Client, client_id) is None:
                raise HTTPException(status_code=404, detail="client not found")
            record = BirthRecord(clientId=client_id, **body.model_dump())
            session.add(record)
            audit(session, "birthRecord.created", "birthRecord", record.id)
            session.commit()
            session.refresh(record)
            return {"birthRecord": record.model_dump(mode="json")}

    @router.post("/charts/generate")
    def generate_chart(body: GenerateIn) -> dict:
        with Session(engine) as session:
            record = session.get(BirthRecord, body.birthRecordId)
            if record is None or record.clientId != body.clientId:
                raise HTTPException(status_code=404, detail="birth record not found")
            job = ChartRequest(clientId=body.clientId, birthRecordId=record.id)
            try:
                artifact = compute_vedic_chart_artifact(
                    {
                        "birthDate": record.birthDate,
                        "birthTime": record.birthTime,
                        "timezoneName": record.timezoneName,
                        "latitude": record.latitude,
                        "longitude": record.longitude,
                        "placeLabel": record.placeLabel,
                    }
                )
                job.status = "completed"
                session.add(job)
                session.add(
                    ChartArtifact(
                        chartRequestId=job.id,
                        artifactJson=json.dumps(artifact),
                        engineVersion=artifact["calculationMetadata"]["engineVersion"],
                    )
                )
            except (KeyError, ValueError) as error:
                job.status = "failed"
                job.error = str(error)
                session.add(job)
            audit(session, "chart.generated", "chartRequest", job.id,
                  {"status": job.status})
            session.commit()
            session.refresh(job)
            return {"job": job.model_dump(mode="json")}

    def _artifact_for(session: Session, job_id: str) -> dict:
        job = session.get(ChartRequest, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        stored = session.exec(
            select(ChartArtifact).where(ChartArtifact.chartRequestId == job_id)
        ).first()
        if stored is None:
            raise HTTPException(status_code=404, detail="artifact not ready")
        return json.loads(stored.artifactJson)

    @router.get("/charts/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        with Session(engine) as session:
            job = session.get(ChartRequest, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="job not found")
            return {"job": job.model_dump(mode="json")}

    @router.get("/charts/jobs/{job_id}/artifact")
    def get_artifact(job_id: str, lang: str | None = None) -> dict:
        with Session(engine) as session:
            artifact = _artifact_for(session, job_id)
            code = normalize_lang(lang)
            return {"artifact": artifact, "language": code,
                    "reading": build_reading(artifact, lang=code)}

    @router.get("/charts/jobs/{job_id}/predictions")
    def get_predictions(job_id: str, horizonYears: float = 5, lang: str | None = None) -> dict:
        with Session(engine) as session:
            artifact = _artifact_for(session, job_id)
            code = normalize_lang(lang)
            return {
                "language": code,
                "predictions": evaluate_predictions_enriched(
                    artifact, horizon_years=horizonYears, lang=code
                ),
            }

    @router.get("/charts/jobs/{job_id}/remedies")
    def get_remedies(job_id: str, lang: str | None = None) -> dict:
        with Session(engine) as session:
            artifact = _artifact_for(session, job_id)
            code = normalize_lang(lang)
            return {"language": code, "remedies": evaluate_remedies(artifact, code)}

    @router.get("/charts/jobs/{job_id}/transits")
    def get_transits(job_id: str, date: str | None = None) -> dict:
        with Session(engine) as session:
            artifact = _artifact_for(session, job_id)
            when = (
                datetime.fromisoformat(date.replace("Z", "+00:00"))
                if date
                else datetime.now(tz=UTC)
            )
            return {"transits": compute_transit_snapshot(artifact, when)}

    @router.get("/audit-events")
    def list_audit_events() -> dict:
        with Session(engine) as session:
            events = session.exec(
                select(AuditEvent).order_by(AuditEvent.createdAt.desc()).limit(100)
            ).all()
            return {"events": [e.model_dump(mode="json") for e in events]}

    @router.get("/dashboard/summary")
    def dashboard_summary() -> dict:
        with Session(engine) as session:
            return {
                "clients": len(session.exec(select(Client)).all()),
                "chartRequests": len(session.exec(select(ChartRequest)).all()),
                "auditEvents": len(session.exec(select(AuditEvent)).all()),
            }

    return router
