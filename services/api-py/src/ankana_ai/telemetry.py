"""Optional usage hook so the host application can meter provider calls without
ankana_ai importing it. The hook gets (provider, model, usage, cost_usd)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

usage_hook: Callable[[str, str, dict, float], None] | None = None


def provider_label(provider: Any) -> str:
    for attr in ("kind", "name"):
        v = getattr(provider, attr, None)
        if isinstance(v, str) and v:
            return v
    return type(provider).__name__.removesuffix("Provider").lower() or "unknown"


def record_usage(provider: Any, model: str, usage: dict, cost: float) -> None:
    hook = usage_hook
    if hook is None:
        return
    try:
        hook(provider_label(provider), model or "unknown", usage or {}, cost)
    except Exception:  # metering must never break an answer
        pass
