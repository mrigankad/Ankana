"""Hindi overlay for Lal Kitab: coverage, TS/Python loading parity, English untouched."""
import json
import re
from pathlib import Path

from ankana_lalkitab.data import data_dir, planet_house_entries
from ankana_lalkitab.i18n import hi_map, hindi_coverage, localize_report

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def test_every_planet_house_string_has_hindi_and_is_flagged():
    m = hi_map()
    assert len(planet_house_entries) == 108
    for e in planet_house_entries:
        strings = [e.get("theme")] + [c["effect"] for c in e.get("conditions", [])] \
            + [r["text"] for r in e.get("remedies", [])]
        for s in strings:
            if s:
                assert DEVANAGARI.search(m[s]), (e["id"], s)
    doc = json.loads((data_dir() / "hi" / "planet_house.hi.json").read_text(encoding="utf-8"))
    assert doc["needs_review_hi"] is True
    assert all(r["needs_review_hi"] is True for r in doc["rows"].values())
    assert hindi_coverage()["planet_house_rows"] == 108


def test_overlay_is_the_same_file_the_ts_package_reads():
    # TS imports ../data/hi/*.json from the same package directory the Python loader uses.
    ts = (Path(data_dir()).parent / "src" / "i18n.ts").read_text(encoding="utf-8")
    assert "../data/hi/planet_house.hi.json" in ts and "../data/hi/rules.hi.json" in ts


def test_english_is_unchanged_and_hindi_replaces_text():
    src = {"theme": planet_house_entries[0]["theme"], "n": 3}
    assert localize_report(src, "en") is src
    out = localize_report(src, "hi")
    assert DEVANAGARI.search(out["theme"]) and out["n"] == 3
