import time

import pytest

from app.storage import AzureBlobStorage, LocalStorage, StorageError, storage_from_env


@pytest.fixture()
def store(tmp_path):
    return LocalStorage(tmp_path / "s", "secret", "http://api.test")


def test_roundtrip_and_overwrite(store):
    store.put("p1/reports/a.pdf", b"one", "application/pdf")
    assert store.exists("p1/reports/a.pdf")
    assert store.get("p1/reports/a.pdf") == b"one"
    store.put("p1/reports/a.pdf", b"two")
    assert store.get("p1/reports/a.pdf") == b"two"
    store.delete("p1/reports/a.pdf")
    assert not store.exists("p1/reports/a.pdf")
    with pytest.raises(StorageError):
        store.get("p1/reports/a.pdf")


@pytest.mark.parametrize("key", ["../x", "a/../../x", "/abs", "a//b", "", "a\\b"])
def test_rejects_unsafe_keys(store, key):
    with pytest.raises(StorageError):
        store.put(key, b"x")


def test_signed_url_verifies_and_expires(store):
    url = store.signed_url("p1/a.pdf", expires_in=60, filename="r.pdf")
    assert url.startswith("http://api.test/v1/storage/p1/a.pdf?exp=")
    exp = int(url.split("exp=")[1].split("&")[0])
    sig = url.split("sig=")[1].split("&")[0]
    assert store.verify("p1/a.pdf", exp, sig)
    assert not store.verify("p1/other.pdf", exp, sig)  # bound to the key
    assert not store.verify("p1/a.pdf", exp + 1, sig)  # bound to expiry
    expired = int(time.time()) - 1
    assert not store.verify("p1/a.pdf", expired, store._sig("p1/a.pdf", expired))


def test_storage_from_env(tmp_path):
    s = storage_from_env({"STORAGE_BACKEND": "local", "STORAGE_LOCAL_DIR": str(tmp_path),
                          "STORAGE_SIGNING_KEY": "k"})
    assert isinstance(s, LocalStorage)
    with pytest.raises(RuntimeError):
        storage_from_env({"STORAGE_BACKEND": "local", "API_ENV": "production"})
    with pytest.raises(RuntimeError):
        storage_from_env({"STORAGE_BACKEND": "s3"})


AZURITE_CONN = (
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:{port}/devstoreaccount1;"
)


@pytest.fixture(scope="module")
def azurite():
    """Azure emulator via testcontainers; skipped when Docker or the image is unavailable."""
    try:
        from testcontainers.core.container import DockerContainer
        from testcontainers.core.waiting_utils import wait_for_logs

        c = DockerContainer("mcr.microsoft.com/azure-storage/azurite").with_exposed_ports(10000)
        c.with_command("azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck")
        c.start()
        wait_for_logs(c, "successfully listens", timeout=30)
    except Exception as exc:
        pytest.skip(f"azurite unavailable: {exc}")
    yield AZURITE_CONN.format(port=c.get_exposed_port(10000))
    c.stop()


def test_azure_blob_with_azurite(azurite):
    import httpx

    s = AzureBlobStorage("ankana-test", connection_string=azurite)
    s.put("p1/reports/a.pdf", b"%PDF-azure", "application/pdf")
    assert s.exists("p1/reports/a.pdf") and s.get("p1/reports/a.pdf") == b"%PDF-azure"
    url = s.signed_url("p1/reports/a.pdf", 60, filename="r.pdf")
    assert "sig=" in url and "se=" in url
    r = httpx.get(url)  # SAS works without credentials
    assert r.status_code == 200 and r.content == b"%PDF-azure"
    assert httpx.get(url.split("?")[0]).status_code in (401, 403, 404)  # private
    s.delete("p1/reports/a.pdf")
    assert not s.exists("p1/reports/a.pdf")


@pytest.mark.parametrize("key", ["p1/a.pdf:stream", "C:/x", "p1/a\x00.pdf", "p1/%2e%2e/x"])
def test_rejects_more_unsafe_keys(store, key):
    if key == "p1/%2e%2e/x":  # percent-encoding is decoded by the web layer, never by storage
        store.put(key, b"x")
        return
    with pytest.raises(StorageError):
        store.put(key, b"x")


def test_download_route_refuses_traversal_even_with_a_valid_signature(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.reports.api import build_reports_router

    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    store = LocalStorage(tmp_path / "s", "k", "http://t")
    app = FastAPI()
    app.state.storage = store
    app.include_router(build_reports_router())
    c = TestClient(app)
    store.put("p1/a.pdf", b"%PDF")
    url = store.signed_url("p1/a.pdf").replace("http://t", "")
    assert c.get(url).status_code == 200
    exp = int(time.time()) + 60
    for key in ("../secret.txt", "p1/../../secret.txt", "..%2fsecret.txt"):
        sig = store._sig(key, exp)  # attacker cannot sign; this is the worst case
        r = c.get(f"/v1/storage/{key}", params={"exp": exp, "sig": sig})
        assert r.status_code in (404, 403) and b"top secret" not in r.content


def test_blank_or_short_signing_key_is_refused_in_production():
    # Key Vault placeholders are a single space: that must not become a real (guessable) key
    for bad in (None, "", " ", "short"):
        env = {"API_ENV": "production", "STORAGE_BACKEND": "local"}
        if bad is not None:
            env["STORAGE_SIGNING_KEY"] = bad
        with pytest.raises(RuntimeError):
            storage_from_env(env)


def test_blank_secret_key_counts_as_unset(monkeypatch):
    from ankana_ai import connections as cx

    monkeypatch.setenv("ANKANA_SECRET_KEY", " ")
    monkeypatch.setenv("API_ENV", "dev")
    assert not cx.secret_key_configured()
    monkeypatch.setenv("API_ENV", "production")
    monkeypatch.setenv("ANKANA_SECRET_KEY", "too-short")
    assert not cx.secret_key_configured()
    monkeypatch.setenv("ANKANA_SECRET_KEY", "x" * 32)
    assert cx.secret_key_configured()
    assert cx.decrypt_key(cx.encrypt_key("sk-123")) == "sk-123"
