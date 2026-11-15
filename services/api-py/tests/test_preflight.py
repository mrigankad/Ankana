"""app.preflight: a complete production env passes, and each missing/bad variable is reported."""

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

from app import preflight


def _pem(key) -> str:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


@pytest.fixture()
def ephe(tmp_path):
    for f in preflight.EPHE_FILES:
        (tmp_path / f).write_bytes(b"x")
    return str(tmp_path)


@pytest.fixture()
def env(ephe):
    return {
        "API_ENV": "production",
        "API_DATABASE_URL": "postgresql+psycopg://ankana_app:pw@db:5432/ankana",
        "ANKANA_SECRET_KEY": "s" * 48,
        "ANKANA_MASTER_KEY": base64.b64encode(b"k" * 32).decode(),
        "NOTIFY_LINK_SECRET": "l" * 48,
        "NOTIFY_PUBLIC_BASE_URL": "https://api.ankana.example",
        "STORAGE_BACKEND": "azure",
        "AZURE_STORAGE_ACCOUNT_URL": "https://st.blob.core.windows.net",
        "AZURE_STORAGE_CONTAINER": "reports",
        "AZURE_CLIENT_ID": "00000000-0000-0000-0000-000000000000",
        "ANKANA_EPHEMERIS": "swiss",
        "ANKANA_SE_EPHE_PATH": ephe,
        "ANKANA_AI_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "ANKANA_ALLOW_LOCAL_PROVIDERS": "0",
        "ANKANA_GIT_SHA": "abc123",
        "ANKANA_SOURCE_URL": "https://github.com/mrigankad/Ankana",
        "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=x",
        "NOTIFY_EMAIL_BACKEND": "acs",
        "ACS_CONNECTION_STRING": "endpoint=https://acs.example/;accesskey=QUJD",
        "ACS_EMAIL_FROM": "no-reply@ankana.example",
        "AUTH_SIGNING_KEY_PEM": _pem(Ed25519PrivateKey.generate()),
        "AUTH_BUILTIN_ISSUER": "https://api.ankana.example",
        "AUTH_WEB_BASE_URL": "https://app.ankana.example",
        "AUTH_ALLOWED_ORIGINS": "https://app.ankana.example",
        "AUTH_TRUST_PROXY": "1",
        "AUTH_COOKIE_SECURE": "1",
        "AUTH_MAILER": "acs",
        "AUTH_MAIL_FROM": "Ankana <no-reply@ankana.example>",
        "ACS_EMAIL_CONNECTION_STRING": "endpoint=https://acs.example/;accesskey=QUJD",
        "AUTH_SMS": "none",
        "NOTIFY_WHATSAPP_BACKEND": "console",
    }


def check(env, role="api"):
    return preflight.check(env, role, has_module=lambda _m: True)


def bad_vars(env, role="api"):
    return {p.var for p in preflight.errors(check(env, role))}


def test_complete_env_passes_for_api_and_worker(env):
    assert preflight.errors(check(env, "api")) == []
    assert preflight.errors(check(env, "worker")) == []


def test_worker_does_not_need_auth_settings(env):
    for k in [k for k in env if k.startswith("AUTH_") or k == "ACS_EMAIL_CONNECTION_STRING"]:
        del env[k]
    assert preflight.errors(check(env, "worker")) == []
    assert "AUTH_SIGNING_KEY_PEM" in bad_vars(env, "api")


def test_empty_env_lists_everything_at_once():
    problems = preflight.errors(check({}, "api"))
    names = {p.var for p in problems}
    assert {"API_ENV", "API_DATABASE_URL", "ANKANA_SECRET_KEY", "ANKANA_MASTER_KEY",
            "NOTIFY_LINK_SECRET", "AUTH_SIGNING_KEY_PEM", "AUTH_BUILTIN_ISSUER",
            "AUTH_ALLOWED_ORIGINS", "AUTH_MAILER", "NOTIFY_EMAIL_BACKEND"} <= names
    assert len(problems) > 10


@pytest.mark.parametrize("var", [
    "API_DATABASE_URL", "ANKANA_SECRET_KEY", "ANKANA_MASTER_KEY", "NOTIFY_LINK_SECRET",
    "NOTIFY_PUBLIC_BASE_URL", "AUTH_SIGNING_KEY_PEM", "AUTH_BUILTIN_ISSUER", "AUTH_WEB_BASE_URL",
    "AUTH_ALLOWED_ORIGINS", "AUTH_MAILER", "AUTH_MAIL_FROM", "ANKANA_SE_EPHE_PATH",
    "ANKANA_EPHEMERIS", "AZURE_STORAGE_ACCOUNT_URL", "AZURE_CLIENT_ID",
])
def test_each_required_variable_is_reported(env, var):
    env.pop(var)
    assert var in bad_vars(env)


def test_key_vault_placeholder_space_counts_as_unset(env):
    env["ANKANA_SECRET_KEY"] = " "
    env["ANTHROPIC_API_KEY"] = " "
    assert "ANKANA_SECRET_KEY" in bad_vars(env)
    assert "ANTHROPIC_API_KEY" in bad_vars(env)  # provider is anthropic


def test_short_secrets_are_rejected(env):
    env["ANKANA_SECRET_KEY"] = "short"
    env["NOTIFY_LINK_SECRET"] = "x" * 23
    assert {"ANKANA_SECRET_KEY", "NOTIFY_LINK_SECRET"} <= bad_vars(env)


def test_signing_key_must_be_ed25519_pem(env):
    env["AUTH_SIGNING_KEY_PEM"] = "not a pem"
    assert "AUTH_SIGNING_KEY_PEM" in bad_vars(env)
    env["AUTH_SIGNING_KEY_PEM"] = _pem(generate_private_key(65537, 2048))
    assert "AUTH_SIGNING_KEY_PEM" in bad_vars(env)
    env["AUTH_SIGNING_KEY_PEM"] = _pem(Ed25519PrivateKey.generate()).replace("\n", "\\n")
    assert "AUTH_SIGNING_KEY_PEM" not in bad_vars(env)


def test_master_key_must_be_32_bytes_base64(env):
    env["ANKANA_MASTER_KEY"] = base64.b64encode(b"short").decode()
    assert "ANKANA_MASTER_KEY" in bad_vars(env)
    env["ANKANA_MASTER_KEY"] = base64.b64encode(b"k" * 32).decode()
    env["ANKANA_MASTER_KEY_PREVIOUS"] = "old-no-colon"
    assert "ANKANA_MASTER_KEY_PREVIOUS" in bad_vars(env)
    del env["ANKANA_MASTER_KEY"], env["ANKANA_MASTER_KEY_PREVIOUS"]
    env["ANKANA_KEYVAULT_KEY_ID"] = "https://v.vault.azure.net/keys/k"
    assert "ANKANA_MASTER_KEY" not in bad_vars(env)


def test_local_storage_needs_signing_key_and_is_refused_by_default(env):
    env["STORAGE_BACKEND"] = "local"
    assert {"STORAGE_BACKEND", "STORAGE_SIGNING_KEY"} <= bad_vars(env)
    env["STORAGE_SIGNING_KEY"] = "k" * 32
    env["PREFLIGHT_ALLOW_LOCAL_STORAGE"] = "1"
    assert not bad_vars(env) & {"STORAGE_BACKEND", "STORAGE_SIGNING_KEY"}


def test_hosted_guards(env):
    env["ANKANA_ALLOW_LOCAL_PROVIDERS"] = "1"
    env["ANKANA_LEGACY_API"] = "1"
    env["AUTH_DEV_STUB"] = "1"
    env["AUTH_COOKIE_SECURE"] = "0"
    env["ANKANA_EPHEMERIS"] = "moshier"
    assert {"ANKANA_ALLOW_LOCAL_PROVIDERS", "ANKANA_LEGACY_API", "AUTH_DEV_STUB",
            "AUTH_COOKIE_SECURE", "ANKANA_EPHEMERIS"} <= bad_vars(env)


def test_ephemeris_data_files_must_exist(env, tmp_path):
    env["ANKANA_SE_EPHE_PATH"] = str(tmp_path / "nope")
    assert "ANKANA_SE_EPHE_PATH" in bad_vars(env)


def test_localhost_and_http_urls_are_rejected(env):
    env["AUTH_BUILTIN_ISSUER"] = "http://api.ankana.example"
    env["AUTH_ALLOWED_ORIGINS"] = "https://app.ankana.example,http://localhost:3000"
    env["NOTIFY_PUBLIC_BASE_URL"] = "https://localhost:8000"
    assert {"AUTH_BUILTIN_ISSUER", "AUTH_ALLOWED_ORIGINS", "NOTIFY_PUBLIC_BASE_URL"} <= bad_vars(env)


def test_allowed_origins_must_include_web_base(env):
    env["AUTH_ALLOWED_ORIGINS"] = "https://other.ankana.example"
    assert "AUTH_ALLOWED_ORIGINS" in bad_vars(env)


def test_mailers_console_refused_and_acs_string_parsed(env):
    env["AUTH_MAILER"] = "console"
    env["NOTIFY_EMAIL_BACKEND"] = "console"
    assert {"AUTH_MAILER", "NOTIFY_EMAIL_BACKEND"} <= bad_vars(env)
    env["AUTH_MAILER"] = "acs"
    env["ACS_EMAIL_CONNECTION_STRING"] = "garbage"
    env["NOTIFY_EMAIL_BACKEND"] = "smtp"
    assert {"ACS_EMAIL_CONNECTION_STRING", "SMTP_HOST", "NOTIFY_EMAIL_FROM"} <= bad_vars(env)
    env["AUTH_MAIL_FROM"] = "Ankana <no-reply@localhost>"
    assert "AUTH_MAIL_FROM" in bad_vars(env)


def test_ai_provider_rules(env):
    env["ANKANA_AI_PROVIDER"] = "mock"
    assert "ANKANA_AI_PROVIDER" in bad_vars(env)
    env["ANKANA_AI_PROVIDER"] = ""
    env.pop("ANTHROPIC_API_KEY")
    assert not bad_vars(env)  # AI simply off: a warning, not a failure
    assert any(p.var == "ANTHROPIC_API_KEY" and p.level == "warning" for p in check(env))


def test_billing_on_needs_razorpay_and_supplier(env):
    assert not bad_vars(env)  # billing off by default
    env["ANKANA_BILLING"] = "on"
    assert {"RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET",
            "ANKANA_SUPPLIER_NAME", "ANKANA_SUPPLIER_GSTIN", "ANKANA_SUPPLIER_ADDRESS",
            "ANKANA_SUPPLIER_EMAIL"} <= bad_vars(env)
    env.update(RAZORPAY_KEY_ID="rzp_live_x", RAZORPAY_KEY_SECRET="s", RAZORPAY_WEBHOOK_SECRET="w",
               ANKANA_SUPPLIER_NAME="Ankana Labs Pvt Ltd", ANKANA_SUPPLIER_GSTIN="29ABCDE1234F1Z5",
               ANKANA_SUPPLIER_STATE_CODE="29", ANKANA_SUPPLIER_ADDRESS="Bengaluru",
               ANKANA_SUPPLIER_EMAIL="billing@ankana.example", ANKANA_BILLING_PROVIDER="razorpay")
    assert not bad_vars(env)


def test_missing_python_packages_are_reported(env):
    problems = preflight.errors(
        preflight.check(env, "api", has_module=lambda m: m != "azure.identity"))
    assert any("azure.identity" in p.message for p in problems)


def test_migrate_role():
    assert bad_vars({}, "migrate") == {"API_MIGRATION_URL", "APP_ROLE_PASSWORD",
                                       "ANKANA_MASTER_KEY", "API_ENV"}
    ok = {"API_MIGRATION_URL": "postgresql+psycopg://o:p@h/db", "APP_ROLE_PASSWORD": "p" * 32,
          "API_ENV": "production", "ANKANA_MASTER_KEY": base64.b64encode(b"k" * 32).decode()}
    assert not bad_vars(ok, "migrate")


def test_cli_exit_codes_and_never_prints_values(env, monkeypatch, capsys):
    monkeypatch.setattr(preflight, "_has_module", lambda _m: True)
    monkeypatch.setattr(preflight.check, "__kwdefaults__", {"has_module": lambda _m: True})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert preflight.main(["--role", "api"]) == 0
    monkeypatch.setenv("ANKANA_SECRET_KEY", "super-secret-short")
    assert preflight.main(["--role", "api"]) == 1
    err = capsys.readouterr().err
    assert "ANKANA_SECRET_KEY" in err and "super-secret-short" not in err


def test_ready_endpoint_is_503_until_configured(env, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    for k in env:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("API_ENV", "production")
    r = TestClient(app).get("/health/ready")
    assert r.status_code == 503 and "ANKANA" not in r.text
    monkeypatch.setenv("API_ENV", "dev")
    assert TestClient(app).get("/health/ready").status_code == 200


def test_metrics_exporter_packages_required_when_app_insights_is_configured(env):
    env["APPLICATIONINSIGHTS_CONNECTION_STRING"] = "InstrumentationKey=00000000-0000-0000-0000-000000000000"
    problems = preflight.check(env, "api", has_module=lambda m: not m.startswith("opentelemetry"))
    assert any("opentelemetry.sdk.metrics" in str(p) for p in problems if p.level == "error")
    env["ANKANA_METRICS"] = "0"
    assert not any("opentelemetry" in str(p) for p in preflight.check(
        env, "api", has_module=lambda m: not m.startswith("opentelemetry")))


def test_trust_proxy_warning_for_the_api_only(env):
    env.pop("AUTH_TRUST_PROXY", None)
    assert any(p.var == "AUTH_TRUST_PROXY" and p.level == "warning" for p in check(env, "api"))
    assert not any(p.var == "AUTH_TRUST_PROXY" for p in check(env, "worker"))
    env["AUTH_TRUST_PROXY"] = "1"
    assert not any(p.var == "AUTH_TRUST_PROXY" for p in check(env, "api"))


def test_dev_stub_fixed_key_is_shared_between_processes():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.auth import StubIssuer

    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()
    a, b = StubIssuer(pem), StubIssuer(pem)
    assert b.verify(a.issue("s1")).subject == "s1"
    import pytest as _pytest

    from app.auth.verifier import AuthError

    with _pytest.raises(AuthError):
        StubIssuer().verify(a.issue("s1"))
