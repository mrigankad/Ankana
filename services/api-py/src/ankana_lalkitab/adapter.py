"""Adapter exposing ankana_lalkitab to the assistant (ankana_ai.tools.LalKitabProvider)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .chart import lk_chart
from .remedies import remedies
from .rules import detect_masnui, detect_rin, sleeping_houses, sleeping_planets
from .varshphal import VARSHPHAL_MAX_AGE, varshphal, year_of_life


def _dump(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    return obj.model_dump(by_alias=True) if hasattr(obj, "model_dump") else obj


class LalKitabAdapter:
    available_rules = True

    def chart(self, artifact: dict, origin: str = "lagna_h1") -> dict:
        c = lk_chart(artifact, origin)
        out = _dump(c)
        out["planetHouse"] = dict(c.planet_house)
        return out

    def sleeping(self, artifact: dict) -> dict:
        c = lk_chart(artifact)
        return {"planets": _dump(sleeping_planets(c)), "houses": _dump(sleeping_houses(c))}

    def rin(self, artifact: dict) -> list:
        return _dump(detect_rin(lk_chart(artifact)))

    def masnui(self, artifact: dict) -> list:
        return _dump(detect_masnui(lk_chart(artifact)))

    def varshphal(self, artifact: dict, age: int | None, now: datetime) -> dict:
        if age is None:
            birth = ((artifact.get("calculationMetadata") or {}).get("input") or {}).get(
                "birthDate"
            )
            age = year_of_life(birth, now) if birth else None
        if age is None or not 1 <= age <= VARSHPHAL_MAX_AGE:
            return {"available": False, "reason": f"age must be 1 to {VARSHPHAL_MAX_AGE}"}
        return _dump(varshphal(lk_chart(artifact), age))

    def upay(self, artifact: dict) -> dict:
        return _dump(remedies(lk_chart(artifact)))


def assistant_adapter() -> LalKitabAdapter:
    return LalKitabAdapter()
