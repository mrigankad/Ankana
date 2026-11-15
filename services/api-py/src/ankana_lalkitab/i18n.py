"""Hindi overlay for the Lal Kitab English paraphrases (mirror of packages/lal-kitab/src/i18n.ts).

The overlay lives in packages/lal-kitab/data/hi/*.json, keyed by the exact English
string, so English edits never desynchronise it: a changed English string simply
has no Hindi until retranslated. Every Hindi string is machine-generated and
flagged ``needs_review_hi: true``.
"""

from __future__ import annotations

from typing import Any

from .data import _read


def _load() -> tuple[dict[str, str], dict]:
    mapping: dict[str, str] = {}
    meta = {"planet_house_rows": 0, "rules_entries": 0, "needs_review_hi": True}
    ph = _read("hi/planet_house.hi.json")
    for row in ph["rows"].values():
        meta["planet_house_rows"] += 1
        if row.get("theme"):
            mapping[row["theme"]] = row["theme_hi"]
        for c in row.get("conditions", []):
            mapping[c["effect"]] = c["effect_hi"]
        for r in row.get("remedies", []):
            mapping[r["text"]] = r["text_hi"]
    rules = _read("hi/rules.hi.json")
    for e in rules["entries"]:
        meta["rules_entries"] += 1
        mapping[e["en"]] = e["hi"]
    return mapping, meta


_STATE: tuple[dict[str, str], dict] | None = None


def _state() -> tuple[dict[str, str], dict]:
    global _STATE
    if _STATE is None:
        _STATE = _load()
    return _STATE


def hi_map() -> dict[str, str]:
    return _state()[0]


def hindi_coverage() -> dict:
    return dict(_state()[1])


def localize_report(value: Any, lang: str | None) -> Any:
    """Return `value` with every known English paraphrase replaced by its Hindi
    translation when lang == "hi"; otherwise unchanged (English stays identical)."""
    if lang != "hi":
        return value
    return _walk(value, hi_map())


def _walk(v: Any, m: dict[str, str]) -> Any:
    if isinstance(v, str):
        return m.get(v, v)
    if isinstance(v, list):
        return [_walk(x, m) for x in v]
    if isinstance(v, dict):
        return {k: _walk(x, m) for k, x in v.items()}
    return v
