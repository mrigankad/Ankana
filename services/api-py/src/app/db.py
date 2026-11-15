"""SQLModel persistence mirroring the Prisma schema (apps/api/prisma)."""

import secrets
from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, create_engine


def _cuid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


class Client(SQLModel, table=True):
    id: str = Field(default_factory=lambda: _cuid("cli"), primary_key=True)
    workspaceId: str = "ws_default"
    fullName: str
    preferredName: str | None = None
    email: str | None = None
    phone: str | None = None
    timezone: str | None = None
    createdAt: datetime = Field(default_factory=_now)
    updatedAt: datetime = Field(default_factory=_now)


class BirthRecord(SQLModel, table=True):
    id: str = Field(default_factory=lambda: _cuid("brc"), primary_key=True)
    clientId: str = Field(foreign_key="client.id")
    birthDate: str
    birthTime: str
    timezoneName: str
    placeLabel: str
    locationQueryText: str | None = None
    canonicalLocationName: str | None = None
    latitude: float
    longitude: float
    providerPlaceId: str | None = None
    geocodeProvider: str | None = None
    geocodeConfidence: str | None = None
    createdAt: datetime = Field(default_factory=_now)
    updatedAt: datetime = Field(default_factory=_now)


class ChartRequest(SQLModel, table=True):
    id: str = Field(default_factory=lambda: _cuid("job"), primary_key=True)
    workspaceId: str = "ws_default"
    clientId: str = Field(foreign_key="client.id")
    birthRecordId: str = Field(foreign_key="birthrecord.id")
    astrologySystem: str = "vedic"
    requestedOutputs: str = "chart"
    status: str = "queued"
    error: str | None = None
    createdAt: datetime = Field(default_factory=_now)


class ChartArtifact(SQLModel, table=True):
    id: str = Field(default_factory=lambda: _cuid("art"), primary_key=True)
    chartRequestId: str = Field(foreign_key="chartrequest.id", unique=True)
    artifactJson: str
    engineVersion: str
    createdAt: datetime = Field(default_factory=_now)


class AuditEvent(SQLModel, table=True):
    id: str = Field(default_factory=lambda: _cuid("aud"), primary_key=True)
    workspaceId: str = "ws_default"
    action: str
    subjectType: str
    subjectId: str
    metaJson: str | None = None
    createdAt: datetime = Field(default_factory=_now)


def make_engine(database_url: str = "sqlite:///data/api.db"):
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if database_url.endswith(":memory:") or database_url == "sqlite://":
        from sqlalchemy.pool import StaticPool

        kwargs["poolclass"] = StaticPool
    else:
        from pathlib import Path

        path = database_url.removeprefix("sqlite:///")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, **kwargs)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session(engine) -> Session:
    return Session(engine)
