"""Production startup preflight: `python -m app.preflight [--role api|worker|migrate]`.

Validates every environment variable a production container needs and exits 1 with
the complete list of problems (not just the first), so a misconfigured revision
fails before it takes traffic. It never prints a value, only variable names and
what is wrong with them.

Used three ways (see docs/deploy.md):
  * the image entrypoint runs it when ANKANA_ROLE is set (container exits at once),
  * GET /health/ready runs it and is the Container Apps readiness probe,
  * deploy.yml runs it as the `preflight` Container Apps job before the api, worker
    and web revisions are rolled out.

A Key Vault placeholder is a single space, so whitespace-only counts as unset.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

ROLES = ("api", "worker", "migrate")
MIN_SECRET = 24  # matches ankana_ai.connections.MIN_PRODUCTION_SECRET_LENGTH
EPHE_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")
TRUTHY = {"1", "true", "yes", "on"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


@dataclass(frozen=True)
class Problem:
    var: str
    message: str
    level: str = "error"  # error | warning

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.var}: {self.message}"


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class _Checker:
    def __init__(self, env: Mapping[str, str], role: str,
                 has_module: Callable[[str], bool]) -> None:
        self.env, self.role, self.has_module = env, role, has_module
        self.problems: list[Problem] = []

    # ---------------------------------------------------------------- helpers
    def get(self, name: str, default: str = "") -> str:
        return (self.env.get(name) or "").strip() or default

    def err(self, var: str, msg: str) -> None:
        self.problems.append(Problem(var, msg))

    def warn(self, var: str, msg: str) -> None:
        self.problems.append(Problem(var, msg, "warning"))

    def flag(self, name: str) -> bool:
        return self.get(name).lower() in TRUTHY

    def require(self, name: str, why: str = "is required") -> str:
        val = self.get(name)
        if not val:
            self.err(name, why)
        return val

    def secret(self, name: str, minimum: int = MIN_SECRET) -> None:
        val = self.require(name)
        if val and len(val) < minimum:
            self.err(name, f"must be {minimum}+ random characters (got {len(val)})")

    def https_url(self, name: str, *, public: bool = True) -> str:
        val = self.require(name)
        if not val:
            return ""
        u = urlparse(val)
        if u.scheme != "https" or not u.hostname:
            self.err(name, "must be an https:// URL")
        elif public and u.hostname in LOCAL_HOSTS:
            self.err(name, "must be the public hostname, not localhost")
        return val

    def module(self, mod: str, needed_for: str) -> None:
        if not self.has_module(mod):
            self.err("image", f"python package {mod!r} is missing from the image "
                              f"(needed for {needed_for})")

    # ----------------------------------------------------------------- groups
    def common(self) -> None:
        if self.get("API_ENV") != "production":
            self.err("API_ENV", "must be 'production'")
        db = self.require("API_DATABASE_URL")
        if db and not db.startswith("postgresql"):
            self.err("API_DATABASE_URL", "must be a postgresql+psycopg:// URL")
        self.secret("ANKANA_SECRET_KEY")
        self.master_key()
        self.secret("NOTIFY_LINK_SECRET")
        self.https_url("NOTIFY_PUBLIC_BASE_URL")
        self.storage()
        self.ephemeris()
        self.ai()
        self.billing()
        self.notify_channels()
        if self.flag("AUTH_DEV_STUB"):
            self.err("AUTH_DEV_STUB", "must be off in production")
        if self.flag("ANKANA_LEGACY_API"):
            self.err("ANKANA_LEGACY_API", "the unauthenticated legacy API must stay off")
        if self.get("ANKANA_GIT_SHA", "unknown") == "unknown":
            self.warn("ANKANA_GIT_SHA", "not set; /v1/meta cannot point at the running source")
        if not self.get("ANKANA_SOURCE_URL"):
            self.warn("ANKANA_SOURCE_URL", "not set; the AGPL source link would be missing")
        if not self.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
            self.warn("APPLICATIONINSIGHTS_CONNECTION_STRING", "not set; no traces or metrics")
        elif self.get("ANKANA_METRICS", "1") != "0":
            # Metrics (app/metrics.py) and the alert rules in infra/monitoring need the exporter.
            self.module("opentelemetry.sdk.metrics", "metrics export (pip extra 'observability')")
            self.module("azure.monitor.opentelemetry.exporter", "Application Insights export")
        if self.role == "api" and not self.flag("AUTH_TRUST_PROXY"):
            self.warn("AUTH_TRUST_PROXY", "not set; behind the ingress every caller shares the "
                      "proxy address, so the per-IP rate limits (public links, location search, "
                      "sign-in) act as one global bucket")
        self.module("psycopg", "Postgres")

    def master_key(self) -> None:
        if self.get("ANKANA_KEYVAULT_KEY_ID"):
            self.module("azure.keyvault.keys", "ANKANA_KEYVAULT_KEY_ID")
            self.module("azure.identity", "ANKANA_KEYVAULT_KEY_ID")
            return
        raw = self.get("ANKANA_MASTER_KEY")
        if not raw:
            self.err("ANKANA_MASTER_KEY", "is required (base64 of 32 random bytes) unless "
                                          "ANKANA_KEYVAULT_KEY_ID is set")
            return
        self._b64_32("ANKANA_MASTER_KEY", raw)
        for part in filter(None, (p.strip() for p in self.get("ANKANA_MASTER_KEY_PREVIOUS").split(","))):
            _, sep, val = part.partition(":")
            if not sep:
                self.err("ANKANA_MASTER_KEY_PREVIOUS", "entries must look like 'id:base64'")
            else:
                self._b64_32("ANKANA_MASTER_KEY_PREVIOUS", val)

    def _b64_32(self, var: str, raw: str) -> None:
        try:
            ok = len(base64.b64decode(raw + "=" * (-len(raw) % 4), validate=True)) == 32
        except ValueError:
            ok = False
        if not ok:
            self.err(var, "must be base64 of exactly 32 bytes (openssl rand -base64 32)")

    def storage(self) -> None:
        backend = self.get("STORAGE_BACKEND", "local").lower()
        if backend == "azure":
            if not (self.get("AZURE_STORAGE_ACCOUNT_URL") or self.get("AZURE_STORAGE_CONNECTION_STRING")):
                self.err("AZURE_STORAGE_ACCOUNT_URL", "is required when STORAGE_BACKEND=azure")
            if not self.get("AZURE_STORAGE_CONTAINER"):
                self.err("AZURE_STORAGE_CONTAINER", "is required when STORAGE_BACKEND=azure")
            self.module("azure.storage.blob", "STORAGE_BACKEND=azure")
            if not self.get("AZURE_STORAGE_CONNECTION_STRING"):
                self.module("azure.identity", "managed-identity storage access")
                if not self.get("AZURE_CLIENT_ID"):
                    self.err("AZURE_CLIENT_ID", "is required so DefaultAzureCredential picks the "
                                                "user-assigned managed identity")
        elif backend == "local":
            self.secret("STORAGE_SIGNING_KEY")
            if not self.flag("PREFLIGHT_ALLOW_LOCAL_STORAGE"):
                self.err("STORAGE_BACKEND", "'local' keeps files on one container's disk, so reports "
                                            "made by the worker are invisible to the api; use 'azure'")
        else:
            self.err("STORAGE_BACKEND", f"unknown value {backend!r} (local|azure)")

    def ephemeris(self) -> None:
        if self.get("ANKANA_EPHEMERIS").lower() != "swiss":
            self.err("ANKANA_EPHEMERIS", "must be 'swiss' in production")
        self.module("swisseph", "ANKANA_EPHEMERIS=swiss")
        path = self.get("ANKANA_SE_EPHE_PATH")
        if not path:
            self.err("ANKANA_SE_EPHE_PATH", "is required (without it pyswisseph silently "
                                            "falls back to the Moshier ephemeris)")
        else:
            missing = [f for f in EPHE_FILES if not os.path.isfile(os.path.join(path, f))]
            if missing:
                self.err("ANKANA_SE_EPHE_PATH", f"missing data files in {path}: {', '.join(missing)}")

    def ai(self) -> None:
        if self.flag("ANKANA_ALLOW_LOCAL_PROVIDERS"):
            self.err("ANKANA_ALLOW_LOCAL_PROVIDERS", "must be 0 in a hosted deployment "
                                                     "(it lets tenants run local CLIs)")
        provider = self.get("ANKANA_AI_PROVIDER").lower()
        key = self.get("ANTHROPIC_API_KEY")
        if provider in ("", "anthropic"):
            if not key and provider == "anthropic":
                self.err("ANTHROPIC_API_KEY", "is required when ANKANA_AI_PROVIDER=anthropic")
            elif not key:
                self.warn("ANTHROPIC_API_KEY", "not set; the AI assistant and AI readings are "
                                               "disabled until it is (az keyvault secret)")
        elif provider == "ollama":
            if not self.get("OLLAMA_BASE_URL"):
                self.err("OLLAMA_BASE_URL", "is required when ANKANA_AI_PROVIDER=ollama")
        else:
            self.err("ANKANA_AI_PROVIDER", f"{provider!r} is not allowed in production "
                                           "(anthropic or ollama)")

    def billing(self) -> None:
        if self.get("ANKANA_BILLING", "off").lower() not in TRUTHY:
            return
        for var in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"):
            self.require(var, "is required when ANKANA_BILLING=on")
        if self.get("ANKANA_BILLING_PROVIDER", "razorpay").lower() != "razorpay":
            self.err("ANKANA_BILLING_PROVIDER", "must be 'razorpay' when billing is on "
                                                "(the mock provider takes no money)")
        name = self.get("ANKANA_SUPPLIER_NAME")
        if not name or "to be set" in name:
            self.err("ANKANA_SUPPLIER_NAME", "must be the legal name that appears on invoices")
        if len(self.get("ANKANA_SUPPLIER_GSTIN")) != 15:
            self.err("ANKANA_SUPPLIER_GSTIN", "must be a 15 character GSTIN")
        code = self.get("ANKANA_SUPPLIER_STATE_CODE")
        if not (code.isdigit() and len(code) == 2):
            self.err("ANKANA_SUPPLIER_STATE_CODE", "must be the 2 digit GST state code")
        self.require("ANKANA_SUPPLIER_ADDRESS")
        if "@" not in self.get("ANKANA_SUPPLIER_EMAIL"):
            self.err("ANKANA_SUPPLIER_EMAIL", "must be an email address")

    def notify_channels(self) -> None:
        backend = self.get("NOTIFY_EMAIL_BACKEND", "console").lower()
        if backend == "acs":
            self.require("ACS_CONNECTION_STRING", "is required when NOTIFY_EMAIL_BACKEND=acs")
            sender = self.require("ACS_EMAIL_FROM", "is required when NOTIFY_EMAIL_BACKEND=acs")
            if sender and "@" not in sender:
                self.err("ACS_EMAIL_FROM", "must be a verified sender address")
            self.module("azure.communication.email", "NOTIFY_EMAIL_BACKEND=acs")
        elif backend == "smtp":
            self.require("SMTP_HOST", "is required when NOTIFY_EMAIL_BACKEND=smtp")
            self.require("NOTIFY_EMAIL_FROM", "is required when NOTIFY_EMAIL_BACKEND=smtp")
        else:
            self.err("NOTIFY_EMAIL_BACKEND", "must be 'acs' or 'smtp'; 'console' only logs "
                                             "reminders and never delivers them")
        for kind in ("whatsapp", "sms"):
            var = f"NOTIFY_{kind.upper()}_BACKEND"
            if self.get(var, "console").lower() == "console":
                self.warn(var, f"{kind} reminders are only logged (no real adapter ships yet)")

    def auth(self) -> None:
        self.signing_key()
        issuer = self.https_url("AUTH_BUILTIN_ISSUER")
        web = self.https_url("AUTH_WEB_BASE_URL")
        origins = [o.strip().rstrip("/") for o in self.get("AUTH_ALLOWED_ORIGINS").split(",") if o.strip()]
        if not origins:
            self.err("AUTH_ALLOWED_ORIGINS", "is required (comma separated https web origins)")
        for o in origins:
            u = urlparse(o)
            if u.scheme != "https" or not u.hostname or u.hostname in LOCAL_HOSTS:
                self.err("AUTH_ALLOWED_ORIGINS", f"origin {o!r} must be a public https origin")
        if web and origins and web.rstrip("/") not in origins:
            self.err("AUTH_ALLOWED_ORIGINS", "must include AUTH_WEB_BASE_URL")
        if self.get("AUTH_COOKIE_SECURE").lower() in ("0", "false", "no", "off"):
            self.err("AUTH_COOKIE_SECURE", "must not be disabled in production")
        if not self.flag("AUTH_TRUST_PROXY"):
            self.warn("AUTH_TRUST_PROXY", "off: behind Container Apps ingress every client "
                                          "shares one rate-limit bucket (set 1)")
        suffix = ".azurecontainerapps.io"
        if issuer and web and urlparse(issuer).hostname.endswith(suffix) \
                and urlparse(web).hostname.endswith(suffix):
            self.warn("AUTH_BUILTIN_ISSUER", "web and api are on default azurecontainerapps.io "
                                             "hosts, which are cross-site; the SameSite=Lax "
                                             "refresh cookie will not be sent. Use custom domains "
                                             "under one registrable domain")
        mailer = self.get("AUTH_MAILER", "console").lower()
        if mailer == "acs":
            conn = self.require("ACS_EMAIL_CONNECTION_STRING", "is required when AUTH_MAILER=acs")
            if conn:
                parts = dict(p.split("=", 1) for p in conn.split(";") if "=" in p)
                if not parts.get("endpoint") or not parts.get("accesskey"):
                    self.err("ACS_EMAIL_CONNECTION_STRING", "must look like "
                                                            "endpoint=https://...;accesskey=...")
        elif mailer == "smtp":
            self.require("SMTP_HOST", "is required when AUTH_MAILER=smtp")
        else:
            self.err("AUTH_MAILER", "must be 'acs' or 'smtp' ('console' is refused in production)")
        sender = self.get("AUTH_MAIL_FROM")
        if not sender or "localhost" in sender:
            self.err("AUTH_MAIL_FROM", "must be a verified sender, e.g. 'Ankana <no-reply@your.domain>'")
        if self.get("AUTH_SMS", "console").lower() == "console":
            self.warn("AUTH_SMS", "console is ignored in production: phone sign-in codes are disabled")
        for pid in filter(None, (p.strip().lower() for p in self.get("AUTH_OIDC_PROVIDERS").split(","))):
            key = "AUTH_OIDC_" + pid.upper().replace("-", "_")
            if not (self.get(key + "_ISSUER") and self.get(key + "_CLIENT_ID")):
                self.warn(key + "_ISSUER", f"provider {pid!r} is listed but incomplete, so it is hidden")
            elif not self.get(key + "_CLIENT_SECRET"):
                self.warn(key + "_CLIENT_SECRET", f"provider {pid!r} has no client secret (public client?)")

    def signing_key(self) -> None:
        pem = self.get("AUTH_SIGNING_KEY_PEM")
        path = self.get("AUTH_SIGNING_KEY_FILE")
        if not pem and not path:
            self.err("AUTH_SIGNING_KEY_PEM", "is required (Ed25519 PKCS8 PEM; "
                                             "see docs/deploy.md for the openssl command)")
            return
        if not pem:
            if not os.path.isfile(path):
                self.err("AUTH_SIGNING_KEY_FILE", "file does not exist")
                return
            with open(path, encoding="utf-8") as fh:
                pem = fh.read()
        self._ed25519("AUTH_SIGNING_KEY_PEM", pem)
        prev = self.get("AUTH_SIGNING_KEY_PREVIOUS_PEM")
        if prev:
            self._ed25519("AUTH_SIGNING_KEY_PREVIOUS_PEM", prev)

    def _ed25519(self, var: str, pem: str) -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        try:
            key = serialization.load_pem_private_key(pem.replace("\\n", "\n").encode(), password=None)
        except Exception:
            self.err(var, "is not a valid unencrypted PEM private key")
            return
        if not isinstance(key, Ed25519PrivateKey):
            self.err(var, "must be an Ed25519 key (openssl genpkey -algorithm ed25519)")

    def worker(self) -> None:
        for var, default in (("NOTIFY_TICK_SECONDS", "300"), ("WORKER_CONCURRENCY", "2")):
            raw = self.get(var, default)
            if not (raw.isdigit() and int(raw) >= 1):
                self.err(var, "must be a positive integer")
        self.module("playwright", "PDF reports")

    def migrate(self) -> None:
        url = self.require("API_MIGRATION_URL")
        if url and not url.startswith("postgresql"):
            self.err("API_MIGRATION_URL", "must be a postgresql+psycopg:// URL")
        self.secret("APP_ROLE_PASSWORD", 16)
        # Data migrations (0004 and 0006) encrypt existing rows in place. Without the master key
        # they would stop, or worse, wrap new practice keys under the public development key.
        self.master_key()
        if self.get("API_ENV") != "production":
            self.err("API_ENV", "must be 'production' so the migration never uses the dev key")


def check(env: Mapping[str, str] | None = None, role: str = "api", *,
          has_module: Callable[[str], bool] = _has_module) -> list[Problem]:
    """All problems for `role`, errors and warnings. Empty list means ready."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    c = _Checker(os.environ if env is None else env, role, has_module)
    if role == "migrate":
        c.migrate()
    else:
        c.common()
        if role == "api":
            c.auth()
        else:
            c.worker()
    return c.problems


def errors(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.level == "error"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.preflight", description=__doc__.split("\n")[0])
    parser.add_argument("--role", choices=ROLES, default=os.getenv("ANKANA_ROLE") or "api")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)
    problems = check(role=args.role)
    bad = errors(problems) if not args.strict else problems
    for p in problems:
        print(p, file=sys.stderr if p in bad else sys.stdout)
    if bad:
        print(f"preflight FAILED for role {args.role}: {len(bad)} problem(s)", file=sys.stderr)
        return 1
    print(f"preflight ok for role {args.role} ({len(problems)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
