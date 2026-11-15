"""GET /v1/charts/{id}/sensitivity: minutes of birth-time error that flip each fact."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import CurrentMember, tenant_db
from app.auth.deps import current_member
from nakshatra_core.provenance import ephemeris_provenance
from nakshatra_core.providers import get_provider
from nakshatra_core.sensitivity import (
    DEFAULT_WINDOW_MINUTES,
    FLAG_MINUTES,
    sensitivity_report,
)

from .charts import load_chart
from .common import ProblemError

router = APIRouter()


@router.get("/charts/{chart_id}/sensitivity", tags=["charts"], operation_id="getChartSensitivity",
            summary="Birth-time sensitivity: minutes of error that flip sign, pada, house or "
                    "dasha lord (flags anything under 10 minutes)")
def get_sensitivity(chart_id: uuid.UUID,
                    window_minutes: int = Query(default=DEFAULT_WINDOW_MINUTES, ge=10, le=720),
                    m: CurrentMember = Depends(current_member),
                    db: Session = Depends(tenant_db, scope="function")) -> dict:
    chart, _ = load_chart(db, m, chart_id)
    inp = chart.payload.get("calculationMetadata", {}).get("input")
    if not inp:
        raise ProblemError(422, "chart has no stored input", "chart_input_missing")
    if inp.get("timeUnknown"):
        raise ProblemError(422, "birth time is unknown for this chart; sensitivity is undefined",
                           "birth_time_unknown")
    provider = get_provider()
    report = sensitivity_report(inp, provider, window=window_minutes)
    return {"chart_id": chart_id, "flag_threshold_minutes": FLAG_MINUTES,
            "ephemeris": ephemeris_provenance(provider), "sensitivity": report}
