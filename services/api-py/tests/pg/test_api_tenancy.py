"""End to end through FastAPI: JWT auth, role checks, tenant isolation."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg


def test_requires_token(api) -> None:
    assert api.get("/v1/clients").status_code == 401
    assert api.get("/v1/clients", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_token_from_another_issuer_is_rejected(api) -> None:
    from app.auth import StubIssuer

    other = StubIssuer()  # different keypair, same claims
    token = other.issue("mallory")
    assert api.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_cross_practice_isolation_over_http(api, auth, make_practice) -> None:
    _pa, ua = make_practice("A")
    pb, ub = make_practice("B")
    ra = api.post("/v1/clients", json={"display_name": "Alice"}, headers=auth(ua))
    rb = api.post("/v1/clients", json={"display_name": "Bob"}, headers=auth(ub))
    assert ra.status_code == rb.status_code == 201
    cid_a, cid_b = ra.json()["client"]["id"], rb.json()["client"]["id"]

    names = [c["display_name"] for c in api.get("/v1/clients", headers=auth(ua)).json()["clients"]]
    assert names == ["Alice"]
    assert api.get(f"/v1/clients/{cid_b}", headers=auth(ua)).status_code == 404
    assert api.get(f"/v1/clients/{cid_a}", headers=auth(ua)).status_code == 200
    assert api.delete(f"/v1/clients/{cid_b}", headers=auth(ua)).status_code == 404
    assert api.get(f"/v1/clients/{cid_b}", headers=auth(ub)).status_code == 200
    # Naming someone else's practice is a 403, not a silent switch.
    assert api.get("/v1/clients", headers=auth(ua, pb)).status_code == 403


def test_me_lists_memberships_and_requires_practice_header_when_ambiguous(
    api, auth, make_practice
) -> None:
    p1, user = make_practice("One")
    p2 = api.post("/v1/practices", json={"name": "Two"}, headers=auth(user)).json()["practice_id"]
    me = api.get("/v1/me", headers=auth(user)).json()
    assert {m["practice_id"] for m in me["memberships"]} == {p1, p2}
    assert api.get("/v1/clients", headers=auth(user)).status_code == 400
    assert api.get("/v1/clients", headers=auth(user, p2)).status_code == 200


def test_user_without_practice_is_forbidden(api, auth) -> None:
    assert api.get("/v1/clients", headers=auth("nobody-yet")).status_code == 403


def test_role_checks(api, auth, make_practice, owner_engine) -> None:
    pid, owner = make_practice("Roles")
    cid = api.post("/v1/clients", json={"display_name": "C"},
                   headers=auth(owner)).json()["client"]["id"]
    # Add members as the DB owner: an assistant and a client-portal user.
    for subject, role, client_id in (("asst", "assistant", None), ("portal", "client", cid)):
        api.get("/v1/me", headers=auth(subject))  # provisions user_account
        with owner_engine.begin() as c:
            uid = c.scalar(text("SELECT id FROM user_account WHERE subject=:s"), {"s": subject})
            c.execute(text("INSERT INTO member (practice_id,user_id,role,client_id) "
                           "VALUES (:p,:u,:r,:c)"),
                      {"p": pid, "u": uid, "r": role, "c": client_id})
    assert api.post("/v1/clients", json={"display_name": "By assistant"},
                    headers=auth("asst")).status_code == 201
    assert api.delete(f"/v1/clients/{cid}", headers=auth("asst")).status_code == 403
    assert api.get("/v1/clients", headers=auth("portal")).status_code == 403
    assert api.get(f"/v1/clients/{cid}", headers=auth("portal")).status_code == 200
    other = api.post("/v1/clients", json={"display_name": "Other"},
                     headers=auth(owner)).json()["client"]["id"]
    assert api.get(f"/v1/clients/{other}", headers=auth("portal")).status_code == 404
    assert api.delete(f"/v1/clients/{cid}", headers=auth(owner)).status_code == 204
    assert api.get(f"/v1/clients/{cid}", headers=auth(owner)).status_code == 404


def test_dev_token_endpoint_with_stub(api) -> None:
    r = api.post("/v1/dev/token", json={"subject": "dev1"})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert api.get("/v1/me", headers=h).status_code == 200


def test_audit_written_in_same_tenant(api, auth, make_practice, owner_engine) -> None:
    pid, user = make_practice("Audit")
    api.post("/v1/clients", json={"display_name": "X"}, headers=auth(user))
    with owner_engine.connect() as c:
        actions = [r[0] for r in c.execute(
            text("SELECT action FROM audit_event WHERE practice_id=:p ORDER BY created_at"),
            {"p": pid})]
    assert actions == ["practice.created", "client.created"]
