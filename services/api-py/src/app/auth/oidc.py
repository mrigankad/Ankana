"""Generic OpenID Connect relying party: authorization code + PKCE (S256).

Works with any compliant issuer (Google, Keycloak, Zitadel, Authentik,
Entra ID): endpoints come from {issuer}/.well-known/openid-configuration. The
ID token is verified (signature via the issuer JWKS, iss, aud, exp, nonce) and
the user is linked by a *verified* email. State, nonce and PKCE verifier are
single use and stored hashed/short-lived in Postgres.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import delete

from app.tenancy.models import AuthOidcState
from app.tenancy.session import global_session

from .config import OidcProvider
from .service import AuthProblem, AuthService, Origin, now, sha256_hex

STATE_TTL = timedelta(minutes=10)
ALGS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256", "EdDSA"]


class OidcError(Exception):
    pass


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class OidcClient:
    def __init__(self, service: AuthService, http: httpx.Client | None = None) -> None:
        self.svc = service
        self.http = http or httpx.Client(timeout=10)
        self._discovery: dict[str, dict] = {}

    def _config(self, p: OidcProvider) -> dict:
        if p.id not in self._discovery:
            try:
                r = self.http.get(f"{p.issuer}/.well-known/openid-configuration")
                r.raise_for_status()
                self._discovery[p.id] = r.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise OidcError(f"discovery failed for {p.id}: {exc}") from exc
        return self._discovery[p.id]

    def callback_url(self) -> str:
        return f"{self.svc.cfg.issuer_url}/v1/auth/oidc/callback"

    def start(self, p: OidcProvider, redirect_to: str | None) -> tuple[str, str]:
        """Returns (authorization URL, state). The caller binds `state` to the browser with
        a cookie so a callback link forged by someone else (login CSRF) is refused."""
        conf = self._config(p)
        state, nonce, verifier = (secrets.token_urlsafe(24), secrets.token_urlsafe(16),
                                  secrets.token_urlsafe(48))
        challenge = _b64u(hashlib.sha256(verifier.encode()).digest())
        with global_session(self.svc.engine) as db:
            db.execute(delete(AuthOidcState).where(AuthOidcState.expires_at < now()))
            db.add(AuthOidcState(state_hash=sha256_hex(state), provider=p.id,
                                 code_verifier=verifier, nonce=nonce,
                                 redirect_to=(redirect_to or "")[:500] or None,
                                 expires_at=now() + STATE_TTL))
        query = urlencode({
            "response_type": "code", "client_id": p.client_id, "redirect_uri": self.callback_url(),
            "scope": p.scopes, "state": state, "nonce": nonce,
            "code_challenge": challenge, "code_challenge_method": "S256"})
        return f"{conf['authorization_endpoint']}?{query}", state

    def finish(self, code: str, state: str, origin: Origin) -> tuple[uuid.UUID, str | None, str]:
        """Returns (user_id, redirect_to, provider id)."""
        with global_session(self.svc.engine) as db:
            row = db.get(AuthOidcState, sha256_hex(state))
            if row is None or row.expires_at < now():
                raise AuthProblem(400, "This sign-in link has expired. Start again.",
                                  "oidc_state_invalid")
            provider_id, verifier, nonce, redirect_to = (
                row.provider, row.code_verifier, row.nonce, row.redirect_to)
            db.delete(row)  # single use
        p = self.svc.cfg.oidc_provider(provider_id)
        if p is None:
            raise AuthProblem(400, "That sign-in provider is not available.", "oidc_unknown")
        try:
            claims = self._exchange(p, code, verifier, nonce)
        except OidcError as exc:
            self.svc.log("signin.failed", ip=origin.ip,
                         meta={"reason": "oidc", "provider": p.id, "detail": str(exc)[:120]})
            raise AuthProblem(401, "The provider could not confirm your identity.",
                              "oidc_failed") from None
        email = str(claims.get("email") or "").lower()
        if not email or claims.get("email_verified") is not True:
            self.svc.log("signin.failed", ip=origin.ip,
                         meta={"reason": "oidc_unverified_email", "provider": p.id})
            raise AuthProblem(403, "Your provider did not confirm a verified email address.",
                              "oidc_email_unverified")
        uid = self.svc.link_oidc_user(p.id, str(claims["sub"]), email, claims.get("name"), origin)
        return uid, redirect_to, p.id

    def _exchange(self, p: OidcProvider, code: str, verifier: str, nonce: str) -> dict:
        conf = self._config(p)
        data = {"grant_type": "authorization_code", "code": code, "client_id": p.client_id,
                "redirect_uri": self.callback_url(), "code_verifier": verifier}
        if p.client_secret:
            data["client_secret"] = p.client_secret
        try:
            tr = self.http.post(conf["token_endpoint"], data=data)
            tr.raise_for_status()
            id_token = tr.json()["id_token"]
            jwks = self.http.get(conf["jwks_uri"])
            jwks.raise_for_status()
            keys = jwt.PyJWKSet.from_dict(jwks.json())
            kid = jwt.get_unverified_header(id_token).get("kid")
            key = next((k for k in keys.keys if kid is None or k.key_id == kid), None)
            if key is None:
                raise OidcError("signing key not found")
            if str(conf.get("issuer", "")).rstrip("/") != p.issuer:
                raise OidcError("discovery issuer does not match the configured issuer")
            claims = jwt.decode(id_token, key.key, algorithms=ALGS, audience=p.client_id,
                                issuer=conf["issuer"],
                                options={"require": ["exp", "sub", "iss", "aud"]})
        except (httpx.HTTPError, KeyError, ValueError, jwt.PyJWTError) as exc:
            raise OidcError(str(exc)) from exc
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcError("nonce mismatch")
        return claims
