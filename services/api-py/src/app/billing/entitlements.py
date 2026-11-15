"""FastAPI dependencies that gate metered actions on the practice's plan.

    @router.post(..., dependencies=[Depends(require_entitlement("ai_asks"))])

Pass-through when ANKANA_BILLING is off. Otherwise: 402 plan_limit_reached when
the monthly quota (or client cap) is used up, 403 plan_feature_unavailable when
the plan does not include the metric. Both are problem+json with an
upgrade_to / upgrade_url hint.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import CurrentMember, current_member, tenant_db

from .service import enforce


def require_entitlement(metric: str) -> Callable[..., None]:
    def check(m: CurrentMember = Depends(current_member),
              db: Session = Depends(tenant_db, scope="function")) -> None:
        enforce(db, m.practice_id, metric)

    check.__name__ = f"entitlement_{metric}"
    return check
