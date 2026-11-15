"""/v1/ai: provider kinds, connections (keys write-only) and per-role routing.

Owners write; staff read. API keys are encrypted with ANKANA_SECRET_KEY and are never returned.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ankana_ai import connections as cx
from ankana_ai.config import HAIKU
from ankana_ai.llm_providers import valid_model
from ankana_ai.providers import ProviderRequest
from ankana_ai.tools import SUBMIT_TOOL
from app.ai_connections import conn_view, entry_for, stored_models
from app.auth import CurrentMember, require_roles, tenant_db
from app.tenancy.models import AiConnection, AiRouting, Role

from .common import STAFF, ProblemError, audit

router = APIRouter(prefix="/ai")
OWNER = (Role.owner,)


# ------------------------------------------------------------------ schemas
class Models(BaseModel):
    top: str | None = Field(default=None, max_length=120)
    strong: str | None = Field(default=None, max_length=120)
    fast: str | None = Field(default=None, max_length=120)

    @field_validator("top", "strong", "fast")
    @classmethod
    def _safe(cls, v: str | None) -> str | None:
        if v and not valid_model(v):
            raise ValueError("model names may use letters, digits and . _ : / @ + - only")
        return v


class ProviderKindOut(BaseModel):
    kind: str
    label: str
    description: str
    logo: str
    local: bool
    requires_key: bool
    requires_base_url: bool
    default_base_url: str | None
    default_models: dict[str, str]
    available: bool
    allowed: bool
    status: str
    detail: str


class ProvidersOut(BaseModel):
    kinds: list[ProviderKindOut]
    local_providers_allowed: bool
    secret_key_configured: bool
    roles: list[str]
    presets: list[str]


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    label: str
    base_url: str | None
    has_key: bool
    models: Models
    effective_models: dict[str, str]
    enabled: bool
    local: bool
    allowed: bool
    created_at: datetime


class ConnectionIn(BaseModel):
    kind: str
    label: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500, description="Write-only.")
    models: Models = Field(default_factory=Models)
    enabled: bool = True


class ConnectionPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500,
                                description="Write-only. Empty string removes the key.")
    models: Models | None = None
    enabled: bool | None = None


class TestOut(BaseModel):
    ok: bool
    latency_ms: int
    model: str | None = None
    error: str | None = None


class Route(BaseModel):
    role: str
    connection_id: uuid.UUID | None = Field(
        description="Null clears the route (the first enabled connection is used).")
    model: str | None = Field(default=None, max_length=120)

    @field_validator("model")
    @classmethod
    def _safe(cls, v: str | None) -> str | None:
        if v and not valid_model(v):
            raise ValueError("model names may use letters, digits and . _ : / @ + - only")
        return v


class RoutingOut(BaseModel):
    routes: list[Route]
    preset: str | None
    presets: list[str]
    roles: list[str]


class RoutingIn(BaseModel):
    routes: list[Route]


class PresetIn(BaseModel):
    preset: str


# ------------------------------------------------------------------ helpers
def _out(c: AiConnection) -> ConnectionOut:
    return ConnectionOut(
        id=c.id, kind=c.kind, label=c.label, base_url=c.base_url,
        has_key=bool(c.api_key_enc), models=Models(**stored_models(c)),
        effective_models=cx.merged_models(c.kind, stored_models(c)), enabled=c.enabled,
        local=c.kind in cx.LOCAL_KINDS, allowed=cx.kind_allowed(c.kind), created_at=c.created_at)


def _get(db: Session, connection_id: uuid.UUID) -> AiConnection:
    c = db.scalar(select(AiConnection).where(AiConnection.id == connection_id))
    if c is None:
        raise ProblemError(404, "connection not found", "not_found")
    return c


def _check_kind(kind: str) -> cx.KindInfo:
    info = cx.KINDS.get(kind)
    if info is None:
        raise ProblemError(422, f"unknown provider kind '{kind}'", "unknown_provider_kind")
    if not cx.kind_allowed(kind):
        raise ProblemError(
            403, "Local-machine providers are disabled on this server "
                 "(set ANKANA_ALLOW_LOCAL_PROVIDERS=1 on a self-hosted install).",
            "local_provider_disabled")
    return info


def _clean_url(url: str | None, kind: str) -> str | None:
    try:
        return cx.validate_base_url(url, kind)
    except ValueError as e:
        raise ProblemError(422, str(e), "invalid_base_url") from e


def _encrypt(key: str) -> str:
    if not cx.secret_key_configured():
        raise ProblemError(503, "ANKANA_SECRET_KEY is not set on the server; API keys cannot be "
                                "stored.", "secret_key_missing")
    return cx.encrypt_key(key)


def _routing_out(db: Session) -> RoutingOut:
    rows = list(db.scalars(select(AiRouting).order_by(AiRouting.role)))
    presets = {r.preset for r in rows}
    return RoutingOut(
        routes=[Route(role=r.role, connection_id=r.connection_id, model=r.model) for r in rows],
        preset=presets.pop() if len(presets) == 1 and len(rows) == len(cx.ROLES) else None,
        presets=list(cx.PRESETS), roles=list(cx.ROLES))


# ---------------------------------------------------------------- providers
@router.get("/providers", response_model=ProvidersOut, tags=["ai"], operation_id="listAiProviders",
            summary="Provider kinds with availability on this server")
def list_providers(m: CurrentMember = Depends(require_roles(*STAFF))) -> ProvidersOut:
    kinds = [ProviderKindOut(
        kind=i.kind, label=i.label, description=i.description, logo=i.logo, local=i.local,
        requires_key=i.requires_key, requires_base_url=i.requires_base_url,
        default_base_url=i.default_base_url, default_models=i.default_models,
        **{k: v for k, v in cx.availability(i.kind).items() if k != "models"})
        for i in cx.KINDS.values()]
    return ProvidersOut(kinds=kinds, local_providers_allowed=cx.local_providers_allowed(),
                        secret_key_configured=cx.secret_key_configured(),
                        roles=list(cx.ROLES), presets=list(cx.PRESETS))


# -------------------------------------------------------------- connections
@router.get("/connections", response_model=list[ConnectionOut], tags=["ai"],
            operation_id="listAiConnections", summary="This practice's AI connections")
def list_connections(m: CurrentMember = Depends(require_roles(*STAFF)),
                     db: Session = Depends(tenant_db, scope="function")) -> list[ConnectionOut]:
    rows = db.scalars(select(AiConnection).order_by(AiConnection.created_at, AiConnection.id))
    return [_out(c) for c in rows]


@router.post("/connections", status_code=201, response_model=ConnectionOut, tags=["ai"],
             operation_id="createAiConnection", summary="Add a connection (owner only)")
def create_connection(body: ConnectionIn, request: Request,
                      m: CurrentMember = Depends(require_roles(*OWNER)),
                      db: Session = Depends(tenant_db, scope="function")) -> ConnectionOut:
    info = _check_kind(body.kind)
    if info.requires_key and not body.api_key:
        raise ProblemError(422, f"{info.label} needs an API key.", "api_key_required")
    base_url = _clean_url(body.base_url, body.kind) if body.base_url else None
    if info.requires_base_url and not (base_url or info.default_base_url):
        raise ProblemError(422, f"{info.label} needs a base URL.", "base_url_required")
    c = AiConnection(
        practice_id=m.practice_id, kind=body.kind, label=body.label.strip(), base_url=base_url,
        api_key_enc=_encrypt(body.api_key) if body.api_key else None,
        model_top=body.models.top or None, model_strong=body.models.strong or None,
        model_fast=body.models.fast or None, enabled=body.enabled)
    db.add(c)
    try:
        db.flush()
    except IntegrityError as e:
        raise ProblemError(409, "a connection with that label already exists",
                           "duplicate_label") from e
    audit(db, m, "ai_connection.created", "ai_connection", c.id, request, {"kind": c.kind})
    return _out(c)


@router.patch("/connections/{connection_id}", response_model=ConnectionOut, tags=["ai"],
              operation_id="updateAiConnection", summary="Edit a connection (owner only)")
def update_connection(connection_id: uuid.UUID, body: ConnectionPatch, request: Request,
                      m: CurrentMember = Depends(require_roles(*OWNER)),
                      db: Session = Depends(tenant_db, scope="function")) -> ConnectionOut:
    c = _get(db, connection_id)
    _check_kind(c.kind)
    fields = body.model_fields_set
    if "label" in fields and body.label:
        c.label = body.label.strip()
    if "base_url" in fields:
        c.base_url = _clean_url(body.base_url, c.kind) if body.base_url else None
    if "api_key" in fields:
        c.api_key_enc = _encrypt(body.api_key) if body.api_key else None
    if body.models is not None:
        c.model_top, c.model_strong, c.model_fast = (
            body.models.top or None, body.models.strong or None, body.models.fast or None)
    if body.enabled is not None:
        c.enabled = body.enabled
    try:
        db.flush()
    except IntegrityError as e:
        raise ProblemError(409, "a connection with that label already exists",
                           "duplicate_label") from e
    audit(db, m, "ai_connection.updated", "ai_connection", c.id, request,
          {"kind": c.kind, "fields": sorted(fields - {"api_key"}),
           "key_changed": "api_key" in fields})
    return _out(c)


@router.delete("/connections/{connection_id}", status_code=204, tags=["ai"],
               operation_id="deleteAiConnection",
               summary="Delete a connection and its stored key (owner only)")
def delete_connection(connection_id: uuid.UUID, request: Request,
                      m: CurrentMember = Depends(require_roles(*OWNER)),
                      db: Session = Depends(tenant_db, scope="function")) -> None:
    c = _get(db, connection_id)
    audit(db, m, "ai_connection.deleted", "ai_connection", c.id, request, {"kind": c.kind})
    db.execute(delete(AiConnection).where(AiConnection.id == connection_id))


@router.post("/connections/{connection_id}/test", response_model=TestOut, tags=["ai"],
             operation_id="testAiConnection",
             summary="Send a tiny prompt through the connection (owner only)")
def test_connection(connection_id: uuid.UUID,
                    m: CurrentMember = Depends(require_roles(*OWNER)),
                    db: Session = Depends(tenant_db, scope="function")) -> TestOut:
    c = _get(db, connection_id)
    _check_kind(c.kind)
    key = None
    started = time.monotonic()
    try:
        key = cx.decrypt_key(c.api_key_enc)
        provider = entry_for(c).provider
        resp = provider.complete(ProviderRequest(
            model=HAIKU, system="This is a connection test. Be brief.", chart_context="",
            messages=[{"role": "user", "content": "Reply with the single word ok."}],
            tools=[{"name": SUBMIT_TOOL, "description": "Deliver the reply as text.",
                    "input_schema": {"type": "object",
                                     "properties": {"text": {"type": "string"}}}}],
            max_tokens=256))
        ok = bool(resp.content)
        return TestOut(ok=ok, latency_ms=int((time.monotonic() - started) * 1000),
                       model=resp.model or None,
                       error=None if ok else "The model returned nothing.")
    except Exception as e:
        return TestOut(ok=False, latency_ms=int((time.monotonic() - started) * 1000),
                       error=cx.redact(str(e), key)[:300])


# ------------------------------------------------------------------ routing
@router.get("/routing", response_model=RoutingOut, tags=["ai"], operation_id="getAiRouting",
            summary="Role to connection routing")
def get_routing(m: CurrentMember = Depends(require_roles(*STAFF)),
                db: Session = Depends(tenant_db, scope="function")) -> RoutingOut:
    return _routing_out(db)


@router.put("/routing", response_model=RoutingOut, tags=["ai"], operation_id="setAiRouting",
            summary="Set routes for the listed roles (owner only)")
def set_routing(body: RoutingIn, request: Request,
                m: CurrentMember = Depends(require_roles(*OWNER)),
                db: Session = Depends(tenant_db, scope="function")) -> RoutingOut:
    roles = [r.role for r in body.routes]
    if len(set(roles)) != len(roles) or any(r not in cx.ROLES for r in roles):
        raise ProblemError(422, f"roles must be unique and one of {', '.join(cx.ROLES)}",
                           "invalid_role")
    for r in body.routes:
        db.execute(delete(AiRouting).where(AiRouting.role == r.role))
        if r.connection_id is None:
            continue
        c = _get(db, r.connection_id)
        _check_kind(c.kind)
        db.add(AiRouting(practice_id=m.practice_id, role=r.role, connection_id=c.id,
                         model=r.model or None, preset=None))
    db.flush()
    audit(db, m, "ai_routing.updated", "ai_routing", m.practice_id, request, {"roles": roles})
    return _routing_out(db)


@router.post("/routing/preset", response_model=RoutingOut, tags=["ai"],
             operation_id="applyAiRoutingPreset",
             summary="Apply best_quality, balanced, lowest_cost or local_only (owner only)")
def apply_preset(body: PresetIn, request: Request,
                 m: CurrentMember = Depends(require_roles(*OWNER)),
                 db: Session = Depends(tenant_db, scope="function")) -> RoutingOut:
    if body.preset not in cx.PRESETS:
        raise ProblemError(422, f"preset must be one of {', '.join(cx.PRESETS)}", "invalid_preset")
    conns = [conn_view(c) for c in db.scalars(select(AiConnection).order_by(
        AiConnection.created_at, AiConnection.id))]
    plan = cx.plan_preset(body.preset, conns)
    if not plan:
        raise ProblemError(409, "No enabled connection fits this preset. Add or enable one first.",
                           "no_eligible_connection")
    db.execute(delete(AiRouting))
    for route in plan:
        db.add(AiRouting(practice_id=m.practice_id, role=route["role"],
                         connection_id=uuid.UUID(route["connection_id"]), model=route["model"],
                         preset=body.preset))
    db.flush()
    audit(db, m, "ai_routing.preset", "ai_routing", m.practice_id, request,
          {"preset": body.preset})
    return _routing_out(db)
