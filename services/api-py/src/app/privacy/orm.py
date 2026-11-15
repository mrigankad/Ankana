"""Session hooks: before any ORM statement or flush, make sure the practice's
keys are loaded and set the crypto scope from session.info["practice_id"]
(stamped by app.tenancy.session.bind_practice)."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session

from . import crypto


def prepare(session: Session, create: bool) -> None:
    pid = session.info.get("practice_id")
    crypto.set_scope(pid)
    if pid and crypto.store.peek(pid) is None:
        crypto.store.load(session.connection(), pid, create=create)


@event.listens_for(Session, "do_orm_execute")
def _on_execute(state) -> None:
    prepare(state.session, create=False)


@event.listens_for(Session, "before_flush")
def _on_flush(session, flush_context, instances) -> None:
    prepare(session, create=True)
