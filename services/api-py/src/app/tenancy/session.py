"""Tenant-scoped database sessions.

`tenant_session` opens a transaction, binds app.practice_id for its lifetime
(transaction-local, so pooled connections never leak a tenant) and commits or
rolls back on exit.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def make_pg_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, future=True)


def bind_practice(session: Session, practice_id: UUID | str) -> None:
    from app.observability import set_practice

    set_practice(practice_id)  # tag logs and the current span; never PII
    session.info["practice_id"] = str(practice_id)  # read by app.privacy.orm (field keys)
    # set_config(..., true) == SET LOCAL, but accepts a bind parameter.
    session.execute(
        text("SELECT set_config('app.practice_id', :pid, true)"), {"pid": str(practice_id)}
    )


@contextmanager
def tenant_session(engine: Engine, practice_id: UUID | str) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            bind_practice(session, practice_id)
            yield session


@contextmanager
def global_session(engine: Engine) -> Iterator[Session]:
    """For global tables only (user_account) and the membership function."""
    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            yield session
