"""Plan catalogue and entitlements.

Limits are configuration, not code constants: override the whole catalogue with
a JSON file named by ANKANA_PLANS_FILE (same shape as DEFAULT_PLANS, prices in
paise ex-GST). A limit of None means unlimited. Numbers below are the tier
proposal in research/03-ai-and-scope.md and are not final pricing.

Metrics
- clients     gauge: live (non-deleted) clients at any time
- ai_asks     counter per calendar month (usage_counter metric "ai_asks")
- reports     counter per calendar month (usage_counter metric "reports")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

GST_RATE_BP = 1800  # 18.00 percent, basis points
INTERVALS = ("month", "year")
FREE = "free"
ORDER = ("free", "solo", "studio")  # ascending; used for upgrade vs downgrade
GAUGE_METRICS = ("clients",)
MONTHLY_METRICS = ("ai_asks", "reports")


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_month_paise: int  # ex-GST; 0 for free
    price_year_paise: int
    limits: dict[str, int | None] = field(default_factory=dict)
    features: tuple[str, ...] = ()

    def price_paise(self, interval: str) -> int:
        return self.price_year_paise if interval == "year" else self.price_month_paise

    def total_paise(self, interval: str) -> int:
        """Tax-inclusive amount charged at the provider."""
        from .gst import tax_on

        net = self.price_paise(interval)
        return net + tax_on(net, GST_RATE_BP)


DEFAULT_PLANS: dict[str, dict] = {
    "free": {"name": "Free", "price_month_paise": 0, "price_year_paise": 0,
             "limits": {"clients": 5, "ai_asks": 10, "reports": 0},
             "features": ["Compute and view charts", "Lal Kitab preview"]},
    "solo": {"name": "Solo", "price_month_paise": 59_900, "price_year_paise": 599_900,
             "limits": {"clients": 150, "ai_asks": 150, "reports": 5},
             "features": ["Logo and colours on reports", "Lal Kitab and Hindi"]},
    "studio": {"name": "Studio", "price_month_paise": 149_900, "price_year_paise": 1_499_900,
               "limits": {"clients": None, "ai_asks": 500, "reports": 25},
               "features": ["White label reports", "3 seats", "Report batch queue"]},
}


def _build(raw: dict[str, dict]) -> dict[str, Plan]:
    out = {}
    for key, p in raw.items():
        out[key] = Plan(key, p["name"], int(p["price_month_paise"]), int(p["price_year_paise"]),
                        dict(p.get("limits", {})), tuple(p.get("features", ())))
    if FREE not in out:
        raise ValueError("the plan catalogue must define a 'free' plan")
    return out


@lru_cache(maxsize=4)
def _load(path: str | None) -> dict[str, Plan]:
    if path:
        with open(path, encoding="utf-8") as fh:
            return _build(json.load(fh))
    return _build(DEFAULT_PLANS)


def catalogue() -> dict[str, Plan]:
    return _load(os.getenv("ANKANA_PLANS_FILE") or None)


def get_plan(key: str) -> Plan:
    plans = catalogue()
    return plans.get(key) or plans[FREE]


def rank(key: str) -> int:
    return ORDER.index(key) if key in ORDER else 0


def next_plan_with(metric: str, current: str) -> str | None:
    """Smallest plan above `current` that raises the limit (upgrade hint)."""
    cur = get_plan(current).limits.get(metric)
    for key in ORDER:
        if rank(key) <= rank(current) or key not in catalogue():
            continue
        lim = catalogue()[key].limits.get(metric)
        if lim is None or (cur is not None and lim > cur):
            return key
    return None
