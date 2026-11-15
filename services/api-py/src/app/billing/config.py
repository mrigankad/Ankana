"""Billing switches and environment-driven settings.

ANKANA_BILLING=off (default) means unlimited usage: no limit is ever enforced and
the /v1/billing routes answer 404. The hosted service sets ANKANA_BILLING=on.
"""

from __future__ import annotations

import os

GRACE_DAYS_DEFAULT = 7


def billing_enabled() -> bool:
    return os.getenv("ANKANA_BILLING", "off").strip().lower() in {"on", "1", "true", "yes"}


def grace_days() -> int:
    try:
        return max(0, int(os.getenv("ANKANA_BILLING_GRACE_DAYS", GRACE_DAYS_DEFAULT)))
    except ValueError:
        return GRACE_DAYS_DEFAULT


def webhook_secret() -> str:
    return os.getenv("RAZORPAY_WEBHOOK_SECRET", "")


def supplier() -> dict:
    """Who issues the invoice (the operator of the hosted service). Set these
    for production; the defaults are placeholders and MUST be replaced."""
    return {
        "name": os.getenv("ANKANA_SUPPLIER_NAME", "Ankana (supplier name to be set)"),
        "gstin": os.getenv("ANKANA_SUPPLIER_GSTIN", ""),
        "state_code": os.getenv("ANKANA_SUPPLIER_STATE_CODE", "29"),
        "address": os.getenv("ANKANA_SUPPLIER_ADDRESS", ""),
        "email": os.getenv("ANKANA_SUPPLIER_EMAIL", ""),
    }
