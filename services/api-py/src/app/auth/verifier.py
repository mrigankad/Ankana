"""Pluggable JWT verification.

Production: JwksVerifier fetches signing keys from AUTH_JWKS_URL (Clerk, Auth0,
Entra External ID, Supabase and Cognito all publish one) and checks issuer,
audience and expiry. Dev and tests: StubIssuer signs RS256 tokens with an
in-process key; it refuses to build when API_ENV=production.
"""

import os
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient

from app.settings import Settings


class AuthError(Exception):
    """Token missing, malformed, expired or not trusted."""


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str
    email: str | None = None
    phone: str | None = None
    name: str | None = None
    session_id: str | None = None  # built-in tokens only; checked for revocation


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Principal: ...


def _principal(claims: dict) -> Principal:
    sub = claims.get("sub")
    iss = claims.get("iss")
    if not sub or not iss:
        raise AuthError("token lacks sub or iss")
    if iss == "ankana":  # the user_account.issuer key of built-in users: never accept it from outside
        raise AuthError("issuer not trusted")
    return Principal(
        issuer=iss, subject=sub, email=claims.get("email"),
        phone=claims.get("phone_number") or claims.get("phone"), name=claims.get("name"),
    )


class JwksVerifier:
    def __init__(self, jwks_url: str, issuer: str | None, audience: str | None,
                 algorithms: tuple[str, ...] = ("RS256",)) -> None:
        self._jwks = PyJWKClient(jwks_url, cache_keys=True)
        self._issuer = issuer
        self._audience = audience
        self._algorithms = list(algorithms)

    def verify(self, token: str) -> Principal:
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=self._algorithms, issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "sub", "iss"],
                         "verify_aud": self._audience is not None},
            )
        except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
            raise AuthError(str(exc)) from exc
        return _principal(claims)


class StubIssuer:
    """Dev-only token issuer and verifier in one object."""

    ISSUER = "ankana-dev-stub"
    AUDIENCE = "ankana-api"

    def __init__(self, key_pem: str | None = None) -> None:
        # A fixed key (AUTH_DEV_STUB_KEY_PEM, dev and load tests only) lets several API worker
        # processes accept the same tokens; by default every process makes its own key.
        if key_pem:
            self._key = serialization.load_pem_private_key(key_pem.encode(), password=None)
            self._kid = "dev-stub-fixed"
        else:
            self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            self._kid = uuid.uuid4().hex

    def issue(self, subject: str, email: str | None = None, name: str | None = None,
              ttl_seconds: int = 3600) -> str:
        now = int(time.time())
        claims = {"iss": self.ISSUER, "aud": self.AUDIENCE, "sub": subject,
                  "iat": now, "exp": now + ttl_seconds}
        if email:
            claims["email"] = email
        if name:
            claims["name"] = name
        return jwt.encode(claims, self._key, algorithm="RS256", headers={"kid": self._kid})

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token, self._key.public_key(), algorithms=["RS256"],
                issuer=self.ISSUER, audience=self.AUDIENCE,
                options={"require": ["exp", "sub", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError(str(exc)) from exc
        return _principal(claims)


class CompositeVerifier:
    """Routes by the token's (unverified) `iss`: Ankana's own issuer goes to the
    built-in verifier, anything else to the external one (JWKS or dev stub). The
    claim only picks the verifier; each verifier checks signature and issuer."""

    def __init__(self, builtin: TokenVerifier, builtin_issuer: str,
                 external: TokenVerifier | None) -> None:
        self._builtin = builtin
        self._issuer = builtin_issuer
        self._external = external

    @property
    def external(self) -> TokenVerifier | None:
        return self._external

    def verify(self, token: str) -> Principal:
        try:
            iss = jwt.decode(token, options={"verify_signature": False}).get("iss")
        except jwt.PyJWTError as exc:
            raise AuthError(str(exc)) from exc
        if iss == self._issuer:
            return self._builtin.verify(token)
        if self._external is None:
            raise AuthError("issuer not trusted")
        return self._external.verify(token)


def build_verifier(settings: Settings, issuer=None) -> TokenVerifier:
    """Built-in issuer always; plus the dev stub (AUTH_DEV_STUB) or an external
    JWKS issuer (AUTH_JWKS_URL) when configured, so existing IdPs keep working."""
    external: TokenVerifier | None = None
    if settings.auth_dev_stub:
        if settings.env == "production":
            raise RuntimeError("dev stub issuer cannot run in production")
        external = StubIssuer(os.getenv("AUTH_DEV_STUB_KEY_PEM") or None)
    elif settings.auth_jwks_url:
        external = JwksVerifier(settings.auth_jwks_url, settings.auth_issuer,
                                settings.auth_audience, settings.auth_algorithms)
    if issuer is None:
        return external or _NoVerifier()
    return CompositeVerifier(issuer, issuer.issuer, external)


class _NoVerifier:
    def verify(self, token: str) -> Principal:
        raise AuthError("no issuer configured")
