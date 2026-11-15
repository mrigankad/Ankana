"""Privacy (DPDP) on real Postgres: field encryption, blind index, key rotation,
export, erasure cascade (incl. storage objects), legal hold, retention, practice
export/deletion, consent receipts and RLS on the new tables."""

import io
import json
import secrets
import uuid
import zipfile
from datetime import UTC, date, datetime, time
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import worker
from app.db import make_engine
from app.main import create_app
from app.privacy import backfill, crypto, orm, service
from app.privacy.keys import DEV_KEY, EnvMasterKeyProvider, PrivacyError, set_master_provider
from app.privacy.models import PRIVACY_TABLES, ConsentReceipt
from app.storage import LocalStorage
from app.tenancy.models import (
    BirthRecord,
    ChartArtifact,
    Client,
    Consultation,
    ConsultationNote,
    RemedyCheckin,
    RemedyItem,
    RemedyPlan,
    Report,
    TimeSource,
)
from app.tenancy.session import tenant_session

pytestmark = pytest.mark.pg


# ------------------------------------------------------------------ fixtures
@pytest.fixture(autouse=True)
def clean_jobs(owner_engine):
    with owner_engine.begin() as c:
        c.execute(text("DELETE FROM job"))


@pytest.fixture()
def storage(tmp_path):
    return LocalStorage(tmp_path / "store", "test-secret", "http://testserver")


@pytest.fixture()
def papi(app_engine, stub, storage) -> TestClient:
    app = create_app(engine=make_engine("sqlite://"), pg_engine=app_engine, verifier=stub,
                     storage=storage)
    return TestClient(app)


def drain(engine, storage) -> None:
    reg = worker.default_registry(engine, storage)
    while worker.process_one(engine, reg, "test"):
        pass


def count(owner_engine, sql: str, **params) -> int:
    with owner_engine.connect() as c:
        return c.scalar(text(sql), params)


def raw(owner_engine, sql: str, **params):
    with owner_engine.connect() as c:
        return c.execute(text(sql), params).all()


@pytest.fixture()
def add_member(papi, auth, owner_engine):
    def _add(practice_id: str, label: str, role: str, client_id: str | None = None) -> str:
        subject = f"{label}-{practice_id[:8]}"
        papi.get("/v1/me", headers=auth(subject))
        with owner_engine.begin() as c:
            uid = c.scalar(text("SELECT id FROM user_account WHERE subject=:s"), {"s": subject})
            c.execute(text("INSERT INTO member (practice_id,user_id,role,client_id) "
                           "VALUES (:p,:u,:r,:c)"),
                      {"p": practice_id, "u": uid, "r": role, "c": client_id})
        return subject

    return _add


def member_id(papi, auth, pid, subject) -> str:
    me = papi.get("/v1/me", headers=auth(subject)).json()
    return next(m["member_id"] for m in me["memberships"] if m["practice_id"] == pid)


def seed_full(engine, storage, pid: str, mid: str, *, name="Asha Verma",
              email="Asha.Verma@Example.com", phone="+91 98765 43210") -> dict:
    """A client with one of everything (rows + a stored report PDF)."""
    with tenant_session(engine, pid) as db:
        client = Client(practice_id=pid, display_name=name, contact_email=email,
                        contact_phone=phone, timezone="Asia/Kolkata", preferred_language="hi")
        db.add(client)
        db.flush()
        birth = BirthRecord(
            practice_id=pid, client_id=client.id, birth_date=date(1990, 5, 15),
            birth_time=time(10, 30), time_source=TimeSource.certificate,
            place_label="Varanasi, near the Assi ghat", latitude=25.3, longitude=82.97,
            timezone_name="Asia/Kolkata")
        db.add(birth)
        db.flush()
        chart = ChartArtifact(practice_id=pid, birth_record_id=birth.id,
                              settings_hash=secrets.token_hex(8), engine_version="t",
                              payload={"lagna": "Cancer"})
        db.add(chart)
        db.flush()
        consult = Consultation(practice_id=pid, client_id=client.id, member_id=mid,
                               chart_artifact_id=chart.id, consulted_at=datetime.now(UTC),
                               mode="video", topic="career")
        db.add(consult)
        db.flush()
        db.add(ConsultationNote(practice_id=pid, consultation_id=consult.id,
                                author_member_id=mid, body="Mother unwell; Saturn dasha ahead"))
        plan = RemedyPlan(practice_id=pid, client_id=client.id, title="Hanuman Chalisa",
                          consultation_id=consult.id)
        db.add(plan)
        db.flush()
        item = RemedyItem(practice_id=pid, plan_id=plan.id, title="Recite daily",
                          instructions="before sunrise")
        db.add(item)
        db.flush()
        db.add(RemedyCheckin(practice_id=pid, item_id=item.id, checkin_date=date.today(),
                             note="done"))
        key = f"{pid}/reports/{chart.id}/v1-abc.pdf"
        db.add(Report(practice_id=pid, chart_artifact_id=chart.id, template_version="1",
                      options_hash="h", status="done", storage_key=key))
        out = {"client_id": str(client.id), "birth_id": str(birth.id), "chart_id": str(chart.id),
               "report_key": key}
    storage.put(key, b"%PDF-1.4 stored report")
    return out


def consent(papi, h, cid, purpose="chart_compute", version="v1"):
    return papi.post(f"/v1/clients/{cid}/consents", headers=h, json={
        "purpose": purpose, "notice_version": version, "notice_text": "We process your chart.",
        "notice_language": "en", "channel": "in_person"})


CLIENT_TABLES = ("birth_record", "consultation", "remedy_plan")


# -------------------------------------------------- 1. encryption round trip
def test_roundtrip_and_ciphertext_at_rest(papi, auth, make_practice, owner_engine, app_engine,
                                          storage):
    pid, subject = make_practice("Enc Jyotish")
    h = auth(subject, pid)
    mid = member_id(papi, auth, pid, subject)
    r = papi.post("/v1/clients", headers=h, json={
        "display_name": "Ravi Kumar", "contact_email": "ravi@example.com",
        "contact_phone": "9876500000"})
    assert r.status_code == 201
    cid = r.json()["client"]["id"]
    assert r.json()["client"]["contact_email"] == "ravi@example.com"
    got = papi.get(f"/v1/clients/{cid}", headers=h).json()["client"]
    assert got["contact_email"] == "ravi@example.com" and got["contact_phone"] == "9876500000"

    seeded = seed_full(app_engine, storage, pid, mid)
    email_ct, phone_ct, bidx = raw(
        owner_engine, "SELECT contact_email, contact_phone, contact_email_bidx FROM client "
                      "WHERE id = :i", i=cid)[0]
    assert email_ct.startswith("enc1:") and "ravi" not in email_ct
    assert phone_ct.startswith("enc1:") and "9876500000" not in phone_ct
    assert bidx and len(bidx) == 64 and "ravi" not in bidx
    assert raw(owner_engine, "SELECT place_label FROM birth_record WHERE id = :i",
               i=seeded["birth_id"])[0][0].startswith("enc1:")
    body = raw(owner_engine, "SELECT body FROM consultation_note n JOIN consultation c "
                             "ON c.id = n.consultation_id WHERE c.client_id = :c",
               c=seeded["client_id"])[0][0]
    assert body.startswith("enc1:") and "Saturn" not in body
    # ORM reads decrypt transparently.
    with tenant_session(app_engine, pid) as db:
        b = db.scalar(select(BirthRecord).where(BirthRecord.id == seeded["birth_id"]))
        assert b.place_label == "Varanasi, near the Assi ghat"


def test_ciphertext_is_bound_to_column_and_practice(papi, auth, make_practice, owner_engine,
                                                    app_engine):
    pid, subject = make_practice("Bind A")
    pid2, subject2 = make_practice("Bind B")
    h, h2 = auth(subject, pid), auth(subject2, pid2)
    a = papi.post("/v1/clients", headers=h, json={
        "display_name": "A", "contact_email": "a@example.com"}).json()["client"]["id"]
    b = papi.post("/v1/clients", headers=h2, json={
        "display_name": "B", "contact_phone": "9000000000"}).json()["client"]["id"]
    # Move A's email ciphertext into A's phone column: wrong label, must not decrypt.
    with owner_engine.begin() as c:
        c.execute(text("UPDATE client SET contact_phone = contact_email WHERE id = :i"), {"i": a})
        # Move B's phone ciphertext into practice A's client: wrong practice.
        ct = c.scalar(text("SELECT contact_phone FROM client WHERE id = :i"), {"i": b})
        c.execute(text("UPDATE client SET contact_email = :v WHERE id = :i"), {"v": ct, "i": a})
    with pytest.raises(PrivacyError):
        with tenant_session(app_engine, pid) as db:
            db.scalar(select(Client).where(Client.id == a))


def test_unbound_session_cannot_encrypt(app_engine):
    crypto.set_scope(None)
    from app.privacy.types import EncryptedText

    with pytest.raises(PrivacyError):
        EncryptedText("x.y").process_bind_param("secret", None)
    # Reading without scope never yields plaintext.
    assert EncryptedText("x.y").process_result_value("enc1:1:abc", None) == "enc1:1:abc"


# ---------------------------------------------------------- 2. blind index
def test_blind_index_lookup(papi, auth, make_practice, add_member):
    pid, subject = make_practice("Blind Co")
    h = auth(subject, pid)
    cid = papi.post("/v1/clients", headers=h, json={
        "display_name": "Meera", "contact_email": "Meera.S@Example.COM",
        "contact_phone": "+91 98765-43210"}).json()["client"]["id"]
    papi.post("/v1/clients", headers=h, json={"display_name": "Other",
                                              "contact_email": "other@example.com"})
    def ids(**q):
        return [c["id"] for c in papi.get("/v1/clients", headers=h, params=q).json()["clients"]]

    assert ids(email="meera.s@example.com") == [cid]
    assert ids(email="  MEERA.S@EXAMPLE.COM ") == [cid]
    assert ids(phone="9876543210") == [cid]
    assert ids(phone="098765 43210") == [cid]
    assert ids(email="meera.s@example.com", phone="9876543210") == [cid]
    assert ids(email="nobody@example.com") == []
    assert ids(email="meera.s@example.com", phone="1111111111") == []
    # Another practice cannot find it (different blind key and RLS).
    pid2, subject2 = make_practice("Blind Rival")
    r = papi.get("/v1/clients", headers=auth(subject2, pid2), params={"email": "meera.s@example.com"})
    assert r.json()["clients"] == []
    # Update changes the index.
    papi.patch(f"/v1/clients/{cid}", headers=h, json={"contact_email": "new@example.com"})
    assert ids(email="meera.s@example.com") == []
    assert ids(email="new@example.com") == [cid]


# ------------------------------------------------------------- 3. rotation
def test_data_key_rotation_and_purge(papi, auth, make_practice, owner_engine, app_engine,
                                     storage):
    pid, subject = make_practice("Rotate Co")
    h = auth(subject, pid)
    mid = member_id(papi, auth, pid, subject)
    seeded = seed_full(app_engine, storage, pid, mid)
    before = raw(owner_engine, "SELECT contact_email FROM client WHERE id = :i",
                 i=seeded["client_id"])[0][0]
    assert before.startswith("enc1:1:")
    with owner_engine.begin() as conn:
        res = backfill.rotate_data_key(conn, pid)
    assert res["new_version"] == 2 and res["reencrypted"] == 7
    after = raw(owner_engine, "SELECT contact_email FROM client WHERE id = :i",
                i=seeded["client_id"])[0][0]
    assert after.startswith("enc1:2:") and after != before
    assert raw(owner_engine, "SELECT place_label FROM birth_record WHERE id = :i",
               i=seeded["birth_id"])[0][0].startswith("enc1:2:")
    crypto.store.forget(pid)
    got = papi.get(f"/v1/clients/{seeded['client_id']}", headers=h).json()["client"]
    assert got["contact_email"] == "Asha.Verma@Example.com"
    # blind index survives rotation (separate key)
    r = papi.get("/v1/clients", headers=h, params={"email": "asha.verma@example.com"})
    assert [c["id"] for c in r.json()["clients"]] == [seeded["client_id"]]
    statuses = dict(raw(owner_engine, "SELECT version, status FROM practice_key "
                                      "WHERE practice_id = :p AND kind = 'dek'", p=pid))
    assert statuses == {1: "retired", 2: "active"}
    with owner_engine.begin() as conn:
        assert backfill.purge_retired(conn, pid) == 1
    crypto.store.forget(pid)
    assert papi.get(f"/v1/clients/{seeded['client_id']}", headers=h).status_code == 200


def test_master_key_rotation(papi, auth, make_practice, owner_engine):
    pid, subject = make_practice("Master Co")
    h = auth(subject, pid)
    cid = papi.post("/v1/clients", headers=h, json={
        "display_name": "M", "contact_email": "m@example.com"}).json()["client"]["id"]
    new_key = secrets.token_bytes(32)
    try:
        set_master_provider(EnvMasterKeyProvider({"dev": DEV_KEY, "k2": new_key}, "k2"))
        with owner_engine.begin() as conn:
            assert backfill.rotate_master(conn) >= 2
        assert {r[0] for r in raw(owner_engine, "SELECT master_key_id FROM practice_key "
                                                "WHERE practice_id = :p", p=pid)} == {"k2"}
        crypto.store.forget()
        assert papi.get(f"/v1/clients/{cid}", headers=h).json()["client"][
            "contact_email"] == "m@example.com"
        # Without the new key the wrapped keys are unusable (nothing is stored in the clear).
        set_master_provider(EnvMasterKeyProvider({"dev": DEV_KEY}, "dev"))
        crypto.store.forget()
        with pytest.raises(PrivacyError):
            papi.get(f"/v1/clients/{cid}", headers=h)
    finally:  # leave every practice wrapped under the default dev key for other tests
        set_master_provider(EnvMasterKeyProvider({"dev": DEV_KEY, "k2": new_key}, "dev"))
        with owner_engine.begin() as conn:
            backfill.rotate_master(conn)
        set_master_provider(None)
        crypto.store.forget()


def test_ai_key_rotation(papi, auth, make_practice, owner_engine):
    pid, _ = make_practice("AI Co")
    old, new = "old-secret", "new-secret"

    def enc(secret: str, plain: str) -> str:
        return "v1:" + backfill._fernet(secret).encrypt(plain.encode()).decode()

    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO ai_connection (practice_id, kind, label, api_key_enc) "
                       "VALUES (:p, 'mock', 'k1', :a), (:p, 'mock', 'k2', :b)"),
                  {"p": pid, "a": enc(old, "sk-one"), "b": enc(new, "sk-two")})
    with owner_engine.begin() as conn:
        assert backfill.rotate_ai_keys(conn, new, old, pid) == 1  # k2 was already under the new one
    for label, plain in (("k1", "sk-one"), ("k2", "sk-two")):
        token = raw(owner_engine, "SELECT api_key_enc FROM ai_connection WHERE practice_id = :p "
                                  "AND label = :l", p=pid, l=label)[0][0]
        assert backfill._fernet(new).decrypt(token.removeprefix("v1:").encode()).decode() == plain


def test_free_text_columns_are_ciphertext_at_rest(papi, auth, make_practice, owner_engine,
                                                  app_engine, storage):
    from app.notify.models import Notification

    pid, subject = make_practice("Free Text Co")
    h = auth(subject, pid)
    mid = member_id(papi, auth, pid, subject)
    seeded = seed_full(app_engine, storage, pid, mid)
    cid = seeded["client_id"]
    assert consent(papi, h, cid).status_code == 201
    with tenant_session(app_engine, pid) as db:
        db.add(Notification(
            practice_id=pid, client_id=cid, kind="reminder", channel="email", language="en",
            local_date=date.today(), dedupe_key="ft-1", subject="Hello Asha " + "s" * 400,
            body="Namaste Asha, remember to recite", scheduled_for=datetime.now(UTC)))
    cols = {
        "remedy_item": ("instructions", "before sunrise"),
        "remedy_checkin": ("note", "done"),
        "consultation": ("topic", "career"),
        "consent": ("notice_text", "We process your chart."),
        "notification": ("body", "Namaste Asha"),
    }
    for table, (col, plain) in cols.items():
        value = raw(owner_engine, f"SELECT {col} FROM {table} WHERE practice_id = :p", p=pid)[0][0]
        assert value.startswith("enc1:") and plain not in value, table
    subj = raw(owner_engine, "SELECT subject FROM notification WHERE practice_id = :p", p=pid)[0][0]
    assert subj.startswith("enc1:") and len(subj) > 500  # a 400+ char subject needs text, not varchar
    # the consent keeps the evidence hash next to the encrypted text
    sha, = raw(owner_engine, "SELECT notice_text_sha256 FROM consent WHERE practice_id = :p",
               p=pid)[0]
    import hashlib

    assert sha == hashlib.sha256(b"We process your chart.").hexdigest()
    # the API and ORM still return plaintext
    receipts = papi.get(f"/v1/clients/{cid}/consent-receipts", headers=h).json()
    first = receipts["receipts"][0] if "receipts" in receipts else receipts[0]
    assert first["notice_text"] == "We process your chart."
    assert first["notice_text_matches_hash"] is True
    with tenant_session(app_engine, pid) as db:
        assert db.scalar(select(RemedyItem.instructions)) == "before sunrise"
        assert db.scalar(select(Consultation.topic)) == "career"
        assert db.scalar(select(Notification.body)) == "Namaste Asha, remember to recite"
    # rotation covers them
    with owner_engine.begin() as conn:
        assert backfill.rotate_data_key(conn, pid)["reencrypted"] == 10
    for table, (col, _) in cols.items():
        assert raw(owner_engine, f"SELECT {col} FROM {table} WHERE practice_id = :p",
                   p=pid)[0][0].startswith("enc1:2:"), table
    crypto.store.forget(pid)
    with tenant_session(app_engine, pid) as db:
        assert db.scalar(select(RemedyItem.instructions)) == "before sunrise"


def test_migration_0005_backfills_plaintext_and_downgrades(make_practice, owner_engine,
                                                           app_engine, db_urls):
    """Rows written by older code (plaintext) are hashed and encrypted by the migration's
    backfill, and the downgrade path restores plaintext."""
    import hashlib


    pid, _ = make_practice("Legacy Free Text")
    ids = {k: str(uuid.uuid4()) for k in ("c", "k", "pl", "it", "ck", "co")}
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO client (id, practice_id, display_name) VALUES (:c,:p,'L')"),
                  {**ids, "p": pid})
        mid = c.scalar(text("SELECT id FROM member WHERE practice_id = :p LIMIT 1"), {"p": pid})
        c.execute(text("INSERT INTO consultation (id, practice_id, client_id, member_id, "
                       "consulted_at, topic) VALUES (:k,:p,:c,:m,now(),'legacy topic')"),
                  {**ids, "p": pid, "m": mid})
        c.execute(text("INSERT INTO remedy_plan (id, practice_id, client_id, title) "
                       "VALUES (:pl,:p,:c,'T')"), {**ids, "p": pid})
        c.execute(text("INSERT INTO remedy_item (id, practice_id, plan_id, title, instructions) "
                       "VALUES (:it,:p,:pl,'t','legacy how')"), {**ids, "p": pid})
        c.execute(text("INSERT INTO remedy_checkin (id, practice_id, item_id, checkin_date, note) "
                       "VALUES (:ck,:p,:it,current_date,'legacy note')"), {**ids, "p": pid})
        c.execute(text("INSERT INTO consent (id, practice_id, client_id, purpose, notice_version, "
                       "notice_text, granted_at) VALUES (:co,:p,:c,'chart_compute','v1',"
                       "'legacy notice',now())"), {**ids, "p": pid})
    only = {("remedy_item", "instructions"), ("remedy_checkin", "note"),
            ("consultation", "topic"), ("consent", "notice_text")}
    with owner_engine.begin() as conn:
        backfill.bind(conn, pid)
        conn.execute(text(
            "UPDATE consent SET notice_text_sha256 = encode(sha256(convert_to(notice_text, "
            "'UTF8')), 'hex') WHERE practice_id = :p AND notice_text_sha256 IS NULL"), {"p": pid})
        assert backfill.encrypt_existing(conn, pid, only=only) == 4
        assert backfill.encrypt_existing(conn, pid, only=only) == 0
    assert raw(owner_engine, "SELECT notice_text_sha256 FROM consent WHERE id = :i",
               i=ids["co"])[0][0] == hashlib.sha256(b"legacy notice").hexdigest()
    assert raw(owner_engine, "SELECT instructions FROM remedy_item WHERE id = :i",
               i=ids["it"])[0][0].startswith("enc1:")
    with tenant_session(app_engine, pid) as db:
        assert db.get(RemedyItem, ids["it"]).instructions == "legacy how"
        assert db.get(Consultation, ids["k"]).topic == "legacy topic"
    with owner_engine.begin() as conn:
        assert backfill.decrypt_existing(conn, only=only) >= 4
    assert raw(owner_engine, "SELECT note FROM remedy_checkin WHERE id = :i",
               i=ids["ck"])[0][0] == "legacy note"


def test_migration_0006_encrypts_existing_rows_and_reverses(admin_url, make_scratch_db):
    """On a database at 0004 holding plaintext free text, upgrading to head hashes the
    consent notice and encrypts every column; downgrading restores plaintext."""
    import hashlib

    from alembic import command

    owner_url, cfg = make_scratch_db("0005_messaging")
    eng = create_engine(owner_url)
    pid, uid, mid, cid = (str(uuid.uuid4()) for _ in range(4))
    k, pl, it, ck, co, nt = (str(uuid.uuid4()) for _ in range(6))
    with eng.begin() as c:
        c.execute(text("INSERT INTO practice (id, name) VALUES (:p, 'Old')"), {"p": pid})
        c.execute(text("SELECT set_config('app.practice_id', :p, true)"), {"p": pid})
        c.execute(text("INSERT INTO user_account (id, issuer, subject) VALUES (:u,'x','s1')"),
                  {"u": uid})
        c.execute(text("INSERT INTO member (id, practice_id, user_id, role) "
                       "VALUES (:m,:p,:u,'owner')"), {"m": mid, "p": pid, "u": uid})
        c.execute(text("INSERT INTO client (id, practice_id, display_name) VALUES (:c,:p,'L')"),
                  {"c": cid, "p": pid})
        c.execute(text("INSERT INTO consultation (id, practice_id, client_id, member_id, "
                       "consulted_at, topic) VALUES (:k,:p,:c,:m,now(),'legacy topic')"),
                  {"k": k, "p": pid, "c": cid, "m": mid})
        c.execute(text("INSERT INTO remedy_plan (id, practice_id, client_id, title) "
                       "VALUES (:pl,:p,:c,'T')"), {"pl": pl, "p": pid, "c": cid})
        c.execute(text("INSERT INTO remedy_item (id, practice_id, plan_id, title, instructions) "
                       "VALUES (:it,:p,:pl,'t','legacy how')"), {"it": it, "p": pid, "pl": pl})
        c.execute(text("INSERT INTO remedy_checkin (id, practice_id, item_id, checkin_date, "
                       "note) VALUES (:ck,:p,:it,current_date,'legacy note')"),
                  {"ck": ck, "p": pid, "it": it})
        c.execute(text("INSERT INTO consent (id, practice_id, client_id, purpose, "
                       "notice_version, notice_text, granted_at) VALUES (:co,:p,:c,"
                       "'chart_compute','v1','legacy notice',now())"),
                  {"co": co, "p": pid, "c": cid})
        c.execute(text("INSERT INTO notification (id, practice_id, client_id, kind, channel, "
                       "local_date, dedupe_key, body, subject, scheduled_for) VALUES (:n,:p,:c,"
                       "'reminder','email',current_date,'d1','Hi Asha','Subj',now())"),
                  {"n": nt, "p": pid, "c": cid})

    def val(table, col, rid):
        with eng.begin() as c:
            c.execute(text("SELECT set_config('app.practice_id', :p, true)"), {"p": pid})
            return c.scalar(text(f"SELECT {col} FROM {table} WHERE id = :i"), {"i": rid})

    command.upgrade(cfg, "head")
    checks = [("consultation", "topic", k, "legacy topic"),
              ("remedy_item", "instructions", it, "legacy how"),
              ("remedy_checkin", "note", ck, "legacy note"),
              ("consent", "notice_text", co, "legacy notice"),
              ("notification", "body", nt, "Hi Asha"), ("notification", "subject", nt, "Subj")]
    for table, col, rid, plain in checks:
        got = val(table, col, rid)
        assert got.startswith("enc1:") and plain not in got, (table, col)
    assert val("consent", "notice_text_sha256", co) == hashlib.sha256(b"legacy notice").hexdigest()
    command.downgrade(cfg, "0005_messaging")
    for table, col, rid, plain in checks:
        assert val(table, col, rid) == plain, (table, col)
    eng.dispose()


# ---------------------------------------------- 4. backfill of existing rows
def test_backfill_encrypts_existing_rows(papi, make_practice, owner_engine, app_engine):
    pid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    with owner_engine.begin() as c:  # a legacy practice: plaintext rows, no keys yet
        c.execute(text("INSERT INTO practice (id, name) VALUES (:p, 'Legacy')"), {"p": pid})
        c.execute(text("INSERT INTO client (id, practice_id, display_name, contact_email, "
                       "contact_phone) VALUES (:i, :p, 'Old', 'legacy@example.com', '9123456789')"),
                  {"i": cid, "p": pid})
    assert count(owner_engine, "SELECT count(*) FROM practice_key WHERE practice_id = :p",
                 p=pid) == 0
    with owner_engine.begin() as conn:
        assert backfill.encrypt_existing(conn, pid) >= 2
        assert backfill.encrypt_existing(conn, pid) == 0  # idempotent
    email, bidx = raw(owner_engine, "SELECT contact_email, contact_email_bidx FROM client "
                                    "WHERE id = :i", i=cid)[0]
    assert email.startswith("enc1:") and bidx
    with tenant_session(app_engine, pid) as db:
        c = db.get(Client, cid)
        assert c.contact_email == "legacy@example.com"
        from app.privacy.blind import find_clients

        assert [x.id for x in find_clients(db, email="LEGACY@example.com")] == [c.id]


# --------------------------------------------------------------- 5. export
def test_export_is_complete_signed_and_scoped(papi, auth, make_practice, add_member,
                                              app_engine, storage):
    pid, subject = make_practice("Export Co")
    h = auth(subject, pid)
    mid = member_id(papi, auth, pid, subject)
    s = seed_full(app_engine, storage, pid, mid)
    cid = s["client_id"]
    assert consent(papi, h, cid).status_code == 201
    papi.patch(f"/v1/clients/{cid}", headers=h, json={"contact_phone": "9000011111"})

    r = papi.post(f"/v1/clients/{cid}/export", headers=h)
    assert r.status_code == 202, r.text
    rid = r.json()["id"]
    assert r.json()["status"] == "queued" and r.json()["download_url"] is None
    drain(app_engine, storage)
    body = papi.get(f"/v1/privacy/requests/{rid}", headers=h).json()
    assert body["status"] == "done", body
    assert body["download_url"] and body["expires_at"]
    path = urlparse(body["download_url"])
    dl = papi.get(f"{path.path}?{path.query}")
    assert dl.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(dl.content))
    names = set(z.namelist())
    expected = {
        "README.txt", "manifest.json", "summary.pdf", "data/client.json",
        "data/birth_records.json", "data/chart_artifacts.json", "data/consents.json",
        "data/consent_receipts.json", "data/consultations.json", "data/remedy_plans.json",
        "data/reports.json", "data/correction_log.json", "data/activity_log.json",
        "data/privacy_requests.json", "data/portal_invites.json",
    }
    assert expected <= names
    report_id = json.loads(z.read("data/reports.json"))[0]["id"]
    assert z.read(f"files/reports/{report_id}.pdf") == b"%PDF-1.4 stored report"
    client = json.loads(z.read("data/client.json"))
    assert client["display_name"] == "Asha Verma"
    assert client["contact_email"] == "Asha.Verma@Example.com"
    assert client["contact_phone"] == "9000011111"
    assert "bidx" not in z.read("data/client.json").decode()
    assert json.loads(z.read("data/birth_records.json"))[0]["place_label"].startswith("Varanasi")
    assert json.loads(z.read("data/chart_artifacts.json"))[0]["payload"] == {"lagna": "Cancer"}
    cons = json.loads(z.read("data/consultations.json"))
    assert cons[0]["notes"][0]["body"] == "Mother unwell; Saturn dasha ahead"
    plans = json.loads(z.read("data/remedy_plans.json"))
    assert plans[0]["items"][0]["checkins"][0]["note"] == "done"
    receipts = json.loads(z.read("data/consent_receipts.json"))
    assert receipts[0]["event"] == "granted" and receipts[0]["verified"] is True
    corr = json.loads(z.read("data/correction_log.json"))
    assert corr[0]["field"] == "contact_phone" and corr[0]["old_value"] == "+91 98765 43210"
    assert any(a["action"] == "consent.granted"
               for a in json.loads(z.read("data/activity_log.json")))
    pdf = z.read("summary.pdf")
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert b"Asha Verma" in pdf and b"Saturn dasha" in pdf

    with tenant_session(app_engine, pid) as db:
        orm.prepare(db, create=False)
        assert service.verify_zip(pid, dl.content)
        tampered = io.BytesIO()
        with zipfile.ZipFile(tampered, "w") as t:
            for n in z.namelist():
                t.writestr(n, z.read(n) + (b" " if n == "data/client.json" else b""))
        assert not service.verify_zip(pid, tampered.getvalue())

    # Access control: assistants refused, another practice 404, the client sees only self.
    assistant = add_member(pid, "asst", "assistant")
    assert papi.post(f"/v1/clients/{cid}/export", headers=auth(assistant, pid)).status_code == 403
    pid2, subject2 = make_practice("Rival")
    assert papi.post(f"/v1/clients/{cid}/export", headers=auth(subject2, pid2)).status_code == 404
    assert papi.get(f"/v1/privacy/requests/{rid}", headers=auth(subject2, pid2)).status_code == 404
    portal = add_member(pid, "portal", "client", cid)
    mine = papi.post(f"/v1/clients/{cid}/export", headers=auth(portal, pid))
    assert mine.status_code == 202
    other = seed_full(app_engine, storage, pid, mid, name="Someone Else")
    assert papi.post(f"/v1/clients/{other['client_id']}/export",
                     headers=auth(portal, pid)).status_code == 404


# -------------------------------------------------- 6. erasure and legal hold
def test_erasure_cascade_tombstone_and_storage(papi, auth, make_practice, add_member,
                                               owner_engine, app_engine, storage):
    pid, subject = make_practice("Erase Co")
    h = auth(subject, pid)
    mid = member_id(papi, auth, pid, subject)
    s = seed_full(app_engine, storage, pid, mid)
    keep = seed_full(app_engine, storage, pid, mid, name="Bystander", email="by@example.com")
    cid = s["client_id"]
    consent(papi, h, cid)
    papi.patch(f"/v1/clients/{cid}", headers=h, json={"contact_email": "changed@example.com"})
    portal = add_member(pid, "portal", "client", cid)
    papi.post(f"/v1/clients/{cid}/export", headers=h)
    drain(app_engine, storage)
    export_key = raw(owner_engine, "SELECT result_key FROM privacy_request WHERE client_id = :c "
                                   "AND result_key IS NOT NULL", c=cid)[0][0]
    assert storage.exists(export_key) and storage.exists(s["report_key"])

    # Legal hold blocks erasure.
    assert papi.put(f"/v1/clients/{cid}/legal-hold", headers=h,
                    json={"hold": True, "reason": "court notice 42"}).json()["legal_hold"]
    blocked = papi.post(f"/v1/clients/{cid}/erase", headers=h, json={"reason": "client asked"})
    assert blocked.status_code == 409 and blocked.json()["code"] == "legal_hold"
    assert papi.put(f"/v1/clients/{cid}/legal-hold", headers=h,
                    json={"hold": False}).json()["legal_hold"] is False

    # Hold placed after the request was queued: the job reports blocked, data untouched.
    queued = papi.post(f"/v1/clients/{cid}/erase", headers=h, json={"reason": "client asked"})
    assert queued.status_code == 202
    papi.put(f"/v1/clients/{cid}/legal-hold", headers=h, json={"hold": True, "reason": "late"})
    drain(app_engine, storage)
    st = papi.get(f"/v1/privacy/requests/{queued.json()['id']}", headers=h).json()
    assert st["status"] == "blocked" and "legal hold" in st["error"]
    assert count(owner_engine, "SELECT count(*) FROM birth_record WHERE client_id = :c", c=cid) == 1

    papi.put(f"/v1/clients/{cid}/legal-hold", headers=h, json={"hold": False})
    r = papi.post(f"/v1/clients/{cid}/erase", headers=h, json={"reason": "DPDP erasure request"})
    assert r.status_code == 202
    drain(app_engine, storage)
    done = papi.get(f"/v1/privacy/requests/{r.json()['id']}", headers=h).json()
    assert done["status"] == "done", done
    assert done["result"]["counts"]["report"] == 1 and done["result"]["counts"]["storage_objects"] >= 2

    for table, col in (("birth_record", "client_id"), ("consultation", "client_id"),
                       ("remedy_plan", "client_id")):
        assert count(owner_engine, f"SELECT count(*) FROM {table} WHERE {col} = :c", c=cid) == 0
    assert count(owner_engine, "SELECT count(*) FROM chart_artifact WHERE id = :i",
                 i=s["chart_id"]) == 0
    assert count(owner_engine, "SELECT count(*) FROM report WHERE chart_artifact_id = :i",
                 i=s["chart_id"]) == 0
    assert count(owner_engine, "SELECT count(*) FROM consultation_note n WHERE NOT EXISTS "
                               "(SELECT 1 FROM consultation c WHERE c.id = n.consultation_id)") == 0
    assert count(owner_engine, "SELECT count(*) FROM remedy_item WHERE plan_id NOT IN "
                               "(SELECT id FROM remedy_plan)") == 0
    assert not storage.exists(s["report_key"]) and not storage.exists(export_key)
    assert storage.exists(keep["report_key"])  # other clients untouched
    assert count(owner_engine, "SELECT count(*) FROM birth_record WHERE client_id = :c",
                 c=keep["client_id"]) == 1

    name, email, phone, bidx, erased, deleted = raw(
        owner_engine, "SELECT display_name, contact_email, contact_phone, contact_email_bidx, "
                      "erased_at, deleted_at FROM client WHERE id = :i", i=cid)[0]
    assert name == "Erased client" and email is None and phone is None and bidx is None
    assert erased and deleted
    assert count(owner_engine, "SELECT count(*) FROM consent WHERE client_id = :c", c=cid) == 1
    assert count(owner_engine, "SELECT count(*) FROM consent_receipt WHERE client_id = :c",
                 c=cid) == 1
    assert count(owner_engine, "SELECT count(*) FROM audit_event WHERE action = 'client.erased' "
                               "AND entity_id = :c", c=cid) == 1
    assert raw(owner_engine, "SELECT old_value, new_value FROM correction_log WHERE client_id = :c",
               c=cid) == [(None, None)]
    assert count(owner_engine, "SELECT count(*) FROM member WHERE client_id = :c", c=cid) == 0
    email_left, deleted_user = raw(owner_engine, "SELECT email, deleted_at FROM user_account "
                                                 "WHERE subject LIKE 'erased-%' LIMIT 1")[0]
    assert email_left is None and deleted_user
    assert papi.get(f"/v1/clients/{cid}", headers=h).status_code == 404
    assert papi.post(f"/v1/clients/{cid}/export", headers=h).status_code == 409
    assert papi.post(f"/v1/clients/{cid}/erase", headers=h,
                     json={"reason": "again"}).status_code == 409
    del portal


def test_erase_needs_clinical_role_and_reason(papi, auth, make_practice, add_member, app_engine,
                                              storage):
    pid, subject = make_practice("Roles Co")
    h = auth(subject, pid)
    s = seed_full(app_engine, storage, pid, member_id(papi, auth, pid, subject))
    asst = add_member(pid, "asst", "assistant")
    url = f"/v1/clients/{s['client_id']}/erase"
    assert papi.post(url, headers=auth(asst, pid), json={"reason": "no way"}).status_code == 403
    assert papi.post(url, headers=h, json={"reason": "x"}).status_code == 422


# ------------------------------------------------------------- 7. retention
def test_retention_dry_run_then_apply(papi, auth, make_practice, owner_engine, app_engine,
                                      storage):
    pid, subject = make_practice("Retention Co")
    h = auth(subject, pid)
    mid = member_id(papi, auth, pid, subject)
    assert papi.post("/v1/practice/retention/dry-run", headers=h).status_code == 409
    old = seed_full(app_engine, storage, pid, mid, name="Old")
    recent = seed_full(app_engine, storage, pid, mid, name="Recent")
    held = seed_full(app_engine, storage, pid, mid, name="Held")
    active = seed_full(app_engine, storage, pid, mid, name="Active")
    papi.put(f"/v1/clients/{held['client_id']}/legal-hold", headers=h,
             json={"hold": True, "reason": "dispute"})
    with tenant_session(app_engine, pid) as db:
        db.execute(text("UPDATE remedy_plan SET status = 'active' WHERE client_id = :c"),
                   {"c": active["client_id"]})
    with owner_engine.begin() as c:  # age three of them past 3 years (every activity source)
        for who in (old, held, active):
            cid = who["client_id"]
            for sql in (
                "UPDATE client SET created_at = now() - interval '4 years', "
                "updated_at = now() - interval '4 years' WHERE id = :c",
                "UPDATE consultation SET consulted_at = now() - interval '4 years' "
                "WHERE client_id = :c",
                "UPDATE birth_record SET created_at = now() - interval '4 years' "
                "WHERE client_id = :c",
                "UPDATE report SET created_at = now() - interval '4 years' WHERE chart_artifact_id "
                "IN (SELECT id FROM chart_artifact WHERE birth_record_id IN "
                "(SELECT id FROM birth_record WHERE client_id = :c))",
                "UPDATE remedy_checkin SET created_at = now() - interval '4 years' WHERE item_id IN "
                "(SELECT id FROM remedy_item WHERE plan_id IN "
                "(SELECT id FROM remedy_plan WHERE client_id = :c))",
            ):
                c.execute(text(sql), {"c": cid})
    assert papi.put("/v1/practice/privacy-settings", headers=h,
                    json={"retention_inactive_years": 3}).status_code == 200
    assert papi.put("/v1/practice/privacy-settings", headers=h, json={
        "retention_auto_apply": True}).status_code == 422

    r = papi.post("/v1/practice/retention/dry-run", headers=h)
    assert r.status_code == 202
    drain(app_engine, storage)
    rep = papi.get(f"/v1/privacy/requests/{r.json()['id']}", headers=h).json()["result"]
    assert [c["client_id"] for c in rep["would_erase"]] == [old["client_id"]]
    assert rep["skipped_legal_hold"] == 1 and rep["skipped_active_remedy"] == 1
    assert rep["total_clients"] == 4 and rep["applied"] is False
    assert count(owner_engine, "SELECT count(*) FROM client WHERE erased_at IS NOT NULL "
                               "AND practice_id = :p", p=pid) == 0

    assert papi.post("/v1/practice/retention/apply", headers=h,
                     json={"confirm": False}).status_code == 422
    r = papi.post("/v1/practice/retention/apply", headers=h, json={"confirm": True})
    drain(app_engine, storage)
    rep = papi.get(f"/v1/privacy/requests/{r.json()['id']}", headers=h).json()["result"]
    assert rep["applied"] and rep["erased"] == 1
    erased = {r[0] for r in raw(owner_engine, "SELECT id::text FROM client WHERE erased_at "
                                              "IS NOT NULL AND practice_id = :p", p=pid)}
    assert erased == {old["client_id"]}
    assert recent["client_id"] not in erased


# ------------------------------------------------- 8. practice export + delete
def test_practice_export_and_account_deletion(papi, auth, make_practice, owner_engine,
                                              app_engine, storage):
    pid, subject = make_practice("Closing Co")
    h = auth(subject, pid)
    mid = member_id(papi, auth, pid, subject)
    a = seed_full(app_engine, storage, pid, mid, name="Client A")
    b = seed_full(app_engine, storage, pid, mid, name="Client B", email="b@example.com")
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO ai_connection (practice_id, kind, label, api_key_enc) "
                       "VALUES (:p, 'mock', 'k', 'v1:secret')"), {"p": pid})

    r = papi.post("/v1/practice/export", headers=h)
    assert r.status_code == 202
    drain(app_engine, storage)
    body = papi.get(f"/v1/privacy/requests/{r.json()['id']}", headers=h).json()
    assert body["status"] == "done"
    z = zipfile.ZipFile(io.BytesIO(storage.get(
        raw(owner_engine, "SELECT result_key FROM privacy_request WHERE id = :i",
            i=r.json()["id"])[0][0])))
    names = set(z.namelist())
    for who in (a, b):
        assert f"clients/{who['client_id']}/data/client.json" in names
        assert f"clients/{who['client_id']}/data/consultations.json" in names
    assert {"practice/practice.json", "practice/members.json", "practice/activity_log.json",
            "practice/clients_index.json", "summary.pdf"} <= names
    members = json.loads(z.read("practice/members.json"))
    assert members[0]["role"] == "owner" and members[0]["email"]

    # Guards.
    assert papi.post("/v1/practice/delete", headers=h,
                     json={"confirm_name": "wrong"}).status_code == 422
    papi.put(f"/v1/clients/{a['client_id']}/legal-hold", headers=h, json={"hold": True})
    assert papi.post("/v1/practice/delete", headers=h,
                     json={"confirm_name": "Closing Co"}).json()["code"] == "legal_hold"
    papi.put(f"/v1/clients/{a['client_id']}/legal-hold", headers=h, json={"hold": False})

    export_key = raw(owner_engine, "SELECT result_key FROM privacy_request WHERE id = :i",
                     i=r.json()["id"])[0][0]
    d = papi.post("/v1/practice/delete", headers=h, json={"confirm_name": "Closing Co",
                                                          "reason": "closing the practice"})
    assert d.status_code == 202, d.text
    drain(app_engine, storage)
    st = raw(owner_engine, "SELECT status, error FROM privacy_request WHERE id = :i",
             i=d.json()["id"])[0]
    assert st[0] == "done", st
    assert count(owner_engine, "SELECT count(*) FROM client WHERE practice_id = :p AND "
                               "erased_at IS NULL", p=pid) == 0
    for table in ("member", "practice_key", "ai_connection", "birth_record", "consultation",
                  "chart_artifact", "report", "privacy_settings"):
        assert count(owner_engine, f"SELECT count(*) FROM {table} WHERE practice_id = :p",
                     p=pid) == 0, table
    name, deleted = raw(owner_engine, "SELECT name, deleted_at FROM practice WHERE id = :p",
                        p=pid)[0]
    assert name == "Deleted practice" and deleted
    assert count(owner_engine, "SELECT count(*) FROM audit_event WHERE practice_id = :p AND "
                               "action = 'practice.deleted'", p=pid) == 1
    assert not storage.exists(a["report_key"]) and not storage.exists(b["report_key"])
    assert not storage.exists(export_key)
    assert papi.get("/v1/clients", headers=h).status_code in (401, 403)


# ----------------------------------------------------------- 9. consent receipts
def test_consent_receipts_are_immutable_signed_and_portal_readable(
        papi, auth, make_practice, add_member, owner_engine, app_engine):
    pid, subject = make_practice("Receipt Co")
    h = auth(subject, pid)
    cid = papi.post("/v1/clients", headers=h, json={"display_name": "Pooja"}).json()["client"]["id"]
    g = consent(papi, h, cid)
    assert g.status_code == 201
    assert consent(papi, h, cid).status_code == 200  # replay: no second receipt
    w = papi.post(f"/v1/clients/{cid}/consents/chart_compute/withdraw", headers=h)
    assert w.status_code == 200
    rows = papi.get(f"/v1/clients/{cid}/consent-receipts", headers=h).json()["receipts"]
    assert [r["event"] for r in rows] == ["granted", "withdrawn"]
    import hashlib

    for r in rows:
        assert r["verified"] is True and r["purpose"] == "chart_compute"
        assert r["notice_text_sha256"] == hashlib.sha256(b"We process your chart.").hexdigest()
        assert r["notice_text"] == "We process your chart." and r["notice_text_matches_hash"]
        assert len(r["signature"]) == 64 and len(r["receipt_hash"]) == 64
    one = papi.get(f"/v1/clients/{cid}/consent-receipts/{rows[0]['id']}", headers=h)
    assert one.status_code == 200 and one.json()["receipt_hash"] == rows[0]["receipt_hash"]

    # The client portal user reads their own receipts only.
    portal = add_member(pid, "portal", "client", cid)
    mine = papi.get(f"/v1/clients/{cid}/consent-receipts", headers=auth(portal, pid))
    assert mine.status_code == 200 and len(mine.json()["receipts"]) == 2
    other = papi.post("/v1/clients", headers=h, json={"display_name": "Else"}).json()["client"]["id"]
    assert papi.get(f"/v1/clients/{other}/consent-receipts",
                    headers=auth(portal, pid)).status_code == 404

    # Append-only for the app role.
    with pytest.raises(DBAPIError):
        with tenant_session(app_engine, pid) as db:
            db.execute(text("UPDATE consent_receipt SET purpose = 'marketing'"))
    with pytest.raises(DBAPIError):
        with tenant_session(app_engine, pid) as db:
            db.execute(text("DELETE FROM consent_receipt"))
    # Tampering at the DB level (owner) is detected by verification.
    with owner_engine.begin() as c:
        c.execute(text("UPDATE consent_receipt SET purpose = 'marketing' WHERE id = :i"),
                  {"i": rows[0]["id"]})
    with tenant_session(app_engine, pid) as db:
        rec = db.scalar(select(ConsentReceipt).where(ConsentReceipt.id == rows[0]["id"]))
        assert service.verify_receipt(db, rec) is False


# ------------------------------------------------------- 10. corrections log
def test_correction_log(papi, auth, make_practice):
    pid, subject = make_practice("Correct Co")
    h = auth(subject, pid)
    cid = papi.post("/v1/clients", headers=h, json={
        "display_name": "Kiran", "contact_email": "k@example.com"}).json()["client"]["id"]
    papi.patch(f"/v1/clients/{cid}", headers={**h, "X-Correction-Reason": "typo"},
               json={"display_name": "Kiran R", "contact_email": "k@example.com"})
    birth = {"birth_date": "1995-03-15", "birth_time": "06:42", "time_source": "memory",
             "place_label": "Pune", "latitude": 18.5, "longitude": 73.8,
             "timezone_name": "Asia/Kolkata"}
    papi.post(f"/v1/clients/{cid}/birth-records", headers=h, json=birth)
    papi.post(f"/v1/clients/{cid}/birth-records", headers=h,
              json={**birth, "birth_time": "07:10", "place_label": "Pune, Maharashtra"})
    log = papi.get(f"/v1/clients/{cid}/corrections", headers=h).json()["corrections"]
    fields = {(c["entity_type"], c["field"]): c for c in log}
    assert fields[("client", "display_name")]["old_value"] == "Kiran"
    assert fields[("client", "display_name")]["reason"] == "typo"
    assert ("client", "contact_email") not in fields  # unchanged values are not logged
    assert fields[("birth_record", "place_label")]["new_value"] == "Pune, Maharashtra"
    assert fields[("birth_record", "birth_time")]["old_value"] == "06:42:00"


# ------------------------------------------------------------- 11. RLS on new tables
def test_new_tables_have_forced_rls(owner_engine):
    rows = raw(owner_engine, "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                             "WHERE relname = ANY(:t) AND relkind = 'r'", t=list(PRIVACY_TABLES))
    policies = {r[0] for r in raw(owner_engine, "SELECT tablename FROM pg_policies")}
    assert {r[0] for r in rows} == set(PRIVACY_TABLES)
    for name, enabled, forced in rows:
        assert enabled and forced and name in policies, name


def test_new_tables_are_tenant_isolated(papi, auth, make_practice, app_engine, storage):
    pa, sa = make_practice("RLS A")
    pb, sb = make_practice("RLS B")
    ha, hb = auth(sa, pa), auth(sb, pb)
    ca = papi.post("/v1/clients", headers=ha, json={"display_name": "A"}).json()["client"]["id"]
    cb = papi.post("/v1/clients", headers=hb, json={"display_name": "B"}).json()["client"]["id"]
    consent(papi, ha, ca)
    consent(papi, hb, cb)
    papi.post(f"/v1/clients/{ca}/export", headers=ha)
    papi.post(f"/v1/clients/{cb}/export", headers=hb)
    papi.patch(f"/v1/clients/{ca}", headers=ha, json={"display_name": "A2"})
    papi.put("/v1/practice/privacy-settings", headers=ha, json={"retention_inactive_years": 5})
    for table in PRIVACY_TABLES:
        with tenant_session(app_engine, pa) as db:
            practices = {r[0] for r in db.execute(text(f"SELECT practice_id FROM {table}"))}
        assert practices <= {uuid.UUID(pa)}, table
        assert practices == {uuid.UUID(pa)}, table  # A has rows in every new table
        with Session(app_engine) as s, s.begin():  # no practice bound: nothing visible
            assert s.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table
    # Cannot write a row for another practice.
    with pytest.raises(DBAPIError):
        with tenant_session(app_engine, pa) as db:
            db.execute(text("INSERT INTO privacy_request (practice_id, kind) "
                            "VALUES (:p, 'client_export')"), {"p": pb})
    with tenant_session(app_engine, pa) as db:  # B's keys are invisible to A
        assert db.scalar(text("SELECT count(*) FROM practice_key WHERE practice_id = :p"),
                         {"p": pb}) == 0


# ------------------------------------------------------------- misc unit tests
def test_every_encrypted_column_is_known():
    cols = {(t, c) for t, c, _ in backfill.encrypted_columns()}
    assert cols == {
        ("client", "contact_email"), ("client", "contact_phone"), ("client", "legal_hold_reason"),
        ("birth_record", "place_label"), ("consultation_note", "body"),
        ("correction_log", "old_value"), ("correction_log", "new_value"),
        ("privacy_request", "reason"),
        ("remedy_item", "instructions"), ("remedy_checkin", "note"), ("consultation", "topic"),
        ("consent", "notice_text"), ("notification", "subject"), ("notification", "body"),
        ("consultation", "client_question"), ("consultation_summary", "topics"),
        ("consultation_summary", "remedies_given"), ("consult_prediction", "statement"),
        ("consult_prediction", "outcome_note"), ("client_life_event", "title"),
        ("client_life_event", "notes"),
    }
    for t, c, label in backfill.encrypted_columns():
        assert label == f"{t}.{c}"


def test_production_requires_master_key():
    from app.privacy.keys import provider_from_env

    with pytest.raises(PrivacyError):
        provider_from_env({"API_ENV": "production"})
    p = provider_from_env({"ANKANA_MASTER_KEY": __import__("base64").b64encode(
        secrets.token_bytes(32)).decode(), "API_ENV": "production"})
    assert p.current_id == "env-1"


def test_text_pdf_is_wellformed():
    from app.privacy.pdf import text_pdf

    pdf = text_pdf("Title", [f"line {i} " + "word " * 40 for i in range(120)])
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert pdf.count(b"/Type /Page ") >= 2
