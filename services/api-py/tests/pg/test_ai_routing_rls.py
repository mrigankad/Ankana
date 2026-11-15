"""AI connections and routing on real Postgres: RLS, key encryption, owner-only writes,
local-provider gating, presets, test endpoint and assistant fallback with per-provider usage."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from ankana_ai import MockProvider
from app.db import make_engine
from app.main import create_app

pytestmark = pytest.mark.pg

BIRTH = {
    "birth_date": "1995-03-15", "birth_time": "06:42", "time_source": "certificate",
    "place_label": "Varanasi, Uttar Pradesh, India", "latitude": 25.3176,
    "longitude": 82.9739, "timezone_name": "Asia/Kolkata",
}


def ready_chart(api, h, with_ai=False) -> tuple[str, str]:
    cid = api.post("/v1/clients", json={"display_name": "Ananya"}, headers=h).json()["client"]["id"]
    purposes = ["chart_compute", *(["ai_assistant"] if with_ai else [])]
    for purpose in purposes:
        assert api.post(f"/v1/clients/{cid}/consents", headers=h, json={
            "purpose": purpose, "notice_version": "v1", "notice_text": "I agree",
            "channel": "in_person"}).status_code == 201
    assert api.post(f"/v1/clients/{cid}/birth-records", json=BIRTH, headers=h).status_code == 201
    r = api.post(f"/v1/clients/{cid}/charts", json={}, headers=h)
    assert r.status_code == 201, r.text
    return cid, r.json()["chart"]["id"]


@pytest.fixture()
def ai_api(app_engine, stub) -> TestClient:
    app = create_app(engine=make_engine("sqlite://"), pg_engine=app_engine, verifier=stub,
                     ai_provider=MockProvider())
    return TestClient(app)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANKANA_SECRET_KEY", "pg-test-secret")
    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS", raising=False)
    try:
        import swisseph  # noqa: F401
    except ImportError:
        monkeypatch.setenv("ANKANA_EPHEMERIS", "astronomy")


@pytest.fixture()
def staff(api, auth, owner_engine):
    def _add(practice_id: str, role: str = "astrologer") -> dict:
        subject = f"{role}-{practice_id[:8]}"
        api.get("/v1/me", headers=auth(subject))
        with owner_engine.begin() as c:
            uid = c.scalar(text("SELECT id FROM user_account WHERE subject=:s"), {"s": subject})
            c.execute(text("INSERT INTO member (practice_id,user_id,role) VALUES (:p,:u,:r)"),
                      {"p": practice_id, "u": uid, "r": role})
        return auth(subject, practice_id)

    return _add


def mk(api, h, kind="ollama_cloud", label="Cloud", **extra):
    body = {"kind": kind, "label": label, **extra}
    if kind == "ollama_cloud":
        body.setdefault("api_key", "ollama-secret-key-123")
    return api.post("/v1/ai/connections", json=body, headers=h)


def test_create_encrypts_key_and_never_returns_it(api, auth, make_practice, owner_engine):
    pid, u = make_practice()
    h = auth(u)
    r = mk(api, h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_key"] is True and "api_key" not in body
    assert "ollama-secret-key-123" not in r.text
    assert body["effective_models"]["strong"] == "gpt-oss:20b"
    listed = api.get("/v1/ai/connections", headers=h)
    assert listed.status_code == 200 and "ollama-secret-key-123" not in listed.text
    with owner_engine.connect() as c:
        enc = c.scalar(text("SELECT api_key_enc FROM ai_connection WHERE practice_id=:p"), {"p": pid})
    assert enc.startswith("v1:") and "ollama-secret-key-123" not in enc
    # key can be replaced and removed, still write-only
    cid = body["id"]
    assert api.patch(f"/v1/ai/connections/{cid}", json={"api_key": ""}, headers=h).json()["has_key"] is False
    assert api.patch(f"/v1/ai/connections/{cid}", json={"api_key": "new"}, headers=h).json()["has_key"]


def test_validation(api, auth, make_practice, monkeypatch):
    _, u = make_practice()
    h = auth(u)
    assert api.post("/v1/ai/connections", json={"kind": "ollama_cloud", "label": "x"},
                    headers=h).status_code == 422  # key required
    assert api.post("/v1/ai/connections", json={"kind": "bogus", "label": "x"},
                    headers=h).json()["code"] == "unknown_provider_kind"
    bad = api.post("/v1/ai/connections", headers=h, json={
        "kind": "openai_compatible", "label": "lan", "base_url": "https://10.0.0.5/v1"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_base_url"
    assert mk(api, h, label="Dup").status_code == 201
    assert mk(api, h, label="Dup").status_code == 409
    monkeypatch.delenv("ANKANA_SECRET_KEY")
    r = mk(api, h, label="NoSecret")
    assert r.status_code == 503 and r.json()["code"] == "secret_key_missing"


def test_rls_isolates_connections_between_practices(api, auth, make_practice, app_engine):
    pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    ha, hb = auth(ua), auth(ub)
    cid = mk(api, ha, label="A only").json()["id"]
    assert api.get("/v1/ai/connections", headers=hb).json() == []
    assert api.patch(f"/v1/ai/connections/{cid}", json={"enabled": False}, headers=hb).status_code == 404
    assert api.delete(f"/v1/ai/connections/{cid}", headers=hb).status_code == 404
    assert api.post(f"/v1/ai/connections/{cid}/test", headers=hb).status_code == 404
    with app_engine.begin() as c:  # raw SQL as the app role: no practice bound sees nothing
        assert c.scalar(text("SELECT count(*) FROM ai_connection")) == 0
        c.execute(text("SELECT set_config('app.practice_id', :p, true)"), {"p": pb})
        assert c.scalar(text("SELECT count(*) FROM ai_connection")) == 0
        c.execute(text("SELECT set_config('app.practice_id', :p, true)"), {"p": pa})
        assert c.scalar(text("SELECT count(*) FROM ai_connection")) == 1


def test_only_owner_writes_staff_read(api, auth, make_practice, staff):
    pid, u = make_practice()
    ho = auth(u)
    cid = mk(api, ho).json()["id"]
    ha = staff(pid, "astrologer")
    assert api.get("/v1/ai/connections", headers=ha).status_code == 200
    assert api.get("/v1/ai/providers", headers=ha).status_code == 200
    assert api.get("/v1/ai/routing", headers=ha).status_code == 200
    assert mk(api, ha, label="x").status_code == 403
    assert api.patch(f"/v1/ai/connections/{cid}", json={"enabled": False}, headers=ha).status_code == 403
    assert api.delete(f"/v1/ai/connections/{cid}", headers=ha).status_code == 403
    assert api.post(f"/v1/ai/connections/{cid}/test", headers=ha).status_code == 403
    assert api.put("/v1/ai/routing", json={"routes": []}, headers=ha).status_code == 403
    assert api.post("/v1/ai/routing/preset", json={"preset": "balanced"}, headers=ha).status_code == 403
    assert api.get("/v1/ai/connections", headers=auth("nobody")).status_code == 403


def test_local_providers_gated(api, auth, make_practice, monkeypatch):
    _, u = make_practice()
    h = auth(u)
    for kind in ("claude_code", "codex", "gemini_cli", "ollama_local"):
        r = mk(api, h, kind, label=kind)
        assert r.status_code == 403 and r.json()["code"] == "local_provider_disabled"
    kinds = {k["kind"]: k for k in api.get("/v1/ai/providers", headers=h).json()["kinds"]}
    assert kinds["claude_code"]["status"] == "disabled" and not kinds["claude_code"]["allowed"]
    assert kinds["anthropic"]["status"] == "needs_key"
    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    assert mk(api, h, "claude_code", label="Claude").status_code == 201
    assert mk(api, h, "ollama_local", label="Ollama").status_code == 201
    on = {k["kind"]: k for k in api.get("/v1/ai/providers", headers=h).json()["kinds"]}
    assert on["claude_code"]["allowed"] and on["claude_code"]["status"] in ("ready", "not_installed")
    # turning the switch off again makes existing local connections unusable, not deleted
    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS")
    listed = api.get("/v1/ai/connections", headers=h).json()
    assert {c["kind"]: c["allowed"] for c in listed}["claude_code"] is False


def test_test_endpoint_reports_ok_and_errors_without_leaking_key(api, auth, make_practice, monkeypatch):
    _, u = make_practice()
    h = auth(u)
    mock = mk(api, h, "mock", label="Offline").json()["id"]
    ok = api.post(f"/v1/ai/connections/{mock}/test", headers=h).json()
    assert ok["ok"] is True and ok["latency_ms"] >= 0 and ok["error"] is None
    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    dead = mk(api, h, "ollama_local", label="Dead", base_url="http://127.0.0.1:9").json()["id"]
    bad = api.post(f"/v1/ai/connections/{dead}/test", headers=h).json()
    assert bad["ok"] is False and bad["error"]
    key = mk(api, h, "openai_compatible", label="Leaky", api_key="sk-leak-999",
             base_url="http://127.0.0.1:9/v1").json()["id"]
    bad = api.post(f"/v1/ai/connections/{key}/test", headers=h).json()
    assert bad["ok"] is False and "sk-leak-999" not in str(bad)


def test_routing_set_preset_and_cascade(api, auth, make_practice, owner_engine):
    pid, u = make_practice()
    h = auth(u)
    a = mk(api, h, label="Cloud").json()["id"]
    b = mk(api, h, "mock", label="Offline").json()["id"]
    empty = api.get("/v1/ai/routing", headers=h).json()
    assert empty["routes"] == [] and "lowest_cost" in empty["presets"]
    r = api.put("/v1/ai/routing", headers=h, json={"routes": [
        {"role": "synthesise", "connection_id": a, "model": "gpt-oss:120b"},
        {"role": "report", "connection_id": b}]})
    assert r.status_code == 200 and {x["role"] for x in r.json()["routes"]} == {"synthesise", "report"}
    assert api.put("/v1/ai/routing", headers=h, json={"routes": [
        {"role": "nonsense", "connection_id": a}]}).json()["code"] == "invalid_role"
    p = api.post("/v1/ai/routing/preset", json={"preset": "lowest_cost"}, headers=h).json()
    assert p["preset"] == "lowest_cost" and len(p["routes"]) == 4
    assert {x["connection_id"] for x in p["routes"]} == {a}  # cloud before mock
    assert api.post("/v1/ai/routing/preset", json={"preset": "local_only"}, headers=h).status_code == 409
    assert api.post("/v1/ai/routing/preset", json={"preset": "zzz"}, headers=h).status_code == 422
    assert api.delete(f"/v1/ai/connections/{a}", headers=h).status_code == 204
    assert api.get("/v1/ai/routing", headers=h).json()["routes"] == []  # routes cascade away
    with owner_engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM ai_routing WHERE practice_id=:p"), {"p": pid}) == 0


def test_ask_uses_routing_falls_back_and_counts_per_provider(
        api, auth, make_practice, owner_engine, monkeypatch):
    """Primary connection is unreachable; the next enabled one (offline sample) answers."""
    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    pid, u = make_practice()
    h = auth(u)
    cid, chart = ready_chart(api, h, with_ai=True)
    dead = mk(api, h, "ollama_local", label="Dead", base_url="http://127.0.0.1:9").json()["id"]
    mk(api, h, "mock", label="Offline")
    assert api.put("/v1/ai/routing", headers=h, json={"routes": [
        {"role": "synthesise", "connection_id": dead}]}).status_code == 200
    r = api.post(f"/v1/charts/{chart}/ask", json={"question": "Where is my Moon placed?"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["verification"]["status"] == "verified" and "Moon is in" in r.json()["answer"]
    with owner_engine.connect() as c:
        rows = dict(c.execute(text(
            "SELECT metric, value FROM usage_counter WHERE practice_id=:p"), {"p": pid}).all())
    assert rows["ai_asks"] == 1 and rows["ai_calls:mock"] >= 2 and rows["ai_tokens:mock"] > 0
    assert "ai_calls:ollama_local" not in rows  # failed calls are not metered as usage
    # disabling the offline connection leaves nothing usable: 502 from the dead one
    mock_id = next(c["id"] for c in api.get("/v1/ai/connections", headers=h).json()
                   if c["kind"] == "mock")
    api.patch(f"/v1/ai/connections/{mock_id}", json={"enabled": False}, headers=h)
    r = api.post(f"/v1/charts/{chart}/ask", json={"question": "Where is my Moon placed?"}, headers=h)
    assert r.status_code == 502 and r.json()["code"] == "ai_provider_error"


def test_hosted_mode_ignores_local_connections_and_uses_server_default(
        ai_api, api, auth, make_practice, owner_engine, monkeypatch):
    """A local connection created on a self-hosted box does nothing once the switch is off."""
    pid, u = make_practice()
    h = auth(u)
    cid, chart = ready_chart(ai_api, h, with_ai=True)
    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    mk(ai_api, h, "ollama_local", label="Dead", base_url="http://127.0.0.1:9")
    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS")
    r = ai_api.post(f"/v1/charts/{chart}/ask", json={"question": "Where is my Moon placed?"}, headers=h)
    assert r.status_code == 200  # server-default MockProvider answered
    with owner_engine.connect() as c:
        n = c.scalar(text("SELECT count(*) FROM usage_counter WHERE practice_id=:p "
                          "AND metric LIKE 'ai_calls:%'"), {"p": pid})
    assert n == 0


def test_ai_reading_job_resolves_routing(app_engine, api, auth, make_practice, owner_engine):
    from app.tenancy.models import Job
    from app.worker import ai_reading_job

    pid, u = make_practice()
    mk(api, auth(u), "mock", label="Offline")
    job = Job(kind="ai_reading", practice_id=pid)
    assert ai_reading_job(job, app_engine)["providers"] == ["mock"]
