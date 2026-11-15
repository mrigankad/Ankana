"""Built-in authentication end to end on real Postgres (RLS-bound app role)."""

import base64
import dataclasses
import hashlib
import re
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.config import AuthConfig, OidcProvider
from app.db import make_engine
from app.main import create_app

pytestmark = pytest.mark.pg

ORIGIN = "http://localhost:3000"
CSRF = {"Origin": ORIGIN, "X-Ankana-Csrf": "1"}
BODY = {"X-Auth-Transport": "body"}
STRONG = "correct horse battery staple"


class MemoryMailer:
    def __init__(self) -> None:
        self.sent: list = []

    def send(self, message) -> None:
        self.sent.append(message)

    def code_for(self, email: str) -> str:
        msgs = [m for m in self.sent if m.to == email and "sign-in code" in m.subject]
        return re.search(r"\b(\d{6})\b", msgs[-1].text).group(1)

    def invite_token(self, email: str) -> str:
        msgs = [m for m in self.sent if m.to == email and "invited" in m.subject]
        return re.search(r"/invite/([\w-]+)", msgs[-1].text).group(1)


class MemorySms:
    def __init__(self) -> None:
        self.sent: list = []

    def send(self, to: str, text_: str) -> None:
        self.sent.append((to, text_))


# ---------------------------------------------------------------- fake IdP
class FakeIdp:
    ISSUER = "https://idp.example.test"

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims = {"sub": "idp-user-1", "email": "oidc.person@example.test",
                       "email_verified": True, "name": "Oidc Person"}
        self.nonce_override: str | None = None
        self.last_nonce: str | None = None
        self.last_form: dict = {}

    def jwks(self) -> dict:
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        return {"keys": [{**jwk, "kid": "k1", "use": "sig", "alg": "RS256"}]}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={
                "issuer": self.ISSUER, "authorization_endpoint": f"{self.ISSUER}/authorize",
                "token_endpoint": f"{self.ISSUER}/token", "jwks_uri": f"{self.ISSUER}/jwks"})
        if path == "/jwks":
            return httpx.Response(200, json=self.jwks())
        if path == "/token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            self.last_form = form
            now = int(time.time())
            claims = {"iss": self.ISSUER, "aud": "client-123", "iat": now, "exp": now + 300,
                      "nonce": self.nonce_override or self.last_nonce, **self.claims}
            token = jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "k1"})
            return httpx.Response(200, json={"id_token": token, "access_token": "x"})
        return httpx.Response(404)


# ---------------------------------------------------------------- fixtures
@pytest.fixture()
def idp() -> FakeIdp:
    return FakeIdp()


@pytest.fixture()
def mailer() -> MemoryMailer:
    return MemoryMailer()


@pytest.fixture()
def sms() -> MemorySms:
    return MemorySms()


@pytest.fixture()
def make_app(app_engine, mailer, sms, idp, tmp_path):
    def _make(**overrides) -> TestClient:
        cfg = AuthConfig(
            env="test", issuer_url="http://ankana.test", web_base_url=ORIGIN,
            allowed_origins=(ORIGIN,), dev_key_path=str(tmp_path / "key.pem"),
            otp_resend_seconds=0, trust_proxy=True,
            oidc=(OidcProvider("keycloak", "Keycloak", idp.ISSUER, "client-123", "secret"),))
        cfg = dataclasses.replace(cfg, **overrides)
        app = create_app(engine=make_engine("sqlite://"), pg_engine=app_engine, auth_config=cfg,
                         mailer=mailer, oidc_http=httpx.Client(transport=httpx.MockTransport(idp.handler)))
        app.state.auth.sms = sms
        c = TestClient(app, headers={"X-Forwarded-For": f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.9"})
        return c

    return _make


@pytest.fixture()
def api(make_app):
    return make_app()


def email_() -> str:
    return f"u{uuid.uuid4().hex[:10]}@example.test"


def bearer(token: str, practice: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if practice:
        h["X-Practice-Id"] = practice
    return h


def signup(api, mailer, email=None, name="Asha Rao", practice="Asha Jyotish", transport=BODY):
    email = email or email_()
    r = api.post("/v1/auth/signup", json={"email": email, "name": name, "practice_name": practice})
    assert r.status_code == 202, r.text
    r = api.post("/v1/auth/otp/verify", json={"email": email, "code": mailer.code_for(email)},
                 headers=transport)
    assert r.status_code == 200, r.text
    return email, r.json()


def sign_in(api, mailer, email, transport=BODY):
    assert api.post("/v1/auth/otp/request", json={"email": email}).status_code == 202
    r = api.post("/v1/auth/otp/verify", json={"email": email, "code": mailer.code_for(email)},
                 headers=transport)
    assert r.status_code == 200, r.text
    return r.json()


def events(owner_engine, action, email=None):
    with owner_engine.connect() as c:
        return c.scalar(text("SELECT count(*) FROM auth_event WHERE action = :a"), {"a": action})


# ------------------------------------------------------------------- tests
def test_jwks_and_discovery_let_an_external_verifier_trust_ankana(api, mailer) -> None:
    disco = api.get("/.well-known/openid-configuration").json()
    assert disco["issuer"] == "http://ankana.test"
    jwks = api.get("/.well-known/jwks.json").json()
    assert jwks["keys"][0]["kty"] == "OKP" and jwks["keys"][0]["crv"] == "Ed25519"
    _, session = signup(api, mailer)
    key = jwt.PyJWKSet.from_dict(jwks).keys[0].key
    claims = jwt.decode(session["access_token"], key, algorithms=["EdDSA"],
                        audience="ankana-api", issuer="http://ankana.test")
    assert claims["email"] == session["user"]["email"] and claims["sid"] == session["session_id"]


def test_signup_creates_owner_practice_and_token_works_on_v1(api, mailer) -> None:
    email, s = signup(api, mailer, name="Meera", practice="Meera Jyotish")
    assert s["memberships"][0]["role"] == "owner"
    assert s["memberships"][0]["practice_name"] == "Meera Jyotish"
    assert s["active_practice_id"] == s["memberships"][0]["practice_id"]
    h = bearer(s["access_token"])
    assert api.get("/v1/me", headers=h).json()["memberships"][0]["role"] == "owner"
    assert api.post("/v1/clients", json={"display_name": "C1"}, headers=h).status_code == 201


def test_browser_transport_sets_httponly_cookie_and_hides_refresh_token(api, mailer) -> None:
    email = email_()
    api.post("/v1/auth/signup", json={"email": email, "name": "A", "practice_name": "P"})
    r = api.post("/v1/auth/otp/verify", json={"email": email, "code": mailer.code_for(email)},
                 headers={"Origin": ORIGIN})
    assert r.status_code == 200 and "refresh_token" not in r.json()
    cookie = r.headers["set-cookie"].lower()
    assert "ankana_rt=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert "path=/v1/auth" in cookie
    assert r.headers["cache-control"] == "no-store"


def test_otp_for_unknown_email_is_silent_and_verify_is_generic(api, mailer) -> None:
    ghost = email_()
    r = api.post("/v1/auth/otp/request", json={"email": ghost})
    assert r.status_code == 202 and not [m for m in mailer.sent if m.to == ghost]
    r = api.post("/v1/auth/otp/verify", json={"email": ghost, "code": "123456"})
    assert r.status_code == 400 and r.json()["code"] == "invalid_code"


def test_otp_is_single_use_and_stored_hashed(api, mailer, owner_engine) -> None:
    email, _ = signup(api, mailer)
    api.post("/v1/auth/otp/request", json={"email": email})
    code = mailer.code_for(email)
    with owner_engine.connect() as c:
        stored = c.scalar(text("SELECT code_hash FROM auth_otp WHERE destination = :e "
                               "ORDER BY created_at DESC LIMIT 1"), {"e": email})
    assert code not in stored and len(stored) == 64
    assert api.post("/v1/auth/otp/verify", json={"email": email, "code": code}).status_code == 200
    again = api.post("/v1/auth/otp/verify", json={"email": email, "code": code})
    assert again.status_code == 400


def test_otp_expires(api, mailer, owner_engine) -> None:
    email, _ = signup(api, mailer)
    api.post("/v1/auth/otp/request", json={"email": email})
    code = mailer.code_for(email)
    with owner_engine.begin() as c:
        c.execute(text("UPDATE auth_otp SET expires_at = now() - interval '1 minute' "
                       "WHERE destination = :e"), {"e": email})
    assert api.post("/v1/auth/otp/verify", json={"email": email, "code": code}).status_code == 400


def test_otp_attempt_counter_burns_the_code(api, mailer) -> None:
    email, _ = signup(api, mailer)
    api.post("/v1/auth/otp/request", json={"email": email})
    good = mailer.code_for(email)
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(5):
        assert api.post("/v1/auth/otp/verify", json={"email": email, "code": wrong}).status_code == 400
    # The right code no longer works once the attempts are spent.
    assert api.post("/v1/auth/otp/verify", json={"email": email, "code": good}).status_code == 400


def test_resend_cooldown_and_new_code_invalidates_old(make_app, mailer) -> None:
    api = make_app(otp_resend_seconds=30)
    email, _ = signup(api, mailer)
    # signup just sent a code, so asking again right away is refused
    assert api.post("/v1/auth/otp/request", json={"email": email}).status_code == 429
    api2 = make_app()
    api2.post("/v1/auth/otp/request", json={"email": email})
    first = mailer.code_for(email)
    api2.post("/v1/auth/otp/request", json={"email": email})
    second = mailer.code_for(email)
    if first != second:
        assert api2.post("/v1/auth/otp/verify", json={"email": email, "code": first}).status_code == 400
    assert api2.post("/v1/auth/otp/verify", json={"email": email, "code": second}).status_code == 200


def test_rate_limit_code_requests_per_email_and_per_ip(make_app, mailer) -> None:
    api = make_app(otp_requests_per_email_hour=3, otp_requests_per_ip_hour=5)
    email, _ = signup(api, mailer)  # request 1
    assert api.post("/v1/auth/otp/request", json={"email": email}).status_code == 202  # 2
    assert api.post("/v1/auth/otp/request", json={"email": email}).status_code == 202  # 3
    r = api.post("/v1/auth/otp/request", json={"email": email})
    assert r.status_code == 429 and "retry-after" in r.headers
    # a different address from the same IP hits the IP ceiling (5 total)
    for _ in range(2):
        assert api.post("/v1/auth/otp/request", json={"email": email_()}).status_code == 202
    assert api.post("/v1/auth/otp/request", json={"email": email_()}).status_code == 429


def test_failed_attempt_limits_lock_per_email_and_per_ip(make_app, mailer, owner_engine) -> None:
    api = make_app(failures_per_email_window=3, failures_per_ip_window=6)
    email, _ = signup(api, mailer)
    for _ in range(3):
        assert api.post("/v1/auth/otp/verify", json={"email": email, "code": "000000"}).status_code == 400
    r = api.post("/v1/auth/otp/verify", json={"email": email, "code": "000000"})
    assert r.status_code == 429
    assert events(owner_engine, "signin.failed") >= 3 and events(owner_engine, "signin.blocked") >= 1
    # other emails from the same IP are blocked once the IP ceiling is reached
    for _ in range(3):
        api.post("/v1/auth/otp/verify", json={"email": email_(), "code": "000000"})
    assert api.post("/v1/auth/otp/verify",
                    json={"email": email_(), "code": "000000"}).status_code == 429


def test_password_flow_and_policy(api, mailer) -> None:
    email, s = signup(api, mailer)
    h = bearer(s["access_token"])
    short = api.put("/v1/auth/password", json={"new_password": "short"}, headers=h)
    assert short.status_code == 422 and short.json()["code"] == "weak_password"
    common = api.put("/v1/auth/password", json={"new_password": "password123"}, headers=h)
    assert common.status_code == 422
    # no complexity theatre: a plain long phrase is fine
    assert api.put("/v1/auth/password", json={"new_password": STRONG}, headers=h).status_code == 204
    ok = api.post("/v1/auth/password/signin", json={"email": email, "password": STRONG}, headers=BODY)
    assert ok.status_code == 200 and ok.json()["memberships"]
    bad = api.post("/v1/auth/password/signin", json={"email": email, "password": "wrong wrong wrong"})
    nope = api.post("/v1/auth/password/signin", json={"email": email_(), "password": "wrong wrong wrong"})
    assert bad.status_code == nope.status_code == 401
    assert bad.json()["detail"] == nope.json()["detail"]  # no account enumeration


def test_changing_password_requires_current_and_signs_out_other_devices(api, mailer) -> None:
    email, first = signup(api, mailer)
    h1 = bearer(first["access_token"])
    api.put("/v1/auth/password", json={"new_password": STRONG}, headers=h1)
    second = sign_in(api, mailer, email)
    h2 = bearer(second["access_token"])
    assert api.put("/v1/auth/password", json={"new_password": "another long phrase here"},
                   headers=h2).status_code == 403
    r = api.put("/v1/auth/password", json={"new_password": "another long phrase here",
                                           "current_password": STRONG}, headers=h2)
    assert r.status_code == 204
    assert api.get("/v1/me", headers=h1).status_code == 401  # other device is out
    assert api.get("/v1/me", headers=h2).status_code == 200


def test_refresh_rotates_and_reuse_revokes_the_session(api, mailer, owner_engine) -> None:
    _, s = signup(api, mailer)
    rt1 = s["refresh_token"]
    r = api.post("/v1/auth/refresh", json={"refresh_token": rt1})
    assert r.status_code == 200
    rt2 = r.json()["refresh_token"]
    assert rt2 != rt1 and r.json()["access_token"]
    # replaying the old token is theft: it fails and kills the whole session
    assert api.post("/v1/auth/refresh", json={"refresh_token": rt1}).status_code == 401
    assert api.post("/v1/auth/refresh", json={"refresh_token": rt2}).status_code == 401
    assert events(owner_engine, "refresh.reuse_detected") >= 1
    assert api.get("/v1/me", headers=bearer(r.json()["access_token"])).status_code == 401


def test_refresh_tokens_are_hashed_at_rest(api, mailer, owner_engine) -> None:
    _, s = signup(api, mailer)
    secret = s["refresh_token"].split(".", 1)[1]
    with owner_engine.connect() as c:
        h = c.scalar(text("SELECT refresh_hash FROM auth_session WHERE id = :i"),
                     {"i": s["session_id"]})
    assert h == hashlib.sha256(secret.encode()).hexdigest() and secret not in h


def test_expired_session_cannot_refresh(api, mailer, owner_engine) -> None:
    _, s = signup(api, mailer)
    with owner_engine.begin() as c:
        c.execute(text("UPDATE auth_session SET expires_at = now() - interval '1 day' "
                       "WHERE id = :i"), {"i": s["session_id"]})
    assert api.post("/v1/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401


def test_cookie_refresh_requires_origin_and_csrf_header(api, mailer) -> None:
    email = email_()
    api.post("/v1/auth/signup", json={"email": email, "name": "A", "practice_name": "P"})
    api.post("/v1/auth/otp/verify", json={"email": email, "code": mailer.code_for(email)},
             headers={"Origin": ORIGIN})
    assert api.cookies.get("ankana_rt")
    # no Origin, wrong Origin, or missing custom header: refused, cookie untouched
    assert api.post("/v1/auth/refresh").status_code == 403
    assert api.post("/v1/auth/refresh", headers={"Origin": "https://evil.test",
                                                 "X-Ankana-Csrf": "1"}).status_code == 403
    assert api.post("/v1/auth/refresh", headers={"Origin": ORIGIN}).status_code == 403
    ok = api.post("/v1/auth/refresh", headers=CSRF)
    assert ok.status_code == 200 and ok.json()["access_token"] and "refresh_token" not in ok.json()
    assert api.post("/v1/auth/signout", headers={"Origin": ORIGIN}).status_code == 403
    assert api.post("/v1/auth/signout", headers=CSRF).status_code == 204
    assert api.post("/v1/auth/refresh", headers=CSRF).status_code == 401


def test_cross_origin_signin_is_refused(api, mailer) -> None:
    r = api.post("/v1/auth/otp/request", json={"email": email_()},
                 headers={"Origin": "https://evil.test"})
    assert r.status_code == 403 and r.json()["code"] == "csrf_origin"


def test_signout_revokes_access_token_immediately(api, mailer) -> None:
    _, s = signup(api, mailer)
    h = bearer(s["access_token"])
    assert api.get("/v1/me", headers=h).status_code == 200
    assert api.post("/v1/auth/signout", json={"refresh_token": s["refresh_token"]}).status_code == 204
    assert api.get("/v1/me", headers=h).status_code == 401
    assert api.post("/v1/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401


def test_list_and_revoke_sessions(api, mailer) -> None:
    email, a = signup(api, mailer)
    b = sign_in(api, mailer, email)
    ha = bearer(a["access_token"])
    listed = api.get("/v1/auth/sessions", headers=ha).json()["sessions"]
    assert {x["id"] for x in listed} == {a["session_id"], b["session_id"]}
    assert [x["id"] for x in listed if x["current"]] == [a["session_id"]]
    assert api.delete(f"/v1/auth/sessions/{b['session_id']}", headers=ha).status_code == 204
    assert api.get("/v1/me", headers=bearer(b["access_token"])).status_code == 401
    c = sign_in(api, mailer, email)
    assert api.delete("/v1/auth/sessions", headers=ha).json()["revoked"] == 1
    assert api.get("/v1/me", headers=bearer(c["access_token"])).status_code == 401
    assert api.get("/v1/me", headers=ha).status_code == 200
    # cannot revoke someone else's session
    _, other = signup(api, mailer)
    assert api.delete(f"/v1/auth/sessions/{other['session_id']}", headers=ha).status_code == 404


def test_config_reports_enabled_methods(api, make_app) -> None:
    cfg = api.get("/v1/auth/config").json()
    assert cfg["oidc"] == [{"id": "keycloak", "label": "Keycloak"}] and cfg["password"]
    off = make_app(oidc=(), password_enabled=False, signup_enabled=False).get("/v1/auth/config").json()
    assert off["oidc"] == [] and not off["password"] and not off["signup"]


def test_signup_closed(make_app, mailer) -> None:
    api = make_app(signup_enabled=False)
    r = api.post("/v1/auth/signup", json={"email": email_(), "name": "A", "practice_name": "P"})
    assert r.status_code == 403 and r.json()["code"] == "signup_disabled"


def test_signup_with_existing_email_just_signs_in_without_a_second_practice(api, mailer) -> None:
    email, first = signup(api, mailer)
    api.post("/v1/auth/signup", json={"email": email, "name": "X", "practice_name": "Second"})
    r = api.post("/v1/auth/otp/verify", json={"email": email, "code": mailer.code_for(email)},
                 headers=BODY)
    assert r.status_code == 200 and len(r.json()["memberships"]) == 1


# ------------------------------------------------------------------ team
def make_team(api, mailer):
    owner_email, o = signup(api, mailer, practice="Team Practice")
    pid = o["memberships"][0]["practice_id"]
    return owner_email, o, pid


def invite(api, mailer, o, pid, email, role="assistant", client_id=None):
    body = {"email": email, "role": role}
    if client_id:
        body["client_id"] = client_id
    return api.post("/v1/practice/invites", json=body, headers=bearer(o["access_token"], pid))


def test_invite_accept_flow_and_audit(api, mailer, owner_engine) -> None:
    _, o, pid = make_team(api, mailer)
    mate = email_()
    r = invite(api, mailer, o, pid, mate, "assistant")
    assert r.status_code == 201, r.text
    token = mailer.invite_token(mate)
    preview = api.get(f"/v1/auth/invites/{token}").json()
    assert preview["practice_name"] == "Team Practice" and preview["role"] == "assistant"
    # the invitee proves control of the address with a code, then accepts
    _, s = signup(api, mailer, email=mate, practice="Throwaway")
    # (signup above made them an owner of their own practice; accept adds the second)
    acc = api.post(f"/v1/auth/invites/{token}/accept", headers=bearer(s["access_token"]))
    assert acc.status_code == 200 and acc.json()["role"] == "assistant"
    assert api.post(f"/v1/auth/invites/{token}/accept",
                    headers=bearer(s["access_token"])).status_code == 410
    h = bearer(s["access_token"], pid)
    assert api.get("/v1/clients", headers=h).status_code == 200
    assert api.post("/v1/practice/invites", json={"email": email_(), "role": "assistant"},
                    headers=h).status_code == 403  # assistants cannot invite
    members = api.get("/v1/practice/members", headers=bearer(o["access_token"], pid)).json()["members"]
    assert {m["role"] for m in members} == {"owner", "assistant"}
    with owner_engine.connect() as c:
        actions = {r[0] for r in c.execute(text(
            "SELECT action FROM audit_event WHERE practice_id = :p"), {"p": pid})}
    assert {"invite.created", "invite.accepted", "practice.created"} <= actions


def test_invite_for_a_brand_new_person_needs_no_practice_of_their_own(api, mailer) -> None:
    _, o, pid = make_team(api, mailer)
    mate = email_()
    invite(api, mailer, o, pid, mate, "astrologer")
    token = mailer.invite_token(mate)
    # plain sign-in for an unknown address stays silent (no enumeration)
    api.post("/v1/auth/otp/request", json={"email": mate})
    assert not [m for m in mailer.sent if m.to == mate and "sign-in code" in m.subject]
    # the invite page uses sign-up without a practice name
    api.post("/v1/auth/signup", json={"email": mate, "name": "New Mate"})
    s = api.post("/v1/auth/otp/verify", json={"email": mate, "code": mailer.code_for(mate)},
                 headers=BODY).json()
    assert s["memberships"] == []
    acc = api.post(f"/v1/auth/invites/{token}/accept", headers=bearer(s["access_token"]))
    assert acc.json()["role"] == "astrologer"
    assert api.get("/v1/auth/session", headers=bearer(s["access_token"])).json()["active_practice_id"] == pid


def test_invite_only_works_for_the_invited_email(api, mailer) -> None:
    _, o, pid = make_team(api, mailer)
    mate = email_()
    invite(api, mailer, o, pid, mate)
    token = mailer.invite_token(mate)
    _, stranger = signup(api, mailer)
    r = api.post(f"/v1/auth/invites/{token}/accept", headers=bearer(stranger["access_token"]))
    assert r.status_code == 403 and r.json()["code"] == "invite_wrong_user"
    assert api.get("/v1/auth/invites/not-a-token").status_code == 404


def test_invite_expiry_and_revoke(api, mailer, owner_engine) -> None:
    _, o, pid = make_team(api, mailer)
    a, b = email_(), email_()
    invite(api, mailer, o, pid, a)
    invite(api, mailer, o, pid, b)
    ta, tb = mailer.invite_token(a), mailer.invite_token(b)
    with owner_engine.begin() as c:
        c.execute(text("UPDATE practice_invite SET expires_at = now() - interval '1 day' "
                       "WHERE email = :e"), {"e": a})
    assert api.get(f"/v1/auth/invites/{ta}").status_code == 410
    pending = api.get("/v1/practice/invites", headers=bearer(o["access_token"], pid)).json()["invites"]
    assert [p["email"] for p in pending] == [b]
    assert api.delete(f"/v1/practice/invites/{pending[0]['id']}",
                      headers=bearer(o["access_token"], pid)).status_code == 204
    assert api.get(f"/v1/auth/invites/{tb}").status_code == 410


def test_reinviting_replaces_the_old_link(api, mailer) -> None:
    _, o, pid = make_team(api, mailer)
    mate = email_()
    invite(api, mailer, o, pid, mate)
    old = mailer.invite_token(mate)
    invite(api, mailer, o, pid, mate, "astrologer")
    assert api.get(f"/v1/auth/invites/{old}").status_code == 410
    assert api.get(f"/v1/auth/invites/{mailer.invite_token(mate)}").json()["role"] == "astrologer"


def test_role_change_and_last_owner_guard(api, mailer, owner_engine) -> None:
    owner_email, o, pid = make_team(api, mailer)
    h = bearer(o["access_token"], pid)
    mate = email_()
    invite(api, mailer, o, pid, mate)
    _, s = signup(api, mailer, email=mate, practice="Own")
    api.post(f"/v1/auth/invites/{mailer.invite_token(mate)}/accept", headers=bearer(s["access_token"]))
    members = api.get("/v1/practice/members", headers=h).json()["members"]
    mid = next(m["member_id"] for m in members if m["email"] == mate)
    own = next(m["member_id"] for m in members if m["email"] == owner_email)
    r = api.patch(f"/v1/practice/members/{mid}", json={"role": "astrologer"}, headers=h)
    assert r.status_code == 200 and r.json()["role"] == "astrologer"
    assert api.patch(f"/v1/practice/members/{own}", json={"role": "assistant"},
                     headers=h).status_code == 409
    assert api.delete(f"/v1/practice/members/{own}", headers=h).status_code == 409
    assert api.patch(f"/v1/practice/members/{mid}", json={"role": "client"},
                     headers=h).status_code == 422
    assert api.delete(f"/v1/practice/members/{mid}", headers=h).status_code == 204
    # removed member loses access immediately
    assert api.get("/v1/clients", headers=bearer(s["access_token"], pid)).status_code == 403
    with owner_engine.connect() as c:
        meta = c.scalar(text("SELECT meta FROM audit_event WHERE action = 'member.role_changed' "
                             "AND practice_id = :p"), {"p": pid})
        assert meta == {"from": "assistant", "to": "astrologer"}
        assert c.scalar(text("SELECT count(*) FROM audit_event WHERE action = 'member.removed'")) >= 1


def test_client_portal_invite_is_scoped_to_one_client(api, mailer) -> None:
    _, o, pid = make_team(api, mailer)
    oh = bearer(o["access_token"], pid)
    mine = api.post("/v1/clients", json={"display_name": "Portal Person"}, headers=oh).json()["client"]["id"]
    other = api.post("/v1/clients", json={"display_name": "Someone Else"}, headers=oh).json()["client"]["id"]
    # client role without a client_id, or a client_id on staff, is refused
    assert invite(api, mailer, o, pid, email_(), "client").status_code == 422
    assert invite(api, mailer, o, pid, email_(), "assistant", mine).status_code == 422
    assert invite(api, mailer, o, pid, email_(), "client", str(uuid.uuid4())).status_code == 404
    portal = email_()
    assert invite(api, mailer, o, pid, portal, "client", mine).status_code == 201
    _, s = signup(api, mailer, email=portal, practice="Whatever")
    acc = api.post(f"/v1/auth/invites/{mailer.invite_token(portal)}/accept",
                   headers=bearer(s["access_token"]))
    assert acc.json()["role"] == "client"
    ph = bearer(s["access_token"], pid)
    assert api.get(f"/v1/clients/{mine}", headers=ph).status_code == 200
    assert api.get(f"/v1/clients/{other}", headers=ph).status_code == 404
    assert api.post("/v1/practice/invites", json={"email": email_(), "role": "assistant"},
                    headers=ph).status_code == 403


def test_switch_practice_is_remembered_on_the_session(api, mailer) -> None:
    _, o, p1 = make_team(api, mailer)
    mate = email_()
    invite(api, mailer, o, p1, mate)
    _, s = signup(api, mailer, email=mate, practice="Second Practice")
    api.post(f"/v1/auth/invites/{mailer.invite_token(mate)}/accept", headers=bearer(s["access_token"]))
    h = bearer(s["access_token"])
    memberships = api.get("/v1/me", headers=h).json()["memberships"]
    assert len(memberships) == 2
    p2 = next(m["practice_id"] for m in memberships if m["practice_id"] != p1)
    # accept already switched the session to the invited practice
    assert api.get("/v1/clients", headers=h).status_code == 200
    sw = api.post("/v1/auth/switch-practice", json={"practice_id": p2}, headers=h)
    assert sw.status_code == 200 and sw.json()["role"] == "owner"
    assert api.get("/v1/auth/session", headers=h).json()["active_practice_id"] == p2
    assert api.post("/v1/auth/switch-practice", json={"practice_id": str(uuid.uuid4())},
                    headers=h).status_code == 403
    # an explicit X-Practice-Id still wins
    assert api.get("/v1/clients", headers=bearer(s["access_token"], p1)).status_code == 200


def test_authenticated_user_can_create_another_practice(api, mailer) -> None:
    _, s = signup(api, mailer)
    h = bearer(s["access_token"])
    r = api.post("/v1/auth/practices", json={"name": "Second"}, headers=h)
    assert r.status_code == 201
    assert api.get("/v1/auth/session", headers=h).json()["active_practice_id"] == r.json()["practice_id"]


# ------------------------------------------------------------------ OIDC
def oidc_login(api, idp, **claims):
    idp.claims.update(claims)
    start = api.get("/v1/auth/oidc/keycloak/start?redirect=/clients", follow_redirects=False)
    assert start.status_code == 302
    url = urlparse(start.headers["location"])
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    idp.last_nonce = q["nonce"]
    return start, q


def test_oidc_authorization_code_with_pkce_creates_and_links_user(api, idp) -> None:
    start, q = oidc_login(api, idp)
    assert start.headers["location"].startswith("https://idp.example.test/authorize?")
    assert q["code_challenge_method"] == "S256" and q["client_id"] == "client-123"
    assert q["redirect_uri"] == "http://ankana.test/v1/auth/oidc/callback"
    cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.status_code == 302
    assert cb.headers["location"] == f"{ORIGIN}/auth/callback?next=/clients"
    assert "ankana_rt=" in cb.headers["set-cookie"]
    # PKCE: the verifier sent to the token endpoint hashes to the challenge
    verifier = idp.last_form["code_verifier"]
    digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert digest.decode() == q["code_challenge"] and idp.last_form["client_secret"] == "secret"
    # the cookie session works through the normal refresh path
    r = api.post("/v1/auth/refresh", headers=CSRF)
    assert r.status_code == 200 and r.json()["user"]["email"] == "oidc.person@example.test"
    assert r.json()["memberships"] == []  # new user: the web sends them to create a practice
    # state is single use
    again = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert again.headers["location"].endswith("/sign-in?error=oidc_state_invalid")


def test_oidc_links_by_verified_email_to_existing_account(api, mailer, idp) -> None:
    email, s = signup(api, mailer)
    _, q = oidc_login(api, idp, sub="idp-link-1", email=email)
    cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.status_code == 302
    r = api.post("/v1/auth/refresh", headers=CSRF).json()
    assert r["user"]["id"] == s["user"]["id"] and len(r["memberships"]) == 1


def test_oidc_rejects_unverified_email_bad_nonce_and_open_redirect(api, mailer, idp) -> None:
    email, _ = signup(api, mailer)
    _, q = oidc_login(api, idp, sub="idp-bad-1", email=email, email_verified=False)
    cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.headers["location"].endswith("/sign-in?error=oidc_email_unverified")
    assert "set-cookie" not in cb.headers
    idp.claims["email_verified"] = True
    _, q = oidc_login(api, idp)
    idp.nonce_override = "forged"
    cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.headers["location"].endswith("/sign-in?error=oidc_failed")
    idp.nonce_override = None
    r = api.get("/v1/auth/oidc/keycloak/start?redirect=//evil.test", follow_redirects=False)
    q = {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}
    idp.last_nonce = q["nonce"]
    cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.headers["location"] == f"{ORIGIN}/auth/callback?next=/"
    assert api.get("/v1/auth/oidc/nope/start", follow_redirects=False).status_code == 404
    assert api.get("/v1/auth/oidc/callback?error=access_denied",
                   follow_redirects=False).headers["location"].endswith("error=oidc_denied")


def test_oidc_id_token_for_another_audience_is_rejected(api, idp) -> None:
    _, q = oidc_login(api, idp, sub="idp-forge", email=email_())
    idp.claims["aud"] = "someone-else"
    cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.headers["location"].endswith("/sign-in?error=oidc_failed")


# --------------------------------------------------- phone and external IdP
def test_phone_code_goes_through_the_sms_interface(api, mailer, sms, owner_engine) -> None:
    email, s = signup(api, mailer)
    phone = "+9198" + str(uuid.uuid4().int)[:8]
    with owner_engine.begin() as c:
        c.execute(text("UPDATE user_account SET phone = :p WHERE id = :i"),
                  {"p": phone, "i": s["user"]["id"]})
    assert api.post("/v1/auth/otp/request", json={"phone": phone}).status_code == 202
    code = re.search(r"\b(\d{6})\b", sms.sent[-1][1]).group(1)
    r = api.post("/v1/auth/otp/verify", json={"phone": phone, "code": code}, headers=BODY)
    assert r.status_code == 200 and r.json()["user"]["id"] == s["user"]["id"]
    assert api.post("/v1/auth/otp/request", json={"phone": "12345"}).status_code == 422


def test_dev_stub_and_external_tokens_still_verify_alongside_builtin(api, mailer, stub) -> None:
    _, s = signup(api, mailer)
    assert api.get("/v1/me", headers=bearer(s["access_token"])).status_code == 200
    # a token from an unknown issuer is not trusted
    assert api.get("/v1/me", headers=bearer(stub.issue("someone"))).status_code == 401
    # a built-in-looking token signed by another key is rejected
    forged = jwt.encode({"iss": "http://ankana.test", "aud": "ankana-api", "sub": s["user"]["id"],
                         "exp": int(time.time()) + 60}, "x" * 32, algorithm="HS256")
    assert api.get("/v1/me", headers=bearer(forged)).status_code == 401


def test_signin_events_are_logged_without_the_email(api, mailer, owner_engine) -> None:
    email, _ = signup(api, mailer)
    api.post("/v1/auth/otp/verify", json={"email": email, "code": "000000"})
    with owner_engine.connect() as c:
        rows = c.execute(text("SELECT action, subject_hash, meta::text FROM auth_event "
                              "WHERE subject_hash IS NOT NULL OR action = 'signin.succeeded'")).all()
    assert rows and not any(email in (r[1] or "") or email in (r[2] or "") for r in rows)
    assert events(owner_engine, "signin.succeeded") >= 1 and events(owner_engine, "signup.completed") >= 1


# ------------------------------------------------------ security review regressions
def test_resend_cooldown_does_not_reveal_whether_an_account_exists(make_app, mailer) -> None:
    api = make_app(otp_resend_seconds=30)
    known, _ = signup(api, mailer)
    ghost = email_()
    statuses = []
    for email in (known, ghost):
        first = api.post("/v1/auth/otp/request", json={"email": email}).status_code
        second = api.post("/v1/auth/otp/request", json={"email": email}).status_code
        statuses.append((first, second))
    assert statuses[0][1] == statuses[1][1] == 429  # same answer for both


def test_signout_needs_the_refresh_secret_not_just_the_session_id(api, mailer) -> None:
    _, s = signup(api, mailer)
    sid = s["session_id"]
    h = bearer(s["access_token"])
    # the session id is visible in the access token; it must not be a signout credential
    assert api.post("/v1/auth/signout", json={"refresh_token": f"{sid}.wrong"}).status_code == 204
    assert api.get("/v1/me", headers=h).status_code == 200
    assert api.post("/v1/auth/signout", json={"refresh_token": s["refresh_token"]}).status_code == 204
    assert api.get("/v1/me", headers=h).status_code == 401


def test_oidc_callback_is_bound_to_the_browser_that_started_the_flow(make_app, idp) -> None:
    victim = make_app()
    attacker = make_app()
    _, q = oidc_login(attacker, idp, sub="idp-attacker", email=email_())
    # the attacker hands the victim a callback URL for the attacker's own flow
    cb = victim.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.headers["location"].endswith("/sign-in?error=oidc_state_invalid")
    assert "ankana_rt" not in cb.headers.get("set-cookie", "")
    # ... and the state was not burned by the failed attempt: the real browser still works
    ok = attacker.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert "ankana_rt=" in ok.headers["set-cookie"]


def test_oidc_redirect_param_rejects_backslash_tricks(api, idp) -> None:
    for bad in (r"/\evil.test", r"/ok\..\evil", "/a\r\nb"):
        r = api.get("/v1/auth/oidc/keycloak/start", params={"redirect": bad}, follow_redirects=False)
        q = {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}
        idp.last_nonce = q["nonce"]
        cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
        assert cb.headers["location"] == f"{ORIGIN}/auth/callback?next=/"


def test_oidc_discovery_issuer_must_match_configuration(api, idp) -> None:
    _, q = oidc_login(api, idp, sub="idp-iss", email=email_())
    api.app.state.oidc._discovery.clear()
    original = idp.handler

    def lying(request):
        r = original(request)
        if request.url.path.endswith("openid-configuration"):
            body = r.json()
            body["issuer"] = "https://evil.example.test"
            return httpx.Response(200, json=body)
        return r

    api.app.state.oidc.http = httpx.Client(transport=httpx.MockTransport(lying))
    cb = api.get(f"/v1/auth/oidc/callback?code=abc&state={q['state']}", follow_redirects=False)
    assert cb.headers["location"].endswith("/sign-in?error=oidc_failed")


def test_production_defaults_to_secure_cookies(monkeypatch) -> None:
    monkeypatch.setenv("API_ENV", "production")
    monkeypatch.setenv("AUTH_BUILTIN_ISSUER", "http://internal-api:8000")
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    assert AuthConfig.from_env().cookie_secure is True


def test_practice_bootstrap_respects_signup_closed(api, make_app, mailer) -> None:
    _, s = signup(api, mailer, practice=None)
    closed = make_app(signup_enabled=False)
    r = closed.post("/v1/practices", json={"name": "Sneaky"}, headers=bearer(s["access_token"]))
    assert r.status_code == 403


def test_external_issuer_cannot_impersonate_builtin_users() -> None:
    from app.auth.verifier import AuthError, _principal

    with pytest.raises(AuthError):
        _principal({"iss": "ankana", "sub": "00000000-0000-0000-0000-000000000000"})


def test_phone_codes_are_off_in_production_and_invite_names_cannot_inject_headers(
        make_app, mailer, api) -> None:
    from app.auth.mailer import SmtpMailer, build_sms

    cfg = dataclasses.replace(api.app.state.auth.cfg, env="production", sms="console")
    assert type(build_sms(cfg)).__name__ == "NoSms"
    from app.auth.mailer import sms_enabled

    assert sms_enabled(cfg) is False and sms_enabled(api.app.state.auth.cfg) is True
    # A practice name with a newline must not reach the Subject header unchanged.
    _, s = signup(api, mailer, practice="Evil\r\nBcc: attacker@example.test")
    h = bearer(s["access_token"])
    guest = email_()
    r = api.post("/v1/practice/invites", json={"email": guest, "role": "assistant"}, headers=h)
    assert r.status_code == 201, r.text
    subject = [m for m in mailer.sent if m.to == guest][-1].subject
    assert "\r" not in subject and "\n" not in subject
    # and the SMTP layer turns any leftover header problem into MailError, not a 500
    from app.auth.mailer import MailError, Message

    smtp = SmtpMailer(dataclasses.replace(cfg, smtp_host="localhost"))
    with pytest.raises(MailError):
        smtp.send(Message(to="a@example.test", subject="x\r\nBcc: y@example.test", text="t"))


# ------------------------------------------------- practice settings and portal summary
def test_owner_renames_practice_and_others_cannot(api, mailer) -> None:
    _, o, pid = make_team(api, mailer)
    oh = bearer(o["access_token"], pid)
    got = api.get("/v1/practice", headers=oh).json()
    assert got["name"] == "Team Practice" and got["timezone"]
    r = api.patch("/v1/practice", json={"name": "  Meera   Jyotish "}, headers=oh)
    assert r.status_code == 200 and r.json()["name"] == "Meera Jyotish"
    assert api.patch("/v1/practice", json={"name": "   "}, headers=oh).status_code == 422
    mate = email_()
    invite(api, mailer, o, pid, mate, "assistant")
    _, s = signup(api, mailer, email=mate, practice="Other")
    api.post(f"/v1/auth/invites/{mailer.invite_token(mate)}/accept", headers=bearer(s["access_token"]))
    ah = bearer(s["access_token"], pid)
    assert api.get("/v1/practice", headers=ah).status_code == 200
    assert api.patch("/v1/practice", json={"name": "Nope"}, headers=ah).status_code == 403


def test_portal_summary_is_client_only_and_scoped(api, mailer) -> None:
    _, o, pid = make_team(api, mailer)
    oh = bearer(o["access_token"], pid)
    mine = api.post("/v1/clients", json={"display_name": "Portal Person"}, headers=oh).json()["client"]["id"]
    api.post("/v1/clients", json={"display_name": "Someone Else"}, headers=oh)
    # a follow-up date in the future becomes the next appointment
    api.post(f"/v1/clients/{mine}/consultations",
             json={"topic": "Career", "mode": "video", "follow_up_date": "2999-01-02"}, headers=oh)
    portal = email_()
    invite(api, mailer, o, pid, portal, "client", mine)
    _, s = signup(api, mailer, email=portal, practice="Whatever")
    api.post(f"/v1/auth/invites/{mailer.invite_token(portal)}/accept", headers=bearer(s["access_token"]))
    ph = bearer(s["access_token"], pid)
    r = api.get("/v1/portal/summary", headers=ph)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["client_id"] == mine and body["display_name"] == "Portal Person"
    assert body["practice_name"] == "Team Practice" and body["reports"] == []
    assert body["next_appointment"]["kind"] == "follow_up"
    assert body["next_appointment"]["date"] == "2999-01-02"
    assert api.get("/v1/portal/summary", headers=oh).status_code == 403
