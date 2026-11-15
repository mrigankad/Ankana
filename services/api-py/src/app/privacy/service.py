"""Data principal rights and retention, without HTTP.

All functions take a Session already bound to the practice (tenant_session /
tenant_db) and run inside its transaction.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import inspect, or_, select, text
from sqlalchemy.orm import Session

from app.jobs import enqueue
from app.storage import Storage, StorageError
from app.tenancy.models import (
    AuditEvent,
    BirthRecord,
    ChartArtifact,
    Client,
    ClientLifeEvent,
    ClientTag,
    Consent,
    Consultation,
    ConsultationNote,
    ConsultationSummary,
    ConsultPrediction,
    Member,
    Practice,
    PracticeInvite,
    RemedyCheckin,
    RemedyItem,
    RemedyPlan,
    Report,
    UsageCounter,
    UserAccount,
)

from . import crypto, erasure_log, orm
from .keys import PrivacyError
from .models import ConsentReceipt, CorrectionLog, PrivacyRequest, PrivacySettings
from .pdf import text_pdf

JOB_KIND = "privacy_request"
EXPORT_TTL_DAYS = 7
CLIENT_FIELDS = ("display_name", "contact_email", "contact_phone", "timezone",
                 "preferred_language")
BIRTH_FIELDS = ("birth_date", "birth_time", "time_source", "place_label", "latitude",
                "longitude", "timezone_name")
ERASED_NAME = "Erased client"


class LegalHoldError(PrivacyError):
    pass


class AlreadyErasedError(PrivacyError):
    pass


# ================================================================ helpers
def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="microseconds")


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str).encode()


def row_dict(obj: Any, exclude: tuple[str, ...] = ()) -> dict:
    out = {}
    for col in inspect(type(obj)).mapper.column_attrs:
        if col.key in exclude or col.key.endswith("_bidx"):
            continue
        out[col.key] = getattr(obj, col.key)
    return out


def _json(obj: Any) -> bytes:
    return json.dumps(obj, indent=2, sort_keys=True, default=str, ensure_ascii=False).encode()


def _audit(db: Session, practice_id, action: str, entity: str, entity_id, *,
           member_id=None, meta: dict | None = None) -> None:
    db.add(AuditEvent(practice_id=practice_id, actor_member_id=member_id, action=action,
                      entity_type=entity, entity_id=str(entity_id), meta=meta))


# ============================================================ consent receipts
def _receipt_body(r: ConsentReceipt) -> dict:
    return {
        "v": r.schema_version, "receipt_id": str(r.id), "practice_id": str(r.practice_id),
        "client_id": str(r.client_id), "consent_id": str(r.consent_id), "event": r.event,
        "purpose": r.purpose, "notice_version": r.notice_version,
        "notice_language": r.notice_language, "notice_text_sha256": r.notice_text_sha256,
        "channel": r.channel,
        "collected_by_member_id": str(r.collected_by_member_id) if r.collected_by_member_id else None,
        "occurred_at": _iso(r.occurred_at),
    }


def issue_receipt(db: Session, consent: Consent, event: str,
                  member_id: uuid.UUID | None = None) -> ConsentReceipt:
    """Write the immutable receipt for a consent grant or withdrawal."""
    orm.prepare(db, create=True)
    occurred = consent.granted_at if event == "granted" else consent.withdrawn_at
    receipt = ConsentReceipt(
        id=uuid.uuid4(), practice_id=consent.practice_id, client_id=consent.client_id,
        consent_id=consent.id, event=event, purpose=consent.purpose.value,
        notice_version=consent.notice_version, notice_language=consent.notice_language,
        notice_text_sha256=consent.notice_text_sha256 or (
            hashlib.sha256(consent.notice_text.encode()).hexdigest()
            if consent.notice_text else None),
        channel=consent.channel,
        collected_by_member_id=member_id or consent.collected_by_member_id,
        occurred_at=occurred, schema_version=1, receipt_hash="", signature="")
    body = _canonical(_receipt_body(receipt))
    receipt.receipt_hash = hashlib.sha256(body).hexdigest()
    receipt.signature = crypto.sign(consent.practice_id, "consent_receipt", body)
    db.add(receipt)
    db.flush()
    return receipt


def verify_receipt(db: Session, receipt: ConsentReceipt) -> bool:
    orm.prepare(db, create=False)
    body = _canonical(_receipt_body(receipt))
    return (hashlib.sha256(body).hexdigest() == receipt.receipt_hash
            and crypto.sign(receipt.practice_id, "consent_receipt", body) == receipt.signature)


def receipt_json(db: Session, r: ConsentReceipt) -> dict:
    consent = db.get(Consent, r.consent_id)
    text_ = consent.notice_text if consent else None
    return {
        **_receipt_body(r), "id": str(r.id), "receipt_hash": r.receipt_hash,
        "signature": r.signature, "verified": verify_receipt(db, r),
        "notice_text": text_,
        "notice_text_matches_hash": (
            hashlib.sha256(text_.encode()).hexdigest() == r.notice_text_sha256
            if text_ and r.notice_text_sha256 else None),
    }


# ================================================================ corrections
def log_corrections(db: Session, *, practice_id, client_id, entity_type: str, entity_id,
                    changes: dict[str, tuple[Any, Any]], member_id=None,
                    reason: str | None = None) -> int:
    n = 0
    for field, (old, new) in changes.items():
        if old == new:
            continue
        db.add(CorrectionLog(
            practice_id=practice_id, client_id=client_id, entity_type=entity_type,
            entity_id=str(entity_id), field=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
            reason=(reason or None) and reason[:500], changed_by_member_id=member_id))
        n += 1
    return n


# ================================================================ requests
def create_request(db: Session, *, practice_id, kind: str, client_id=None, reason=None,
                   member_id=None, payload: dict | None = None) -> PrivacyRequest:
    req = PrivacyRequest(practice_id=practice_id, client_id=client_id, kind=kind,
                         reason=reason, requested_by_member_id=member_id,
                         result=payload or None)
    db.add(req)
    db.flush()
    req.job_id = enqueue(db, JOB_KIND, {"request_id": str(req.id)}, practice_id=practice_id)
    _audit(db, practice_id, f"privacy.{kind}.requested", "privacy_request", req.id,
           member_id=member_id, meta={"client_id": str(client_id) if client_id else None})
    return req


def get_client_any(db: Session, client_id) -> Client | None:
    """Client row including soft-deleted ones (rights apply to them too)."""
    return db.scalar(select(Client).where(Client.id == client_id))


# ================================================================ export
def _client_data(db: Session, practice_id, client: Client) -> dict[str, Any]:
    cid = client.id
    births = list(db.scalars(select(BirthRecord).where(BirthRecord.client_id == cid)
                             .order_by(BirthRecord.version)))
    charts = list(db.scalars(select(ChartArtifact).where(
        ChartArtifact.birth_record_id.in_([b.id for b in births] or [uuid.uuid4()]))
        .order_by(ChartArtifact.created_at)))
    consents = list(db.scalars(select(Consent).where(Consent.client_id == cid)
                               .order_by(Consent.granted_at)))
    receipts = list(db.scalars(select(ConsentReceipt).where(ConsentReceipt.client_id == cid)
                               .order_by(ConsentReceipt.occurred_at)))
    consultations = list(db.scalars(select(Consultation).where(Consultation.client_id == cid)
                                    .order_by(Consultation.consulted_at)))
    notes = list(db.scalars(select(ConsultationNote).where(
        ConsultationNote.consultation_id.in_([c.id for c in consultations] or [uuid.uuid4()]))
        .order_by(ConsultationNote.created_at)))
    plans = list(db.scalars(select(RemedyPlan).where(RemedyPlan.client_id == cid)
                            .order_by(RemedyPlan.created_at)))
    items = list(db.scalars(select(RemedyItem).where(
        RemedyItem.plan_id.in_([p.id for p in plans] or [uuid.uuid4()]))
        .order_by(RemedyItem.sort_order)))
    checkins = list(db.scalars(select(RemedyCheckin).where(
        RemedyCheckin.item_id.in_([i.id for i in items] or [uuid.uuid4()]))
        .order_by(RemedyCheckin.checkin_date)))
    reports = list(db.scalars(select(Report).where(
        Report.chart_artifact_id.in_([c.id for c in charts] or [uuid.uuid4()]))
        .order_by(Report.created_at)))
    summaries = list(db.scalars(select(ConsultationSummary).where(
        ConsultationSummary.consultation_id.in_([c.id for c in consultations] or [uuid.uuid4()]))))
    predictions = list(db.scalars(select(ConsultPrediction).where(
        ConsultPrediction.client_id == cid).order_by(ConsultPrediction.created_at)))
    life_events = list(db.scalars(select(ClientLifeEvent).where(
        ClientLifeEvent.client_id == cid).order_by(ClientLifeEvent.event_date)))
    tags = [t.tag for t in db.scalars(select(ClientTag).where(ClientTag.client_id == cid)
                                      .order_by(ClientTag.tag))]
    corrections = list(db.scalars(select(CorrectionLog).where(CorrectionLog.client_id == cid)
                                  .order_by(CorrectionLog.created_at)))
    cid_s = str(cid)
    audits = list(db.scalars(select(AuditEvent).where(or_(
        AuditEvent.entity_id == cid_s, AuditEvent.meta["client_id"].astext == cid_s))
        .order_by(AuditEvent.created_at)))
    invites = list(db.scalars(select(PracticeInvite).where(PracticeInvite.client_id == cid)))
    requests = list(db.scalars(select(PrivacyRequest).where(PrivacyRequest.client_id == cid)
                               .order_by(PrivacyRequest.created_at)))
    return {
        "client": client, "births": births, "charts": charts, "consents": consents,
        "receipts": receipts, "consultations": consultations, "notes": notes, "plans": plans,
        "items": items, "checkins": checkins, "reports": reports,
        "summaries": summaries, "predictions": predictions, "life_events": life_events, "tags": tags, "corrections": corrections,
        "audits": audits, "requests": requests, "invites": invites,
    }


def _summary_lines(d: dict[str, Any], practice_name: str) -> list[str]:
    c: Client = d["client"]
    lines = [
        f"Practice: {practice_name}", f"Generated: {_iso(datetime.now(UTC))}",
        "This summary lists the personal data held about the person below. The JSON files "
        "in this archive contain the complete records.", "",
        "## Contact details", f"Name: {c.display_name}", f"Email: {c.contact_email or '-'}",
        f"Phone: {c.contact_phone or '-'}", f"Time zone: {c.timezone or '-'}",
        f"Preferred language: {c.preferred_language or '-'}",
        f"Record created: {_iso(c.created_at)}", "",
        f"## Birth records ({len(d['births'])})"]
    for b in d["births"]:
        lines.append(f"v{b.version}: {b.birth_date} {b.birth_time or 'time unknown'} "
                     f"({b.time_source.value}), {b.place_label} [{b.latitude}, {b.longitude}], "
                     f"{b.timezone_name}")
    lines += ["", f"## Charts ({len(d['charts'])})"]
    lines.append(f"{len(d['charts'])} computed chart artifacts (full payloads in "
                 "data/chart_artifacts.json).")
    lines += ["", f"## Consents ({len(d['consents'])})"]
    for k in d["consents"]:
        state = f"withdrawn {_iso(k.withdrawn_at)}" if k.withdrawn_at else "active"
        lines.append(f"{k.purpose.value}: granted {_iso(k.granted_at)}, notice "
                     f"{k.notice_version}, {state}")
    lines += ["", f"## Consent receipts ({len(d['receipts'])})"]
    for r in d["receipts"]:
        lines.append(f"{r.event} {r.purpose} at {_iso(r.occurred_at)} "
                     f"(receipt {r.id}, sha256 {r.receipt_hash[:16]}...)")
    lines += ["", f"## Consultations ({len(d['consultations'])})"]
    notes_by = {}
    for n in d["notes"]:
        notes_by.setdefault(n.consultation_id, []).append(n)
    for k in d["consultations"]:
        lines.append(f"{_iso(k.consulted_at)} mode={k.mode or '-'} topic={k.topic or '-'}")
        for n in notes_by.get(k.id, []):
            lines.append(f"  Note: {n.body}")
    lines += ["", f"## Remedy plans ({len(d['plans'])})"]
    for p in d["plans"]:
        lines.append(f"{p.title} ({p.status.value}, {p.cycle_days} days, start "
                     f"{p.start_date or '-'})")
    lines += ["", f"## Reports ({len(d['reports'])})",
              f"{len(d['reports'])} generated PDF reports (included under files/reports "
              "when still stored).", "",
              f"## Corrections ({len(d['corrections'])})"]
    for k in d["corrections"]:
        lines.append(f"{_iso(k.created_at)} {k.entity_type}.{k.field}: "
                     f"{k.old_value or '-'} -> {k.new_value or '-'}")
    lines += ["", f"## Activity log entries ({len(d['audits'])})"]
    return lines


def client_bundle(db: Session, practice_id, client: Client, storage: Storage,
                  practice_name: str = "") -> dict[str, bytes]:
    """Every file for one client, as {path: bytes}."""
    orm.prepare(db, create=False)
    d = _client_data(db, practice_id, client)
    notes_by: dict[uuid.UUID, list] = {}
    for n in d["notes"]:
        notes_by.setdefault(n.consultation_id, []).append(row_dict(n))
    items_by: dict[uuid.UUID, list] = {}
    checks_by: dict[uuid.UUID, list] = {}
    for k in d["checkins"]:
        checks_by.setdefault(k.item_id, []).append(row_dict(k))
    for i in d["items"]:
        items_by.setdefault(i.plan_id, []).append({**row_dict(i),
                                                   "checkins": checks_by.get(i.id, [])})
    files: dict[str, bytes] = {
        "data/client.json": _json(row_dict(client)),
        "data/birth_records.json": _json([row_dict(b) for b in d["births"]]),
        "data/chart_artifacts.json": _json([row_dict(c) for c in d["charts"]]),
        "data/consents.json": _json([row_dict(c) for c in d["consents"]]),
        "data/consent_receipts.json": _json([receipt_json(db, r) for r in d["receipts"]]),
        "data/consultations.json": _json([{**row_dict(c), "notes": notes_by.get(c.id, [])}
                                          for c in d["consultations"]]),
        "data/remedy_plans.json": _json([{**row_dict(p), "items": items_by.get(p.id, [])}
                                         for p in d["plans"]]),
        "data/reports.json": _json([row_dict(r) for r in d["reports"]]),
        "data/consultation_summaries.json": _json([row_dict(x) for x in d["summaries"]]),
        "data/predictions.json": _json([row_dict(x) for x in d["predictions"]]),
        "data/life_events.json": _json([row_dict(x) for x in d["life_events"]]),
        "data/tags.json": _json(d["tags"]),
        "data/correction_log.json": _json([row_dict(c) for c in d["corrections"]]),
        "data/activity_log.json": _json([row_dict(a) for a in d["audits"]]),
        "data/privacy_requests.json": _json([row_dict(r) for r in d["requests"]]),
        "data/portal_invites.json": _json([row_dict(i, exclude=("token_hash",))
                                           for i in d["invites"]]),
    }
    for r in d["reports"]:
        if r.storage_key:
            try:
                files[f"files/reports/{r.id}.pdf"] = storage.get(r.storage_key)
            except StorageError:
                pass  # object already gone; the metadata row is still exported
    files["summary.pdf"] = text_pdf(f"Personal data held about {client.display_name}",
                                    _summary_lines(d, practice_name))
    return files


def build_zip(practice_id, files: dict[str, bytes], *, kind: str, subject_id: str | None) -> bytes:
    """ZIP with a manifest (sha256 per file) signed with the practice key."""
    manifest = {
        "format": "ankana-privacy-export/1", "kind": kind, "practice_id": str(practice_id),
        "subject_id": subject_id, "generated_at": _iso(datetime.now(UTC)),
        "files": [{"path": p, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                  for p, b in sorted(files.items())],
    }
    manifest["signature"] = crypto.sign(practice_id, "export_manifest", _canonical(manifest))
    manifest["signature_algorithm"] = "HMAC-SHA256 under the practice signing key"
    readme = ("Ankana personal data export\n\nmanifest.json lists every file with its SHA-256 "
              "and an HMAC signature. data/*.json holds the full records; summary.pdf is a "
              "readable overview.\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme)
        z.writestr("manifest.json", _json(manifest))
        for path, data in sorted(files.items()):
            z.writestr(path, data)
    return buf.getvalue()


def verify_zip(practice_id, data: bytes) -> bool:
    """Check file hashes and the manifest signature of an export ZIP."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        manifest = json.loads(z.read("manifest.json"))
        sig = manifest.pop("signature")
        manifest.pop("signature_algorithm", None)
        if crypto.sign(practice_id, "export_manifest", _canonical(manifest)) != sig:
            return False
        return all(hashlib.sha256(z.read(f["path"])).hexdigest() == f["sha256"]
                   for f in manifest["files"])


def export_client(db: Session, practice_id, client: Client, storage: Storage) -> tuple[bytes, dict]:
    practice = db.get(Practice, practice_id)
    files = client_bundle(db, practice_id, client, storage, practice.name)
    data = build_zip(practice_id, files, kind="client", subject_id=str(client.id))
    return data, {"files": sorted(files), "bytes": len(data)}


def export_practice(db: Session, practice_id, storage: Storage) -> tuple[bytes, dict]:
    orm.prepare(db, create=False)
    practice = db.get(Practice, practice_id)
    clients = list(db.scalars(select(Client).order_by(Client.created_at)))
    files: dict[str, bytes] = {}
    index = []
    for c in clients:
        index.append({"client_id": str(c.id), "erased": c.erased_at is not None,
                      "display_name": c.display_name})
        if c.erased_at is None:
            for path, data in client_bundle(db, practice_id, c, storage, practice.name).items():
                files[f"clients/{c.id}/{path}"] = data
    members = db.execute(select(Member, UserAccount).join(
        UserAccount, UserAccount.id == Member.user_id)).all()
    files["practice/practice.json"] = _json(row_dict(practice))
    files["practice/members.json"] = _json([
        {**row_dict(m), "email": u.email, "phone": u.phone, "display_name": u.display_name}
        for m, u in members])
    files["practice/clients_index.json"] = _json(index)
    files["practice/privacy_settings.json"] = _json(
        [row_dict(s) for s in db.scalars(select(PrivacySettings))])
    files["practice/usage_counters.json"] = _json(
        [row_dict(u) for u in db.scalars(select(UsageCounter))])
    files["practice/activity_log.json"] = _json(
        [row_dict(a) for a in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at))])
    files["practice/privacy_requests.json"] = _json(
        [row_dict(r) for r in db.scalars(select(PrivacyRequest).order_by(PrivacyRequest.created_at))])
    files["summary.pdf"] = text_pdf(f"Practice data export: {practice.name}", [
        f"Generated: {_iso(datetime.now(UTC))}", "",
        f"Clients: {len(clients)} ({sum(1 for c in clients if c.erased_at)} erased tombstones)",
        f"Members: {len(members)}", "",
        "Each client has a folder under clients/ with the same layout as a single-client "
        "export. practice/ holds practice-level records."])
    data = build_zip(practice_id, files, kind="practice", subject_id=str(practice_id))
    return data, {"files": len(files), "bytes": len(data), "clients": len(clients)}


def store_export(db: Session, storage: Storage, req: PrivacyRequest, data: bytes) -> str:
    key = f"{req.practice_id}/privacy/{req.id}/export.zip"
    storage.put(key, data, "application/zip")
    req.result_key = key
    req.expires_at = datetime.now(UTC) + timedelta(days=EXPORT_TTL_DAYS)
    return key


def purge_expired_exports(db: Session, storage: Storage, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    rows = list(db.scalars(select(PrivacyRequest).where(
        PrivacyRequest.result_key.is_not(None), PrivacyRequest.expires_at < now)))
    for r in rows:
        storage.delete(r.result_key)
        r.result_key = None
    return len(rows)


# ================================================================ erasure
def _del(db: Session, sql: str, **params) -> int:
    return db.execute(text(sql), params).rowcount


def _revoke_sessions(db: Session, user_id) -> None:
    _del(db, "UPDATE auth_session SET revoked_at = coalesce(revoked_at, now()), "
             "revoked_reason = 'erased' WHERE user_id = :u", u=user_id)
    _del(db, "DELETE FROM auth_otp WHERE destination IN (SELECT email FROM user_account "
             "WHERE id = :u UNION SELECT phone FROM user_account WHERE id = :u)", u=user_id)
    _del(db, "DELETE FROM auth_identity WHERE user_id = :u", u=user_id)
    _del(db, "DELETE FROM user_credential WHERE user_id = :u", u=user_id)


def erase_client(db: Session, practice_id, client_id, storage: Storage, *,
                 member_id=None, via: str = "request", event=None, ignore_hold: bool = False,
                 log: bool = True) -> dict[str, int]:
    """Erase everything held about a client and leave a minimal tombstone.

    Overwrite/delete model: personal rows are deleted, the client row is kept with
    its name replaced and contact fields nulled (id, created_at, erased_at remain),
    consent rows and receipts stay as evidence, an audit entry records the erasure.
    Storage objects (report PDFs, previous export ZIPs) are deleted first so a retry
    after a partial failure still finds the keys it needs.
    """
    orm.prepare(db, create=False)
    client = get_client_any(db, client_id)
    if client is None:
        raise PrivacyError("client not found")
    if client.erased_at is not None:
        raise AlreadyErasedError("client already erased")
    if client.legal_hold and not ignore_hold:
        raise LegalHoldError("client is under legal hold")
    if log:  # durable, ids only, before anything is deleted (see erasure_log)
        erasure_log.record(db, storage, event or erasure_log.new_event(
            "client", practice_id, client_id, via), publish=event is None)
    c = {"c": client_id}

    births = "SELECT id FROM birth_record WHERE client_id = :c"
    charts = f"SELECT id FROM chart_artifact WHERE birth_record_id IN ({births})"
    keys = [r[0] for r in db.execute(text(
        f"SELECT storage_key FROM report WHERE chart_artifact_id IN ({charts}) "
        "AND storage_key IS NOT NULL"), c)]
    keys += [r[0] for r in db.execute(text(
        "SELECT result_key FROM privacy_request WHERE client_id = :c AND result_key IS NOT NULL"),
        c)]
    for key in keys:
        storage.delete(key)

    counts: dict[str, int] = {"storage_objects": len(keys)}
    plans = "SELECT id FROM remedy_plan WHERE client_id = :c"
    consults = "SELECT id FROM consultation WHERE client_id = :c"
    steps = [
        ("remedy_checkin", f"DELETE FROM remedy_checkin WHERE item_id IN "
                           f"(SELECT id FROM remedy_item WHERE plan_id IN ({plans}))"),
        ("remedy_item", f"DELETE FROM remedy_item WHERE plan_id IN ({plans})"),
        ("remedy_plan", "DELETE FROM remedy_plan WHERE client_id = :c"),
        ("client_tag", "DELETE FROM client_tag WHERE client_id = :c"),
        ("notification", "DELETE FROM notification WHERE client_id = :c"),
        ("consult_prediction", "DELETE FROM consult_prediction WHERE client_id = :c"),
        ("client_life_event", "DELETE FROM client_life_event WHERE client_id = :c"),
        ("consultation_summary", f"DELETE FROM consultation_summary WHERE consultation_id IN ({consults})"),
        ("consultation_note", f"DELETE FROM consultation_note WHERE consultation_id IN ({consults})"),
        ("consultation", "DELETE FROM consultation WHERE client_id = :c"),
        ("report", f"DELETE FROM report WHERE chart_artifact_id IN ({charts})"),
        ("chart_artifact", f"DELETE FROM chart_artifact WHERE birth_record_id IN ({births})"),
        ("birth_record", "DELETE FROM birth_record WHERE client_id = :c"),
        ("idempotency_key", "DELETE FROM idempotency_key WHERE endpoint LIKE :pat "
                            "OR response::text LIKE :pat"),
    ]
    for name, sql in steps:
        params = dict(c)
        if ":pat" in sql:
            params["pat"] = f"%{client_id}%"
        counts[name] = db.execute(text(sql), params).rowcount
    counts["correction_log_scrubbed"] = _del(
        db, "UPDATE correction_log SET old_value = NULL, new_value = NULL WHERE client_id = :c", **c)
    _del(db, "UPDATE privacy_request SET result_key = NULL, expires_at = NULL "
             "WHERE client_id = :c", **c)

    user_ids = [r[0] for r in db.execute(text(
        "SELECT user_id FROM member WHERE client_id = :c"), c)]
    counts["portal_members"] = _del(db, "DELETE FROM member WHERE client_id = :c", **c)
    counts["invites"] = _del(db, "DELETE FROM practice_invite WHERE client_id = :c", **c)
    anonymised = 0
    for uid in user_ids:
        remaining = db.scalar(text("SELECT count(*) FROM app_memberships(:u)"), {"u": uid})
        if not remaining:
            _revoke_sessions(db, uid)
            anonymised += _del(
                db, "UPDATE user_account SET email = NULL, phone = NULL, display_name = NULL, "
                    "subject = 'erased-' || id::text, deleted_at = coalesce(deleted_at, now()), "
                    "updated_at = now() WHERE id = :u", u=uid)
    counts["login_accounts_anonymised"] = anonymised

    _del(db, "UPDATE client SET display_name = :n, contact_email = NULL, contact_phone = NULL, "
             "contact_email_bidx = NULL, contact_phone_bidx = NULL, timezone = NULL, "
             "preferred_language = NULL, legal_hold = false, legal_hold_reason = NULL, "
             "legal_hold_at = NULL, "
             "erased_at = now(), deleted_at = coalesce(deleted_at, now()), updated_at = now() "
             "WHERE id = :c", n=ERASED_NAME, **c)
    db.expire(client)
    _audit(db, practice_id, "client.erased", "client", client_id, member_id=member_id,
           meta={"via": via, "counts": counts, "client_id": str(client_id)})
    return counts


# ================================================================ legal hold
def set_legal_hold(db: Session, practice_id, client: Client, hold: bool, reason: str | None,
                   member_id=None) -> Client:
    if client.erased_at is not None:
        raise AlreadyErasedError("client already erased")
    client.legal_hold = hold
    client.legal_hold_reason = reason if hold else None
    client.legal_hold_at = datetime.now(UTC) if hold else None
    db.flush()
    _audit(db, practice_id, "client.legal_hold_set" if hold else "client.legal_hold_released",
           "client", client.id, member_id=member_id, meta={"client_id": str(client.id)})
    return client


# ================================================================ retention
_CANDIDATES = text("""
SELECT c.id, c.legal_hold,
  GREATEST(c.created_at, c.updated_at,
    (SELECT max(consulted_at) FROM consultation x WHERE x.client_id = c.id),
    (SELECT max(created_at) FROM birth_record x WHERE x.client_id = c.id),
    (SELECT max(r.created_at) FROM report r
       JOIN chart_artifact a ON a.id = r.chart_artifact_id
       JOIN birth_record b ON b.id = a.birth_record_id WHERE b.client_id = c.id),
    (SELECT max(k.created_at) FROM remedy_checkin k
       JOIN remedy_item i ON i.id = k.item_id
       JOIN remedy_plan p ON p.id = i.plan_id WHERE p.client_id = c.id),
    (SELECT max(granted_at) FROM consent x WHERE x.client_id = c.id)) AS last_activity,
  EXISTS (SELECT 1 FROM remedy_plan p WHERE p.client_id = c.id AND p.status = 'active'
          AND p.deleted_at IS NULL) AS active_remedy
FROM client c WHERE c.erased_at IS NULL
""")


def retention_candidates(db: Session, years: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=round(365.25 * years))
    rows = db.execute(_CANDIDATES).all()
    would, held, active = [], 0, 0
    for cid, hold, last, active_remedy in rows:
        if last >= cutoff:
            continue
        if hold:
            held += 1
        elif active_remedy:
            active += 1
        else:
            would.append({"client_id": str(cid), "last_activity": _iso(last)})
    would.sort(key=lambda x: x["last_activity"])
    return {"years": years, "cutoff": _iso(cutoff), "total_clients": len(rows),
            "would_erase": would, "skipped_legal_hold": held,
            "skipped_active_remedy": active, "applied": False}


def get_settings(db: Session, practice_id) -> PrivacySettings:
    s = db.get(PrivacySettings, practice_id)
    if s is None:
        s = PrivacySettings(practice_id=practice_id, retention_auto_apply=False)
        db.add(s)
        db.flush()
    return s


def run_retention(db: Session, practice_id, storage: Storage, *, apply: bool,
                  now: datetime | None = None, member_id=None) -> dict:
    s = get_settings(db, practice_id)
    if s.retention_inactive_years is None:
        raise PrivacyError("retention is not configured for this practice")
    report = retention_candidates(db, s.retention_inactive_years, now)
    if apply:
        done = 0
        for item in report["would_erase"]:
            try:
                erase_client(db, practice_id, uuid.UUID(item["client_id"]), storage,
                             member_id=member_id, via="retention")
                done += 1
            except (LegalHoldError, AlreadyErasedError):
                continue
        report["applied"] = True
        report["erased"] = done
        purge_expired_exports(db, storage)
    return report


# ================================================================ practice deletion
def held_clients(db: Session) -> int:
    return db.scalar(text(
        "SELECT count(*) FROM client WHERE legal_hold AND erased_at IS NULL")) or 0


def delete_practice(db: Session, practice_id, storage: Storage, *, member_id=None,
                    via: str = "request", event=None, ignore_hold: bool = False) -> dict:
    """Account deletion: erase every client, delete exports, members and settings,
    destroy the practice keys (crypto-shred of everything still encrypted), and
    leave an anonymised practice tombstone. Billing identifiers (GSTIN, Razorpay
    ids) are kept for tax and payment retention; see docs/privacy.md."""
    orm.prepare(db, create=False)
    if held_clients(db) and not ignore_hold:
        raise LegalHoldError("clients under legal hold must be released first")
    erasure_log.record(db, storage, event or erasure_log.new_event(
        "practice", practice_id, None, via), publish=event is None)
    counts: dict[str, int] = {"clients_erased": 0}
    for cid in [r[0] for r in db.execute(text(
            "SELECT id FROM client WHERE erased_at IS NULL"))]:
        erase_client(db, practice_id, cid, storage, member_id=member_id,
                     via="practice_deletion" if event is None else "replay",
                     ignore_hold=ignore_hold, log=event is None)
        counts["clients_erased"] += 1
    keys = [r[0] for r in db.execute(text(
        "SELECT result_key FROM privacy_request WHERE result_key IS NOT NULL"))]
    for k in keys:
        storage.delete(k)
    counts["storage_objects"] = len(keys)
    user_ids = [r[0] for r in db.execute(text("SELECT user_id FROM member"))]
    counts["members"] = _del(db, "DELETE FROM member")
    for uid in user_ids:
        if not db.scalar(text("SELECT count(*) FROM app_memberships(:u)"), {"u": uid}):
            _revoke_sessions(db, uid)
            _del(db, "UPDATE user_account SET email = NULL, phone = NULL, display_name = NULL, "
                     "subject = 'erased-' || id::text, deleted_at = coalesce(deleted_at, now()), "
                     "updated_at = now() WHERE id = :u", u=uid)
    _del(db, "UPDATE privacy_request SET result_key = NULL, expires_at = NULL, reason = NULL")
    _del(db, "UPDATE correction_log SET old_value = NULL, new_value = NULL")
    counts["invites"] = _del(db, "DELETE FROM practice_invite")
    # AI connections hold the practice's provider API keys (Fernet): delete outright.
    _del(db, "DELETE FROM ai_routing")
    counts["ai_connections"] = _del(db, "DELETE FROM ai_connection")
    _del(db, "DELETE FROM privacy_settings")
    _del(db, "DELETE FROM usage_counter")
    _del(db, "DELETE FROM idempotency_key")
    _del(db, "UPDATE practice SET name = 'Deleted practice', logo_url = NULL, "
             "brand_primary_color = NULL, brand_accent_color = NULL, brand_footer = NULL, "
             "state = NULL, deleted_at = now(), updated_at = now() WHERE id = :p", p=practice_id)
    _audit(db, practice_id, "practice.deleted", "practice", practice_id, member_id=member_id,
           meta={"counts": counts})
    db.flush()
    counts["keys_destroyed"] = _del(db, "DELETE FROM practice_key")
    crypto.store.forget(practice_id)
    return counts
