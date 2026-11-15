"""Master-key providers.

A practice data key (DEK) is never stored in the clear: it is wrapped by a
master key that lives outside the database. Two providers:

- EnvMasterKeyProvider: AES-256-GCM key from ANKANA_MASTER_KEY (base64, 32 bytes).
  ANKANA_MASTER_KEY_ID names it (default "env-1"). Rotation: put the new key in
  ANKANA_MASTER_KEY(+_ID) and keep the old ones in ANKANA_MASTER_KEY_PREVIOUS as
  "id:base64,id2:base64", then run `python -m app.privacy.cli rotate-master`.
- AzureKeyVaultMasterKeyProvider: RSA-OAEP-256 wrap with a Key Vault key
  (ANKANA_KEYVAULT_KEY_ID = https://<vault>.vault.azure.net/keys/<name>[/<version>]).
  Needs `azure-keyvault-keys` and `azure-identity`. NOT exercised by the test suite
  (no vault in CI); the interface is the same as the env provider.

In dev and test (API_ENV not production) a fixed, public development key is used
when nothing is configured, with a warning. Production refuses to start without one.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger(__name__)

DEV_KEY = b"ankana-dev-master-key-NOT-SECRET"  # exactly 32 bytes
assert len(DEV_KEY) == 32


class PrivacyError(Exception):
    pass


class MasterKeyProvider(Protocol):
    current_id: str

    def wrap(self, key: bytes, aad: bytes) -> tuple[str, bytes]:
        """Return (master_key_id, wrapped_key)."""

    def unwrap(self, master_key_id: str, wrapped: bytes, aad: bytes) -> bytes: ...


class EnvMasterKeyProvider:
    def __init__(self, keys: dict[str, bytes], current_id: str) -> None:
        for kid, k in keys.items():
            if len(k) != 32:
                raise PrivacyError(f"master key {kid!r} must be 32 bytes")
        if current_id not in keys:
            raise PrivacyError("current master key id missing")
        self._keys = keys
        self.current_id = current_id

    def wrap(self, key: bytes, aad: bytes) -> tuple[str, bytes]:
        nonce = secrets.token_bytes(12)
        ct = AESGCM(self._keys[self.current_id]).encrypt(nonce, key, aad)
        return self.current_id, nonce + ct

    def unwrap(self, master_key_id: str, wrapped: bytes, aad: bytes) -> bytes:
        try:
            k = self._keys[master_key_id]
        except KeyError:
            raise PrivacyError(
                f"master key {master_key_id!r} is not configured "
                "(add it to ANKANA_MASTER_KEY_PREVIOUS)") from None
        return AESGCM(k).decrypt(wrapped[:12], wrapped[12:], aad)


class AzureKeyVaultMasterKeyProvider:
    def __init__(self, key_id: str) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.keys.crypto import CryptographyClient

        self._cred = DefaultAzureCredential()
        self._factory = CryptographyClient
        self.current_id = key_id
        self._clients: dict[str, object] = {}

    def _client(self, key_id: str):
        if key_id not in self._clients:
            self._clients[key_id] = self._factory(key_id, self._cred)
        return self._clients[key_id]

    def wrap(self, key: bytes, aad: bytes) -> tuple[str, bytes]:
        from azure.keyvault.keys.crypto import KeyWrapAlgorithm

        res = self._client(self.current_id).wrap_key(KeyWrapAlgorithm.rsa_oaep_256, key)
        return res.key_id or self.current_id, res.encrypted_key  # versioned id

    def unwrap(self, master_key_id: str, wrapped: bytes, aad: bytes) -> bytes:
        from azure.keyvault.keys.crypto import KeyWrapAlgorithm

        return self._client(master_key_id).unwrap_key(
            KeyWrapAlgorithm.rsa_oaep_256, wrapped).key


def _b64(s: str) -> bytes:
    raw = base64.b64decode(s.strip() + "=" * (-len(s.strip()) % 4), validate=False)
    if len(raw) != 32:
        raise PrivacyError("master key must be 32 bytes, base64 encoded")
    return raw


def provider_from_env(env: dict | None = None) -> MasterKeyProvider:
    env = os.environ if env is None else env
    if env.get("ANKANA_KEYVAULT_KEY_ID"):
        return AzureKeyVaultMasterKeyProvider(env["ANKANA_KEYVAULT_KEY_ID"])
    raw = env.get("ANKANA_MASTER_KEY")
    if not raw:
        if env.get("API_ENV") == "production":
            raise PrivacyError("ANKANA_MASTER_KEY (or ANKANA_KEYVAULT_KEY_ID) is required "
                               "in production")
        log.warning("ANKANA_MASTER_KEY not set: using the public development master key")
        return EnvMasterKeyProvider({"dev": DEV_KEY}, "dev")
    kid = env.get("ANKANA_MASTER_KEY_ID", "env-1")
    keys = {kid: _b64(raw)}
    prev = env.get("ANKANA_MASTER_KEY_PREVIOUS", "")
    for part in filter(None, (p.strip() for p in prev.split(","))):
        pid, _, val = part.partition(":")
        keys[pid] = _b64(val)
    return EnvMasterKeyProvider(keys, kid)


_provider: MasterKeyProvider | None = None


def get_master_provider() -> MasterKeyProvider:
    global _provider
    if _provider is None:
        _provider = provider_from_env()
    return _provider


def set_master_provider(provider: MasterKeyProvider | None) -> None:
    """Install a provider (tests, rotation CLI). None re-reads the environment."""
    global _provider
    _provider = provider
