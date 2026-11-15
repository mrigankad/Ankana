"""Cross-client reads shared by the client list and the Today feed: latest chart
facts (lagna, Moon sign, running dasha, mini chart), birth-time flags, tags and
consultation timing. Everything runs on the caller's RLS session."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.tenancy.models import (
    BirthRecord,
    ChartArtifact,
    Client,
    ClientTag,
    Consultation,
    TimeSource,
)

ABBR = {"sun": "Su", "moon": "Mo", "mars": "Ma", "mercury": "Me", "jupiter": "Ju",
        "venus": "Ve", "saturn": "Sa", "rahu": "Ra", "ketu": "Ke"}
UNSURE_TIME = (TimeSource.approximate, TimeSource.unknown)
OPEN_RECTIFICATION = ("needed", "open", "pending", "requested")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


@dataclass
class ChartFacts:
    client_id: uuid.UUID
    chart_id: uuid.UUID
    lagna_index: int
    lagna_sign: str
    lagna_degree: float
    moon_index: int | None
    maha: str | None
    antar: str | None
    antar_ends: datetime | None
    houses: dict[int, list[str]] = field(default_factory=dict)


def running_dasha(vimshottari: dict | None, now: datetime) -> tuple[str | None, str | None,
                                                                     datetime | None]:
    """(mahadasha lord, antardasha lord, antardasha end) running at `now`."""
    for maha in (vimshottari or {}).get("mahadashas", []):
        if parse_iso(maha["start"]) <= now < parse_iso(maha["end"]):
            for sub in maha.get("children", []):
                if parse_iso(sub["start"]) <= now < parse_iso(sub["end"]):
                    return maha["planet"], sub["planet"], parse_iso(sub["end"])
            return maha["planet"], None, None
    return None, None, None


def latest_chart_facts(db: Session, client_ids: Iterable[uuid.UUID] | None,
                       now: datetime) -> dict[uuid.UUID, ChartFacts]:
    """Facts from each client's newest chart (of their newest birth record that has one)."""
    stmt = (
        select(BirthRecord.client_id, ChartArtifact.id, ChartArtifact.payload["ascendant"],
               ChartArtifact.payload["planets"], ChartArtifact.payload["vimshottari"])
        .join(ChartArtifact, (ChartArtifact.birth_record_id == BirthRecord.id)
              & (ChartArtifact.practice_id == BirthRecord.practice_id))
        .where(BirthRecord.deleted_at.is_(None))
        .ext(distinct_on(BirthRecord.client_id))
        .order_by(BirthRecord.client_id, BirthRecord.version.desc(),
                  ChartArtifact.created_at.desc()))
    if client_ids is not None:
        ids = list(client_ids)
        if not ids:
            return {}
        stmt = stmt.where(BirthRecord.client_id.in_(ids))
    out: dict[uuid.UUID, ChartFacts] = {}
    for client_id, chart_id, asc, planets, vimshottari in db.execute(stmt):
        asc = asc or {}
        planets = planets or []
        moon = next((p for p in planets if p.get("planet") == "moon"), None)
        maha, antar, ends = running_dasha(vimshottari, now)
        houses: dict[int, list[str]] = {}
        for p in planets:
            if p.get("house") and p.get("planet") in ABBR:
                houses.setdefault(int(p["house"]), []).append(ABBR[p["planet"]])
        out[client_id] = ChartFacts(
            client_id=client_id, chart_id=chart_id, lagna_index=int(asc.get("signIndex", 0)),
            lagna_sign=asc.get("signName", ""), lagna_degree=float(asc.get("degreesInSign", 0)),
            moon_index=int(moon["signIndex"]) if moon else None,
            maha=maha, antar=antar, antar_ends=ends, houses=houses)
    return out


def rectify_flags(db: Session) -> dict[uuid.UUID, tuple[bool, TimeSource]]:
    """client_id -> (needs rectify, time source) from the newest birth record."""
    rows = db.execute(
        select(BirthRecord.client_id, BirthRecord.time_source, BirthRecord.rectification_status)
        .where(BirthRecord.deleted_at.is_(None))
        .ext(distinct_on(BirthRecord.client_id))
        .order_by(BirthRecord.client_id, BirthRecord.version.desc()))
    return {cid: (src in UNSURE_TIME or (status or "") in OPEN_RECTIFICATION, src)
            for cid, src, status in rows}


def tags_by_client(db: Session, client_ids: Iterable[uuid.UUID] | None = None
                   ) -> dict[uuid.UUID, list[str]]:
    stmt = select(ClientTag.client_id, ClientTag.tag).order_by(ClientTag.created_at, ClientTag.tag)
    if client_ids is not None:
        stmt = stmt.where(ClientTag.client_id.in_(list(client_ids)))
    out: dict[uuid.UUID, list[str]] = {}
    for cid, tag in db.execute(stmt):
        out.setdefault(cid, []).append(tag)
    return out


@dataclass
class Timing:
    last: datetime | None = None
    next_booked: datetime | None = None
    next_follow_up: date | None = None


def consultation_timing(db: Session, now: datetime) -> dict[uuid.UUID, Timing]:
    """Per client: last consultation, next booked visit, earliest open follow-up.
    A visit's time is scheduled_at when booked, else consulted_at. A follow-up is open
    until another consultation happens on or after its date."""
    rows = db.execute(select(
        Consultation.id, Consultation.client_id, Consultation.consulted_at,
        Consultation.scheduled_at, Consultation.follow_up_date)
        .where(Consultation.deleted_at.is_(None))).all()
    by_client: dict[uuid.UUID, list] = {}
    for r in rows:
        by_client.setdefault(r.client_id, []).append(r)
    out: dict[uuid.UUID, Timing] = {}
    for cid, items in by_client.items():
        t = Timing()
        times = [(r.scheduled_at or r.consulted_at, r) for r in items]
        past = [at for at, _ in times if at <= now]
        future = [at for at, _ in times if at > now]
        t.last = max(past) if past else None
        t.next_booked = min(future) if future else None
        open_dates = []
        for _at, r in times:
            if r.follow_up_date is None:
                continue
            followed = any(o.id != r.id and (o_at.date() >= r.follow_up_date and o_at <= now)
                           for o_at, o in times)
            if not followed:
                open_dates.append(r.follow_up_date)
        t.next_follow_up = min(open_dates) if open_dates else None
        out[cid] = t
    return out


def live_clients(db: Session) -> list[tuple[uuid.UUID, str, datetime]]:
    return [tuple(r) for r in db.execute(select(Client.id, Client.display_name, Client.created_at)
                                         .where(Client.deleted_at.is_(None)))]

