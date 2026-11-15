"""Settings for the built-in identity provider, read from the environment.

Everything is optional in dev: keys are generated into a gitignored file, codes
print to the API console and the web origin defaults to localhost:3000.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

BUILTIN_ISSUER_KEY = "ankana"  # user_account.issuer for built-in users (stable across URL changes)
AUDIENCE = "ankana-api"


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class OidcProvider:
    id: str
    label: str
    issuer: str
    client_id: str
    client_secret: str | None
    scopes: str = "openid email profile"


@dataclass(frozen=True)
class AuthConfig:
    env: str = "dev"
    issuer_url: str = "http://127.0.0.1:3001"
    web_base_url: str = "http://localhost:3000"
    allowed_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    signing_key_pem: str | None = None
    signing_key_file: str | None = None
    previous_key_pem: str | None = None
    dev_key_path: str = ".auth-dev/signing-key.pem"
    access_ttl_seconds: int = 900
    refresh_ttl_days: int = 30
    refresh_absolute_days: int = 90
    cookie_secure: bool = False
    cookie_domain: str | None = None
    cookie_name: str = "ankana_rt"
    password_enabled: bool = True
    signup_enabled: bool = True
    password_min_length: int = 10
    password_hibp: bool = False
    # Codes
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_resend_seconds: int = 30
    # Brute-force limits (rolling windows, counted from auth_event)
    otp_requests_per_email_hour: int = 5
    otp_requests_per_ip_hour: int = 30
    failures_per_email_window: int = 8
    failures_per_ip_window: int = 40
    failure_window_seconds: int = 900
    invite_ttl_days: int = 7
    trust_proxy: bool = False  # take the client IP from the last X-Forwarded-For hop
    mailer: str = "console"
    mail_from: str = "Ankana <no-reply@localhost>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    acs_connection_string: str | None = None
    sms: str = "console"
    oidc: tuple[OidcProvider, ...] = field(default_factory=tuple)

    @property
    def production(self) -> bool:
        return self.env == "production"

    def oidc_provider(self, provider_id: str) -> OidcProvider | None:
        return next((p for p in self.oidc if p.id == provider_id), None)

    @classmethod
    def from_env(cls) -> AuthConfig:
        env = os.getenv("API_ENV", "dev")
        issuer = os.getenv("AUTH_BUILTIN_ISSUER", cls.issuer_url).rstrip("/")
        origins = os.getenv("AUTH_ALLOWED_ORIGINS")
        web = os.getenv("AUTH_WEB_BASE_URL", cls.web_base_url).rstrip("/")
        providers = []
        names = (x.strip().lower() for x in os.getenv("AUTH_OIDC_PROVIDERS", "").split(","))
        for pid in filter(None, names):
            key = "AUTH_OIDC_" + pid.upper().replace("-", "_")
            issuer_url, client_id = os.getenv(key + "_ISSUER"), os.getenv(key + "_CLIENT_ID")
            if not issuer_url or not client_id:
                continue  # half-configured providers are hidden, not half-working
            providers.append(OidcProvider(
                id=pid, label=os.getenv(key + "_LABEL", pid.capitalize()),
                issuer=issuer_url.rstrip("/"), client_id=client_id,
                client_secret=os.getenv(key + "_CLIENT_SECRET"),
                scopes=os.getenv(key + "_SCOPES", "openid email profile")))
        return cls(
            env=env, issuer_url=issuer, web_base_url=web,
            allowed_origins=(
                tuple(o.strip().rstrip("/") for o in origins.split(",") if o.strip())
                if origins else (web, "http://127.0.0.1:3000")),
            signing_key_pem=os.getenv("AUTH_SIGNING_KEY_PEM"),
            signing_key_file=os.getenv("AUTH_SIGNING_KEY_FILE"),
            previous_key_pem=os.getenv("AUTH_SIGNING_KEY_PREVIOUS_PEM"),
            dev_key_path=os.getenv("AUTH_DEV_KEY_PATH", cls.dev_key_path),
            access_ttl_seconds=_int("AUTH_ACCESS_TTL_SECONDS", 900),
            refresh_ttl_days=_int("AUTH_REFRESH_TTL_DAYS", 30),
            refresh_absolute_days=_int("AUTH_REFRESH_ABSOLUTE_DAYS", 90),
            cookie_secure=_flag("AUTH_COOKIE_SECURE", issuer.startswith("https://") or env == "production"),
            cookie_domain=os.getenv("AUTH_COOKIE_DOMAIN") or None,
            password_enabled=_flag("AUTH_PASSWORD_ENABLED", True),
            signup_enabled=_flag("AUTH_SIGNUP_ENABLED", True),
            password_min_length=_int("AUTH_PASSWORD_MIN_LENGTH", 10),
            password_hibp=_flag("AUTH_PASSWORD_HIBP", False),
            invite_ttl_days=_int("AUTH_INVITE_TTL_DAYS", 7),
            trust_proxy=_flag("AUTH_TRUST_PROXY", False),
            mailer=os.getenv("AUTH_MAILER", "console").lower(),
            mail_from=os.getenv("AUTH_MAIL_FROM", cls.mail_from),
            smtp_host=os.getenv("SMTP_HOST"), smtp_port=_int("SMTP_PORT", 587),
            smtp_user=os.getenv("SMTP_USER"), smtp_password=os.getenv("SMTP_PASSWORD"),
            smtp_starttls=_flag("SMTP_STARTTLS", True),
            acs_connection_string=os.getenv("ACS_EMAIL_CONNECTION_STRING"),
            sms=os.getenv("AUTH_SMS", "console").lower(),
            oidc=tuple(providers),
        )
