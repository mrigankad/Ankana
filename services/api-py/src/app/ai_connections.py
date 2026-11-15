"""Per-practice AI connections: build the provider chain for a role, record usage.

The chain is [routed connection, then every other enabled connection by creation time].
Local-machine kinds are skipped unless ANKANA_ALLOW_LOCAL_PROVIDERS=1.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ankana_ai.connections import (
    ChainEntry,
    ConnView,
    FallbackProvider,
    TieredProvider,
    build_provider,
    decrypt_key,
    kind_allowed,
    merged_models,
)
from app.tenancy.models import AiConnection, AiRouting
from app.tenancy.session import tenant_session

log = logging.getLogger("ankana.ai")


def stored_models(c: AiConnection) -> dict[str, str | None]:
    return {"top": c.model_top, "strong": c.model_strong, "fast": c.model_fast}


def conn_view(c: AiConnection) -> ConnView:
    return ConnView(id=str(c.id), kind=c.kind, enabled=c.enabled, base_url=c.base_url,
                    models=merged_models(c.kind, stored_models(c)))


def entry_for(c: AiConnection, forced_model: str | None = None) -> ChainEntry:
    provider = build_provider(c.kind, base_url=c.base_url, api_key=decrypt_key(c.api_key_enc),
                              models=stored_models(c))  # type: ignore[arg-type]
    models = merged_models(c.kind, stored_models(c))
    return ChainEntry(c.kind, str(c.id), TieredProvider(provider, models, forced_model))


def chain_for_role(db: Session, role: str) -> FallbackProvider | None:
    """None when the practice has no usable connection (caller falls back to the server default)."""
    conns = [c for c in db.scalars(select(AiConnection).order_by(
        AiConnection.created_at, AiConnection.id)) if c.enabled and kind_allowed(c.kind)]
    if not conns:
        return None
    route = db.scalar(select(AiRouting).where(AiRouting.role == role))
    if route is not None:
        conns.sort(key=lambda c: c.id != route.connection_id)  # stable: routed one first
    entries: list[ChainEntry] = []
    for c in conns:
        try:
            forced = route.model if route is not None and c.id == route.connection_id else None
            entries.append(entry_for(c, forced))
        except Exception as exc:  # undecryptable key, bad kind: skip, the rest still serve
            log.warning("ai connection %s skipped: %s", c.id, exc)
    return FallbackProvider(entries) if entries else None


def record_usage(engine, practice_id: uuid.UUID, chain: FallbackProvider) -> None:
    """One counter pair per provider kind: ai_calls:<kind> and ai_tokens:<kind>."""
    from app.v1.common import bump_usage

    if not chain.usage_by_kind:
        return
    with tenant_session(engine, practice_id) as db:
        for kind, u in chain.usage_by_kind.items():
            bump_usage(db, practice_id, f"ai_calls:{kind}", u["calls"])
            if u["tokens"]:
                bump_usage(db, practice_id, f"ai_tokens:{kind}", u["tokens"])
