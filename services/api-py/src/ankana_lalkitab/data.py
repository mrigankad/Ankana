"""Lal Kitab data tables. Single source: packages/lal-kitab/data (no copy).

``planet_house`` is read from ``planet_house.json`` and, when present, merged with
``planet_house/*.json`` (per-planet files). A per-planet row replaces a base row
with the same id; rows with new ids are appended.
Override the directory with the LAL_KITAB_DATA_DIR environment variable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PLANET_ORDER = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]


def data_dir() -> Path:
    env = os.environ.get("LAL_KITAB_DATA_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4] / "packages" / "lal-kitab" / "data"


def _read(name: str) -> Any:
    return json.loads((data_dir() / name).read_text(encoding="utf-8"))


def _load_planet_house() -> list[dict]:
    rows: list[dict] = list(_read("planet_house.json")["rows"])
    folder = data_dir() / "planet_house"
    if folder.is_dir():
        index = {r["id"]: i for i, r in enumerate(rows)}
        for f in sorted(folder.glob("*.json")):
            payload = json.loads(f.read_text(encoding="utf-8"))
            extra = payload if isinstance(payload, list) else payload.get("rows", [])
            for row in extra:
                if row["id"] in index:
                    rows[index[row["id"]]] = row
                else:
                    index[row["id"]] = len(rows)
                    rows.append(row)
    return rows


pakka_ghar: list[dict] = _read("pakka_ghar.json")["rows"]
aspect_rows: list[dict] = _read("aspects.json")["rows"]
dormant_data: dict = _read("dormant.json")
rin_data: dict = _read("rin.json")
masnui_data: dict = _read("masnui.json")
varshphal_data: dict = _read("varshphal.json")
cycle35: list[dict] = _read("cycle35.json")["rows"]
remedy_delivery: dict = _read("remedy_delivery.json")
planet_house_entries: list[dict] = _load_planet_house()
friendship_tables: list[dict] = _read("friendship.json")["tables"]


def data_coverage() -> dict:
    def count(rows: list[dict]) -> dict:
        return {"rows": len(rows), "needs_review": sum(1 for r in rows if r.get("needs_review"))}

    return {
        "pakka_ghar": count(pakka_ghar),
        "aspects": count(aspect_rows),
        "dormant_awakeners": count(dormant_data["awakeners"]),
        "self_awakening": count(dormant_data["self_awakening"]),
        "rin": count(rin_data["rows"]),
        "masnui": count(masnui_data["rows"]),
        "varshphal_matrix": {
            "rows": len(varshphal_data["rows"]),
            "needs_review": len(varshphal_data["rows"]) if varshphal_data.get("needs_review") else 0,
        },
        "cycle35": count(cycle35),
        "remedy_delivery": count(remedy_delivery["rows"]),
        "friendship": count(friendship_tables),
        "planet_house": {
            "total": len(planet_house_entries),
            "done": sum(1 for e in planet_house_entries if e["status"] == "done"),
            "todo": sum(1 for e in planet_house_entries if e["status"] == "todo"),
        },
    }
