"""Lightweight lagna preview for the intake form. Nothing is persisted and no
client or consent is needed: it is a pure calculation on birth details that the
practitioner is still typing. Authenticated and rate limited per member."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from datetime import time as dtime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentMember, require_roles
from app.tenancy.models import Role
from nakshatra_core.ascendant import sidereal_ascendant
from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_core.vargas import varga_sign

from .common import STAFF, ProblemError

router = APIRouter()

ABBR = {"sun": "Su", "moon": "Mo", "mars": "Ma", "mercury": "Me", "jupiter": "Ju",
        "venus": "Ve", "saturn": "Sa", "rahu": "Ra", "ketu": "Ke"}
SCAN_MINUTES = 240  # look this far either side of the recorded time
LIMIT_PER_MINUTE = 40

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _rate_limit(member: CurrentMember) -> None:
    now = time.monotonic()
    key = str(member.member_id)
    with _lock:
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= LIMIT_PER_MINUTE:
            raise ProblemError(429, "too many preview requests, wait a few seconds",
                               "rate_limited")
        q.append(now)


class PreviewIn(BaseModel):
    birth_date: date
    birth_time: dtime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone_name: str = Field(max_length=64)
    ayanamsa: str = "lahiri"


def _clock(birth: dtime, minutes: int) -> str:
    base = datetime(2000, 1, 1, birth.hour, birth.minute)
    return (base + timedelta(minutes=minutes)).strftime("%H:%M")


@router.post("/charts/preview", tags=["charts"], operation_id="previewChart",
             summary="Lagna preview and birth-time sensitivity (not stored, rate limited)")
def preview_chart(body: PreviewIn, m: CurrentMember = Depends(require_roles(*STAFF))) -> dict:
    _rate_limit(m)
    try:
        art = compute_vedic_chart_artifact({
            "birthDate": body.birth_date.isoformat(),
            "birthTime": body.birth_time.strftime("%H:%M"),
            "timezoneName": body.timezone_name,
            "latitude": body.latitude, "longitude": body.longitude,
            "ayanamsa": body.ayanamsa,
        })
    except (KeyError, ValueError) as exc:
        raise ProblemError(422, f"cannot compute chart: {exc}", "chart_compute_failed") from exc

    asc = art["ascendant"]
    moon = next(p for p in art["planets"] if p["planet"] == "moon")
    houses = {str(h["number"]): [ABBR[o] for o in h["occupants"]]
              for h in art["houses"] if h["occupants"]}

    # Walk the clock in 1 minute steps. The scan uses the pure-math ascendant as a
    # delta on top of the chart's own lagna, so it matches the chart at minute 0.
    utc = datetime.fromisoformat(art["calculationMetadata"]["utcDateTime"].replace("Z", "+00:00"))
    base_scan = sidereal_ascendant(utc, body.latitude, body.longitude)
    base_sidereal = asc["siderealLongitude"]

    def at(offset: int) -> float:
        d = sidereal_ascendant(utc + timedelta(minutes=offset), body.latitude, body.longitude)
        return (base_sidereal + ((d - base_scan + 180) % 360 - 180)) % 360

    d1_sign = int(base_sidereal // 30)
    d9_sign = varga_sign("d9", base_sidereal)

    def hold(which: str, step: int) -> int:
        for k in range(1, SCAN_MINUTES + 1):
            lon = at(step * k)
            now = int(lon // 30) if which == "d1" else varga_sign("d9", lon)
            if now != (d1_sign if which == "d1" else d9_sign):
                return k - 1
        return SCAN_MINUTES

    d1_before, d1_after = hold("d1", -1), hold("d1", 1)
    d9_before, d9_after = hold("d9", -1), hold("d9", 1)
    bt = body.birth_time
    return {
        "lagna": {"sign": asc["signName"], "sign_index": asc["signIndex"],
                  "degrees_in_sign": round(asc["degreesInSign"], 4),
                  "nakshatra": asc["nakshatra"], "pada": asc["pada"]},
        "moon": {"sign": moon["signName"], "nakshatra": moon["nakshatra"], "pada": moon["pada"]},
        "houses": houses,
        "sensitivity": {
            "d1_minutes_before": d1_before, "d1_minutes_after": d1_after,
            "d1_holds_from": _clock(bt, -d1_before), "d1_holds_until": _clock(bt, d1_after),
            "d9_minutes_before": d9_before, "d9_minutes_after": d9_after,
            "d9_holds_from": _clock(bt, -d9_before), "d9_holds_until": _clock(bt, d9_after),
            "window_minutes": min(d9_before, d9_after),
            "scan_minutes": SCAN_MINUTES,
        },
        "ayanamsa": art["calculationMetadata"]["ayanamsa"],
    }


__all__ = ["router", "Role"]
