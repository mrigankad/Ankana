"""Signing keys and the built-in access-token issuer (EdDSA / Ed25519).

Production: AUTH_SIGNING_KEY_PEM (or AUTH_SIGNING_KEY_FILE) holds a PKCS8 PEM,
typically injected from Key Vault. Rotation: move the old key to
AUTH_SIGNING_KEY_PREVIOUS_PEM so its tokens keep verifying (it is published in
the JWKS) until they expire, then drop it.
Dev and tests: a key is generated into AUTH_DEV_KEY_PATH (gitignored). It is
never generated when API_ENV=production.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .config import AUDIENCE, BUILTIN_ISSUER_KEY, AuthConfig
from .verifier import AuthError, Principal


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _load_pem(pem: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError("auth signing key must be an Ed25519 private key (PKCS8 PEM)")
    return key


def _pub_raw(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _kid(key: Ed25519PrivateKey) -> str:
    return _b64u(hashlib.sha256(_pub_raw(key)).digest()[:12])


def _jwk(key: Ed25519PrivateKey) -> dict:
    return {"kty": "OKP", "crv": "Ed25519", "x": _b64u(_pub_raw(key)), "kid": _kid(key),
            "use": "sig", "alg": "EdDSA"}


def generate_pem() -> str:
    return Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()


def load_signing_key(cfg: AuthConfig) -> Ed25519PrivateKey:
    if cfg.signing_key_pem and cfg.signing_key_pem.strip():
        return _load_pem(cfg.signing_key_pem.replace("\\n", "\n"))
    if cfg.signing_key_file:
        return _load_pem(Path(cfg.signing_key_file).read_text())
    if cfg.production:
        raise RuntimeError("Set AUTH_SIGNING_KEY_PEM or AUTH_SIGNING_KEY_FILE "
                           "(dev key generation is disabled in production)")
    path = Path(cfg.dev_key_path)
    if path.exists():
        return _load_pem(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    pem = generate_pem()
    path.write_text(pem)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return _load_pem(pem)


@dataclass
class Issuer:
    """Signs and verifies Ankana access tokens, and derives the HMAC key used
    for one-time codes."""

    cfg: AuthConfig
    key: Ed25519PrivateKey
    previous: Ed25519PrivateKey | None = None

    @classmethod
    def from_config(cls, cfg: AuthConfig) -> Issuer:
        prev = (_load_pem(cfg.previous_key_pem.replace("\\n", "\n"))
                if cfg.previous_key_pem and cfg.previous_key_pem.strip() else None)
        return cls(cfg, load_signing_key(cfg), prev)

    # -- publication
    @property
    def issuer(self) -> str:
        return self.cfg.issuer_url

    def jwks(self) -> dict:
        keys = [_jwk(self.key)] + ([_jwk(self.previous)] if self.previous else [])
        return {"keys": keys}

    def discovery(self) -> dict:
        base = self.cfg.issuer_url
        return {
            "issuer": base, "jwks_uri": f"{base}/.well-known/jwks.json",
            "token_endpoint": f"{base}/v1/auth/refresh",
            "id_token_signing_alg_values_supported": ["EdDSA"],
            "subject_types_supported": ["public"],
            "response_types_supported": ["token"],
            "claims_supported": ["sub", "iss", "aud", "exp", "iat", "email", "name", "sid"],
        }

    # -- tokens
    def issue(self, user_id: uuid.UUID, session_id: uuid.UUID, email: str | None,
              name: str | None) -> str:
        now = int(time.time())
        claims: dict = {"iss": self.cfg.issuer_url, "aud": AUDIENCE, "sub": str(user_id),
                        "sid": str(session_id), "iat": now,
                        "exp": now + self.cfg.access_ttl_seconds, "jti": uuid.uuid4().hex}
        if email:
            claims["email"] = email
        if name:
            claims["name"] = name
        return jwt.encode(claims, self.key, algorithm="EdDSA", headers={"kid": _kid(self.key)})

    def verify(self, token: str) -> Principal:
        keys = [self.key.public_key()] + ([self.previous.public_key()] if self.previous else [])
        last: Exception | None = None
        for pub in keys:
            try:
                claims = jwt.decode(token, pub, algorithms=["EdDSA"], issuer=self.cfg.issuer_url,
                                    audience=AUDIENCE, options={"require": ["exp", "sub", "iss"]})
            except jwt.PyJWTError as exc:
                last = exc
                continue
            return Principal(issuer=BUILTIN_ISSUER_KEY, subject=claims["sub"],
                             email=claims.get("email"), name=claims.get("name"),
                             session_id=claims.get("sid"))
        raise AuthError(str(last))

    # -- secrets derived from the signing key (never stored)
    def hmac_hex(self, purpose: str, value: str) -> str:
        secret = self.key.private_bytes(serialization.Encoding.Raw,
                                        serialization.PrivateFormat.Raw,
                                        serialization.NoEncryption())
        k = hashlib.sha256(b"ankana/" + purpose.encode() + b"/" + secret).digest()
        return hmac.new(k, value.encode(), hashlib.sha256).hexdigest()
