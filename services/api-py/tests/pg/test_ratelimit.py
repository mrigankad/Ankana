"""Shared (Postgres) rate limiter: counts across processes, covers the public endpoints
(location search, reminder links), degrades to an in-process window if the store is down."""

import httpx
import pytest
from sqlalchemy import create_engine, text

from app import ratelimit
from app.ratelimit import SharedRateLimiter

pytestmark = pytest.mark.pg


@pytest.fixture(autouse=True)
def clean(owner_engine):
    ratelimit.clear(owner_engine)
    yield
    ratelimit.clear(owner_engine)


def test_two_replicas_share_one_budget(app_engine):
    a = SharedRateLimiter("t_shared", 5, 3600)  # separate instances = separate processes
    b = SharedRateLimiter("t_shared", 5, 3600)
    results = [a.allow(app_engine, "1.2.3.4") for _ in range(3)]
    results += [b.allow(app_engine, "1.2.3.4") for _ in range(3)]
    assert results == [True] * 5 + [False]
    assert a.allow(app_engine, "9.9.9.9")  # another caller is unaffected
    assert not b.check(app_engine, "1.2.3.4").allowed
    assert b.check(app_engine, "1.2.3.4").retry_after >= 1


def test_scopes_are_independent_and_keys_are_stored_hashed(app_engine, owner_engine):
    one, two = SharedRateLimiter("t_a", 1, 3600), SharedRateLimiter("t_b", 1, 3600)
    assert one.allow(app_engine, "ip") and not one.allow(app_engine, "ip")
    assert two.allow(app_engine, "ip")
    with owner_engine.connect() as c:
        keys = [r[0] for r in c.execute(text("SELECT key_hash FROM rate_limit_bucket"))]
    assert len(keys) == 2 and all(len(k) == 64 and "ip" not in k for k in keys)


def test_previous_window_still_counts_so_no_burst_at_the_edge(app_engine, owner_engine):
    lim = SharedRateLimiter("t_slide", 5, 3600)
    with owner_engine.begin() as c:  # the previous window was far over the limit
        c.execute(text(
            "INSERT INTO rate_limit_bucket (key_hash, window_start, hits) VALUES (:k, "
            "to_timestamp(floor(extract(epoch FROM now()) / 3600) * 3600) - interval '1 hour', "
            "1000)"), {"k": lim._hash("edge")})
    # the old window is weighted by the share of it still inside the last hour
    assert not lim.allow(app_engine, "edge")
    assert lim.allow(app_engine, "someone-else")


def test_falls_back_to_in_process_window_when_the_store_is_down():
    dead = create_engine("postgresql+psycopg://x:y@127.0.0.1:1/none",
                         connect_args={"connect_timeout": 1})
    lim = SharedRateLimiter("t_down", 3, 60)
    assert [lim.allow(dead, "k") for _ in range(5)] == [True, True, True, False, False]
    lim = SharedRateLimiter("t_none", 2, 60)
    assert [lim.allow(None, "k") for _ in range(3)] == [True, True, False]


def test_prune_removes_old_windows(app_engine, owner_engine):
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO rate_limit_bucket VALUES ('old', now() - interval '3 days', 4), "
                       "('new', now(), 1)"))
    assert ratelimit.prune(app_engine, 86400) == 1


def test_location_search_is_limited_and_available_at_v1(api, monkeypatch):
    from app import locations

    def down(*a, **k):
        raise httpx.ConnectError("offline in tests")

    monkeypatch.setattr(locations, "search_nominatim", down)
    codes = [api.get("/v1/locations/search", params={"q": "Varanasi"}).status_code
             for _ in range(33)]
    assert codes[:30] == [200] * 30 and codes[30:] == [429] * 3
    blocked = api.get("/v1/locations/search", params={"q": "Varanasi"})
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) >= 1
    # the legacy path is a second mount of the same router and shares the budget
    assert api.get("/api/v1/locations/search", params={"q": "Delhi"}).status_code == 429
    ok = api.get("/v1/locations/search", params={"q": "x" * 201})
    assert ok.status_code in (422, 429)


def test_location_search_returns_results_within_budget(api, monkeypatch):
    from app import locations

    monkeypatch.setattr(locations, "search_nominatim",
                        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("x")))
    r = api.get("/v1/locations/search", params={"q": "Varanasi"})
    assert r.status_code == 200 and r.json()["results"][0]["displayName"].startswith("Varanasi")


def test_proxy_header_only_trusted_when_configured(api):
    from types import SimpleNamespace

    def req(trust: bool, fwd: str | None):
        app = SimpleNamespace(state=SimpleNamespace(
            auth=SimpleNamespace(cfg=SimpleNamespace(trust_proxy=trust))))
        headers = {"x-forwarded-for": fwd} if fwd else {}
        return SimpleNamespace(app=app, headers=headers, client=SimpleNamespace(host="10.0.0.1"))

    assert ratelimit.client_ip(req(False, "6.6.6.6")) == "10.0.0.1"
    assert ratelimit.client_ip(req(True, "6.6.6.6, 7.7.7.7")) == "7.7.7.7"
    assert ratelimit.client_ip(req(True, None)) == "10.0.0.1"
