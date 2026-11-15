"""The unauthenticated legacy /api/v1 surface is off in production (security review)."""

import pytest
from fastapi.testclient import TestClient

from app.db import make_engine
from app.main import create_app

pytestmark = pytest.mark.pg

LEGACY = [("get", "/api/v1/clients"), ("get", "/api/v1/audit-events"),
          ("get", "/api/v1/dashboard/summary"), ("get", "/api/v1/panchang/today")]


def _client(app_engine, tmp_path, monkeypatch, env, flag=None):
    from app.auth.config import AuthConfig

    monkeypatch.setenv("API_ENV", env)
    if flag is None:
        monkeypatch.delenv("ANKANA_LEGACY_API", raising=False)
    else:
        monkeypatch.setenv("ANKANA_LEGACY_API", flag)
    cfg = AuthConfig(env=env, dev_key_path=str(tmp_path / "k.pem"),
                     signing_key_pem=None, cookie_secure=True)
    if env == "production":  # production refuses to mint a dev key
        from app.auth.keys import generate_pem

        cfg = AuthConfig(env=env, signing_key_pem=generate_pem(), cookie_secure=True)
    monkeypatch.setenv("AUTH_SMS", "none")
    monkeypatch.setenv("STORAGE_SIGNING_KEY", "test-signing-key-0123456789abcdef")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path / "s"))

    class Mailer:
        def send(self, message) -> None:
            pass

    return TestClient(create_app(engine=make_engine("sqlite://"), pg_engine=app_engine,
                                 auth_config=cfg, mailer=Mailer()))


def test_legacy_routes_are_404_in_production(app_engine, tmp_path, monkeypatch):
    c = _client(app_engine, tmp_path, monkeypatch, "production")
    for method, path in LEGACY:
        assert getattr(c, method)(path).status_code == 404, path
    assert c.post("/api/v1/charts/compute", json={}).status_code == 404
    assert c.get("/health").status_code == 200


def test_legacy_routes_stay_on_in_dev_and_can_be_forced_on(app_engine, tmp_path, monkeypatch):
    dev = _client(app_engine, tmp_path, monkeypatch, "dev")
    assert dev.get("/api/v1/clients").status_code == 200
    forced = _client(app_engine, tmp_path, monkeypatch, "production", flag="1")
    assert forced.get("/api/v1/clients").status_code == 200
