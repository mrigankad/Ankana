"""Guards for the hotspots found in the load test (docs/performance.md)."""

import pytest
from sqlalchemy import event

pytestmark = pytest.mark.pg


def _count_checkouts(engine):
    box = {"n": 0}

    def on_checkout(*_a):
        box["n"] += 1

    event.listen(engine, "checkout", on_checkout)
    return box, lambda: event.remove(engine, "checkout", on_checkout)


def test_an_authenticated_read_takes_two_pool_checkouts_not_three(api, auth, make_practice,
                                                                  app_engine):
    """User lookup and memberships share one transaction; the request itself is the second
    (tenant) session. Every checkout costs a ping, BEGIN and COMMIT round trip."""
    pid, subject = make_practice("Perf Co")
    h = auth(subject, pid)
    api.get("/v1/clients", headers=h)  # warm up: first request creates nothing new
    box, off = _count_checkouts(app_engine)
    try:
        r = api.get("/v1/clients", headers=h)
    finally:
        off()
    assert r.status_code == 200 and box["n"] == 2, box


def test_memberships_are_not_reread_when_the_request_already_has_them(api, auth, make_practice,
                                                                      app_engine):
    pid, subject = make_practice("Perf Co 2")
    h = auth(subject, pid)
    seen = []

    def spy(conn, cursor, statement, *a):
        if "app_memberships" in statement:
            seen.append(statement)

    event.listen(app_engine, "before_cursor_execute", spy)
    try:
        assert api.get("/v1/clients", headers=h).status_code == 200
    finally:
        event.remove(app_engine, "before_cursor_execute", spy)
    assert len(seen) == 1


