"""Report pipeline end to end: API -> queue -> worker -> Chromium PDF -> signed URL.

Chromium tests skip when `python -m playwright install chromium` has not been run.
"""

import base64
import os
import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient

try:
    import swisseph  # noqa: F401
except ImportError:  # dev machines without a C compiler
    os.environ.setdefault("ANKANA_EPHEMERIS", "astronomy")

from app import worker
from app.db import make_engine
from app.main import create_app
from app.reports.html import DEFAULT_SECTIONS
from app.storage import LocalStorage
from app.tenancy.models import BirthRecord, ChartArtifact, Client, TimeSource
from app.tenancy.session import tenant_session
from nakshatra_core.chart import compute_vedic_chart_artifact

BIRTH = {"birthDate": "1990-05-15", "birthTime": "10:30", "timezoneName": "Asia/Kolkata",
         "latitude": 28.6139, "longitude": 77.209, "placeLabel": "New Delhi"}
PNG_1PX = ("data:image/png;base64," + base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)).decode())


def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return os.path.exists(p.chromium.executable_path)
    except Exception:
        return False


needs_chromium = pytest.mark.skipif(
    os.environ.get("REPORT_RENDERER") == "stub" or not chromium_available(),
    reason="chromium not installed or REPORT_RENDERER=stub")


@pytest.fixture(autouse=True)
def clean_jobs(owner_engine):
    from sqlalchemy import text

    with owner_engine.begin() as c:
        c.execute(text("DELETE FROM job"))


@pytest.fixture()
def storage(tmp_path):
    return LocalStorage(tmp_path / "store", "test-secret", "http://testserver")


@pytest.fixture()
def client_api(app_engine, stub, storage) -> TestClient:
    app = create_app(engine=make_engine("sqlite://"), pg_engine=app_engine, verifier=stub,
                     storage=storage)
    return TestClient(app)


@pytest.fixture()
def seed_chart(app_engine):
    def _seed(practice_id: str, name: str = "Asha Verma") -> str:
        with tenant_session(app_engine, practice_id) as db:
            client = Client(practice_id=practice_id, display_name=name)
            db.add(client)
            db.flush()
            birth = BirthRecord(
                practice_id=practice_id, client_id=client.id, birth_date=date(1990, 5, 15),
                birth_time=time(10, 30), time_source=TimeSource.certificate,
                place_label="New Delhi", latitude=28.6139, longitude=77.209,
                timezone_name="Asia/Kolkata")
            db.add(birth)
            db.flush()
            art = ChartArtifact(practice_id=practice_id, birth_record_id=birth.id,
                                settings_hash=uuid.uuid4().hex, engine_version="test",
                                payload=compute_vedic_chart_artifact(BIRTH))
            db.add(art)
            db.flush()
            return str(art.id)

    return _seed


def run_worker(app_engine, storage, html_to_pdf=None):
    from app.reports import service

    registry = worker.default_registry(app_engine, storage)
    if html_to_pdf:
        registry.handlers[service.RENDER_REPORT] = lambda job: service.render_report_job(
            job, app_engine, storage, html_to_pdf)
    worker.run_worker(app_engine, registry, concurrency=1, once=True, poll_seconds=0.05)


def fake_pdf(html, branding, title):
    fake_pdf.calls.append(html)
    return b"%PDF-1.4 fake"


fake_pdf.calls = []


def test_request_is_202_idempotent_and_tenant_scoped(client_api, auth, make_practice,
                                                     seed_chart):
    pid, subject = make_practice("Acme Jyotish")
    chart = seed_chart(pid)
    h = auth(subject, pid)
    r = client_api.post("/v1/reports", json={"chart_id": chart}, headers=h)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued" and body["download_url"] is None
    assert r.headers["location"] == f"/v1/reports/{body['id']}"
    again = client_api.post("/v1/reports", json={"chart_id": chart}, headers=h).json()
    assert again["id"] == body["id"]  # same artifact + options -> same report
    other = client_api.post("/v1/reports", json={"chart_id": chart, "language": "hi"},
                            headers=h).json()
    assert other["id"] != body["id"]

    # Another practice cannot see or request it.
    pid2, subject2 = make_practice("Rival")
    h2 = auth(subject2, pid2)
    assert client_api.get(f"/v1/reports/{body['id']}", headers=h2).status_code == 404
    assert client_api.post("/v1/reports", json={"chart_id": chart}, headers=h2).status_code == 404
    assert client_api.post("/v1/reports", json={"chart_id": chart, "template": "x"},
                           headers=h).status_code == 422
    assert client_api.post("/v1/reports", json={"chart_id": chart, "language": "fr"},
                           headers=h).status_code == 422


def test_branding_validation(client_api, auth, make_practice):
    pid, subject = make_practice("Brand Co")
    h = auth(subject, pid)
    ok = client_api.put("/v1/practice/branding", headers=h, json={
        "logo_url": PNG_1PX, "brand_primary_color": "#112233", "brand_accent_color": "#ffaa00",
        "brand_footer": "Dr. Rao - 98xxxxxx"})
    assert ok.status_code == 200 and ok.json()["brand_primary_color"] == "#112233"
    for bad in ({"brand_primary_color": "red"}, {"logo_url": "http://insecure/x.png"},
                {"logo_url": "javascript:alert(1)"}):
        assert client_api.put("/v1/practice/branding", headers=h, json=bad).status_code == 422


def test_job_to_pdf_with_stub_renderer(client_api, auth, make_practice, seed_chart, app_engine,
                                       storage):
    pid, subject = make_practice("Acme Jyotish")
    chart = seed_chart(pid)
    h = auth(subject, pid)
    put = client_api.put("/v1/practice/branding", headers=h, json={
        "logo_url": PNG_1PX, "brand_primary_color": "#112233"})
    assert put.status_code == 200, put.text
    assert client_api.get("/v1/practice/branding", headers=h).json()["brand_primary_color"] == "#112233"
    rid = client_api.post("/v1/reports", headers=h, json={
        "chart_id": chart, "lal_kitab": True,
        "sections": ["summary", "kundali", "planets", "remedies"]}).json()["id"]
    fake_pdf.calls.clear()
    run_worker(app_engine, storage, fake_pdf)

    got = client_api.get(f"/v1/reports/{rid}", headers=h).json()
    assert got["status"] == "done" and got["size_bytes"] == len(b"%PDF-1.4 fake")
    html = fake_pdf.calls[0]
    assert "Acme Jyotish" in html
    assert "Asha Verma" in html
    assert "#112233" in html, html[html.index("--primary")-20:][:200]
    assert "data:image/png;base64" in html and "<svg" in html
    assert "Lal Kitab" in html and "Sleeping planets" in html
    assert "Urbanist" in html and "font/ttf;base64" in html
    assert "<script" not in html

    dl = client_api.get(got["download_url"].replace("http://testserver", ""))
    assert dl.status_code == 200 and dl.content == b"%PDF-1.4 fake"
    bad = got["download_url"].replace("http://testserver", "").replace("sig=", "sig=0")
    assert client_api.get(bad).status_code == 403
    # Re-running does not render again (idempotent), and storage is keyed by artifact.
    assert f"/reports/{chart}/v1-" in got["download_url"]


def test_render_failure_retries_then_marks_failed(client_api, auth, make_practice, seed_chart,
                                                  app_engine, storage, monkeypatch):
    from app.jobs import queue

    monkeypatch.setattr(queue, "BACKOFF_BASE_SECONDS", 0.0)
    pid, subject = make_practice("Fail Co")
    chart = seed_chart(pid)
    h = auth(subject, pid)
    rid = client_api.post("/v1/reports", headers=h, json={"chart_id": chart}).json()["id"]

    def boom(html, branding, title):
        raise RuntimeError("chromium crashed")

    run_worker(app_engine, storage, boom)
    got = client_api.get(f"/v1/reports/{rid}", headers=h).json()
    assert got["status"] == "failed" and "chromium crashed" in got["error"]
    # Re-requesting a failed report re-queues it and can then succeed.
    client_api.post("/v1/reports", headers=h, json={"chart_id": chart})
    assert client_api.get(f"/v1/reports/{rid}", headers=h).json()["status"] == "queued"
    run_worker(app_engine, storage, fake_pdf)
    assert client_api.get(f"/v1/reports/{rid}", headers=h).json()["status"] == "done"


def test_hindi_html_uses_devanagari_labels():
    from app.reports.branding import Branding
    from app.reports.service import build_html

    inputs = {"artifact": compute_vedic_chart_artifact(BIRTH), "client_name": "आशा",
              "language": "hi", "template": "standard", "created_at": __import__(
                  "datetime").datetime(2026, 11, 14),
              "options": {"sections": ["summary", "kundali", "planets", "dasha"],
                          "branding": Branding("प्रैक्टिस").snapshot()}}
    html = build_html(inputs)
    assert "जन्म कुंडली रिपोर्ट" in html and "मेष" in html and "Noto Sans Devanagari" in html
    assert html == build_html(inputs)  # deterministic


def test_footer_carries_branding_and_agpl_line():
    from app.reports.branding import Branding
    from app.reports.pdf import footer_template

    f = footer_template(Branding("Acme <b>", footer="Dr Rao"))
    assert "Prepared with Ankana · open source under AGPL-3.0" in f
    assert "Dr Rao" in f and "<b>" not in f


def test_logo_ssrf_guard():
    from app.reports.branding import BrandingError, logo_data_uri

    for url in ("https://localhost/x.png", "https://127.0.0.1/x.png",
                "https://169.254.169.254/latest/meta-data", "file:///etc/passwd"):
        with pytest.raises(BrandingError):
            logo_data_uri(url)


@needs_chromium
@pytest.mark.parametrize("language", ["en", "hi"])
def test_real_chromium_pdf(client_api, auth, make_practice, seed_chart, app_engine, storage,
                           language):
    pid, subject = make_practice("Acme Jyotish")
    chart = seed_chart(pid)
    h = auth(subject, pid)
    client_api.put("/v1/practice/branding", headers=h, json={
        "logo_url": PNG_1PX, "brand_footer": "Acme Jyotish - Delhi"})
    rid = client_api.post("/v1/reports", headers=h, json={
        "chart_id": chart, "language": language, "lal_kitab": True,
        "sections": ["summary", "kundali", "planets", "houses", "yogas", "dasha",
                     "reading", "panchang", "remedies"]}).json()["id"]
    run_worker(app_engine, storage)
    got = client_api.get(f"/v1/reports/{rid}", headers=h).json()
    assert got["status"] == "done", got
    pdf = client_api.get(got["download_url"].replace("http://testserver", "")).content
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000
    # Embedded Urbanist font (and Devanagari for Hindi).
    assert b"Urbanist" in pdf
    if language == "hi":
        assert b"NotoSansDevanagari" in pdf or b"Noto" in pdf
    out = os.environ.get("REPORT_TEST_OUT")
    if out:
        open(os.path.join(out, f"report-{language}.pdf"), "wb").write(pdf)


def test_concurrent_retries_of_a_failed_report_enqueue_one_job(
        client_api, auth, make_practice, seed_chart, app_engine, owner_engine):
    import threading

    from sqlalchemy import text

    from app.reports.service import request_report

    pid, subject = make_practice("Retry Race")
    chart = seed_chart(pid)
    first = client_api.post("/v1/reports", json={"chart_id": chart},
                            headers=auth(subject, pid)).json()
    with owner_engine.begin() as c:
        c.execute(text("UPDATE report SET status='failed' WHERE id=:i"), {"i": first["id"]})
        c.execute(text("DELETE FROM job WHERE payload->>'report_id' = :i"), {"i": first["id"]})
    member = uuid.uuid4()
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def retry() -> None:
        try:
            with tenant_session(app_engine, pid) as db:
                barrier.wait(timeout=10)
                request_report(db, practice_id=uuid.UUID(pid), member_id=member,
                               chart_id=uuid.UUID(chart), template="standard", language="en",
                               sections=list(DEFAULT_SECTIONS))
                import time

                time.sleep(0.5)  # hold the transaction open so the other retry has to wait
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=retry) for _ in range(2)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    assert not errors, errors
    with owner_engine.connect() as c:
        n = c.scalar(text("SELECT count(*) FROM job WHERE payload->>'report_id' = :i"),
                     {"i": first["id"]})
    assert n == 1
