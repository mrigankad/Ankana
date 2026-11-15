"""Environment-driven settings for the tenant/auth layer."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # App-role connection (non-superuser, subject to RLS).
    database_url: str | None = None
    # Owner connection used only by Alembic.
    migration_url: str | None = None
    env: str = "dev"  # dev | test | production
    auth_jwks_url: str | None = None
    auth_issuer: str | None = None
    auth_audience: str | None = None
    auth_algorithms: tuple[str, ...] = field(default=("RS256",))
    auth_dev_stub: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("API_ENV", "dev")
        stub = os.getenv("AUTH_DEV_STUB", "").lower() in {"1", "true", "yes"}
        if stub and env == "production":
            raise RuntimeError("AUTH_DEV_STUB must not be enabled when API_ENV=production")
        return cls(
            database_url=os.getenv("API_DATABASE_URL"),
            migration_url=os.getenv("API_MIGRATION_URL"),
            env=env,
            auth_jwks_url=os.getenv("AUTH_JWKS_URL"),
            auth_issuer=os.getenv("AUTH_ISSUER"),
            auth_audience=os.getenv("AUTH_AUDIENCE"),
            auth_algorithms=tuple(os.getenv("AUTH_ALGORITHMS", "RS256").split(",")),
            auth_dev_stub=stub,
        )
