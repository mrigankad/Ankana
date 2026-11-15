"""Alembic env. URL precedence: -x url=..., API_MIGRATION_URL, API_DATABASE_URL.
Migrations must run as the schema owner, not the RLS-bound app role."""

import os

from sqlalchemy import create_engine

from alembic import context
from app.privacy import models as _privacy_models  # noqa: F401
from app.tenancy.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = (
        context.get_x_argument(as_dictionary=True).get("url")
        or os.getenv("API_MIGRATION_URL")
        or os.getenv("API_DATABASE_URL")
    )
    if not url:
        raise RuntimeError("Set API_MIGRATION_URL (owner connection) to run migrations")
    return url


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
