"""Private object storage with time-limited signed URLs.

Backends, selected by STORAGE_BACKEND (default "local"):
- LocalStorage: files under STORAGE_LOCAL_DIR; "signed" URLs are HMAC tokens
  served by the API route GET /v1/storage/{key} (see app.reports.api).
- AzureBlobStorage: private container; URLs are blob SAS tokens (read only,
  short expiry). Needs AZURE_STORAGE_CONNECTION_STRING (account key) or
  AZURE_STORAGE_ACCOUNT_URL (managed identity, user-delegation SAS).

Keys look like "<practice_id>/reports/<artifact_id>/<version>-<hash>.pdf" and
never contain PII.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import quote


class StorageError(Exception):
    pass


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def list_keys(self, prefix: str) -> list[str]: ...
    def signed_url(self, key: str, expires_in: int = 900, filename: str | None = None) -> str: ...


def _safe_key(key: str) -> str:
    parts = key.split("/")
    if not key or key.startswith("/") or "\x00" in key or any(
            p in ("", ".", "..") or "\\" in p or ":" in p for p in parts):
        raise StorageError(f"invalid storage key: {key!r}")
    return key


class LocalStorage:
    def __init__(self, root: str | Path, signing_key: str, public_base_url: str = "") -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._secret = signing_key.encode()
        self.public_base_url = public_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / _safe_key(key)).resolve()
        if self.root not in path.parents:
            raise StorageError("key escapes storage root")
        return path

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)  # atomic: readers never see a partial file

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"not found: {key}") from exc

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list_keys(self, prefix: str) -> list[str]:
        base = self.root / _safe_key(prefix.rstrip("/"))
        if not base.is_dir():
            return []
        return sorted(p.relative_to(self.root).as_posix() for p in base.rglob("*")
                      if p.is_file() and not p.name.endswith(".tmp"))

    def _sig(self, key: str, exp: int) -> str:
        return hmac.new(self._secret, f"{key}\n{exp}".encode(), hashlib.sha256).hexdigest()

    def signed_url(self, key: str, expires_in: int = 900, filename: str | None = None) -> str:
        _safe_key(key)
        exp = int(time.time()) + expires_in
        url = f"{self.public_base_url}/v1/storage/{quote(key)}?exp={exp}&sig={self._sig(key, exp)}"
        return url + (f"&filename={quote(filename)}" if filename else "")

    def verify(self, key: str, exp: int, sig: str) -> bool:
        return exp >= time.time() and hmac.compare_digest(self._sig(key, exp), sig)


class AzureBlobStorage:
    def __init__(self, container: str, connection_string: str | None = None,
                 account_url: str | None = None) -> None:
        from azure.storage.blob import BlobServiceClient

        if connection_string:
            self._svc = BlobServiceClient.from_connection_string(connection_string)
        elif account_url:
            from azure.identity import DefaultAzureCredential  # optional dependency

            self._svc = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        else:
            raise StorageError("set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_URL")
        self.container = container
        self._cc = self._svc.get_container_client(container)
        try:
            self._cc.create_container()  # private by default
        except Exception:
            pass  # exists (or created concurrently)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        from azure.storage.blob import ContentSettings

        self._cc.upload_blob(_safe_key(key), data, overwrite=True,
                             content_settings=ContentSettings(content_type=content_type))

    def get(self, key: str) -> bytes:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._cc.download_blob(_safe_key(key)).readall()
        except ResourceNotFoundError as exc:
            raise StorageError(f"not found: {key}") from exc

    def exists(self, key: str) -> bool:
        return self._cc.get_blob_client(_safe_key(key)).exists()

    def delete(self, key: str) -> None:
        self._cc.get_blob_client(_safe_key(key)).delete_blob(delete_snapshots="include") \
            if self.exists(key) else None

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(b.name for b in self._cc.list_blobs(name_starts_with=prefix))

    def signed_url(self, key: str, expires_in: int = 900, filename: str | None = None) -> str:
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        now = datetime.now(UTC)
        expiry = now + timedelta(seconds=expires_in)
        kwargs: dict = {}
        if filename:
            kwargs["content_disposition"] = f'attachment; filename="{filename}"'
        cred = self._svc.credential
        if getattr(cred, "account_key", None):
            kwargs["account_key"] = cred.account_key
        else:  # managed identity: user delegation key
            kwargs["user_delegation_key"] = self._svc.get_user_delegation_key(
                now - timedelta(minutes=5), expiry)
        sas = generate_blob_sas(
            account_name=self._svc.account_name, container_name=self.container,
            blob_name=_safe_key(key), permission=BlobSasPermissions(read=True),
            expiry=expiry, **kwargs)
        blob_url = self._cc.get_blob_client(key).url
        return f"{blob_url}?{sas}"


def storage_from_env(env: dict | None = None) -> Storage:
    env = os.environ if env is None else env
    backend = env.get("STORAGE_BACKEND", "local").lower()
    if backend == "local":
        key = (env.get("STORAGE_SIGNING_KEY") or "").strip()  # " " is a Key Vault placeholder
        if env.get("API_ENV") == "production" and len(key) < 24:
            raise RuntimeError("STORAGE_SIGNING_KEY is required in production "
                               "(24+ random characters)")
        if not key:
            key = "dev-only-signing-key"
        return LocalStorage(env.get("STORAGE_LOCAL_DIR", "./data/storage"), key,
                            env.get("STORAGE_PUBLIC_BASE_URL", "http://localhost:8000"))
    if backend == "azure":
        return AzureBlobStorage(
            env.get("AZURE_STORAGE_CONTAINER", "ankana-private"),
            connection_string=env.get("AZURE_STORAGE_CONNECTION_STRING"),
            account_url=env.get("AZURE_STORAGE_ACCOUNT_URL"))
    raise RuntimeError(f"unknown STORAGE_BACKEND {backend!r} (use local|azure)")
