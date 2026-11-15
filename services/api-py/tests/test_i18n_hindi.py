"""Hindi interpretation: catalog completeness, placeholder parity, snapshot, coverage."""
import json
import re
import string
import sys
from pathlib import Path

import pytest

from ankana_ai.eval.charts import CHART_INPUTS, EVAL_NOW
from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_i18n import CATALOGS, REMEDY_DATA_HI, names
from nakshatra_i18n import significations_hi as sig_hi
from nakshatra_i18n.yogas_hi import YOGA_DESC_HI, YOGA_NAMES_HI
from nakshatra_interpret import build_reading
from nakshatra_interpret import significations as sig_en
from nakshatra_rules import evaluate_predictions_enriched, evaluate_remedies
from nakshatra_rules.evaluator import _SOURCE_KEYS, rule_catalog_key
from nakshatra_rules.pack import DOMAIN_LABEL, VEDIC_PREDICTION_RULES
from nakshatra_rules.remedies import _REMEDY_DATA

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from gen_interpret_golden import snapshot_hi  # noqa: E402

GOLDEN_HI = Path(__file__).parent / "golden" / "interpret_hi_ananya.json"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
EN, HI = CATALOGS["en"], CATALOGS["hi"]


def fields(template: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def test_every_en_key_has_hi_and_vice_versa():
    assert set(EN) == set(HI)


@pytest.mark.parametrize("key", sorted(EN))
def test_placeholder_parity_and_devanagari(key):
    assert fields(EN[key]) == fields(HI[key]), key
    structural = {"ls.ruled_item", "ls.dasha.ruled.item", "ls.title.hybrid", "ls.title.open",
                  "ls.title.range"}  # pure layout templates, no words
    if key not in structural:
        assert DEVANAGARI.search(HI[key]), key


def test_signification_tables_are_complete():
    assert set(sig_hi.PLANET_SIGNIFICATIONS) == set(sig_en.PLANET_SIGNIFICATIONS)
    for p, row in sig_en.PLANET_SIGNIFICATIONS.items():
        assert set(sig_hi.PLANET_SIGNIFICATIONS[p]) == set(row)
    assert set(sig_hi.HOUSE_THEMES) == set(sig_en.HOUSE_THEMES)
    assert set(sig_hi.SIGN_TRAITS) == set(sig_en.SIGN_TRAITS)
    assert set(sig_hi.NAKSHATRA_TRAITS) == set(sig_en.NAKSHATRA_TRAITS)
    assert set(sig_hi.DIGNITY_PHRASES) == set(sig_en.DIGNITY_PHRASES)
    assert len(names.NAKSHATRAS_HI) == 27 and len(names.SIGNS_HI) == 12
    assert len(names.PANCHANG_YOGAS_HI) == 27 and len(names.KARANAS_HI) == 11


def test_remedy_data_and_rule_catalog_coverage():
    for planet, row in _REMEDY_DATA.items():
        assert set(REMEDY_DATA_HI[planet]) == set(row)
    for rule in VEDIC_PREDICTION_RULES:
        assert rule_catalog_key(rule) in EN, rule["id"]
        assert rule["source"] in _SOURCE_KEYS, rule["source"]


def test_english_rule_text_equals_catalog():
    for rule in VEDIC_PREDICTION_RULES:
        label = DOMAIN_LABEL[rule["domain"]]
        rendered = EN[rule_catalog_key(rule)].format(level="{level}", lord="{lord}", label=label)
        assert rendered == rule["text"], rule["id"]


def test_yoga_tables_cover_all_detectors():
    art = compute_vedic_chart_artifact(CHART_INPUTS["ananya-1995"])
    keys = {y["key"] for y in art["yogas"]}
    assert keys <= set(YOGA_NAMES_HI)
    assert keys - set(YOGA_DESC_HI) <= {"ruchaka", "bhadra", "hamsa", "malavya", "sasa"}


LATIN = re.compile(r"[A-Za-z]{3,}")
MACHINE = {"ruleIds", "linkedRemedyPlanets", "key", "kind", "planet", "effect", "domain",
           "confidenceBand", "strengthOfRecommendation", "generatedAt", "engineVersion",
           "birthDate", "start", "end", "level"}


def _latin_leaks(o, field=""):
    if isinstance(o, str):
        return [(field, o)] if field not in MACHINE and LATIN.search(o) else []
    if isinstance(o, dict):
        return [x for k, v in o.items() for x in _latin_leaks(v, k)]
    if isinstance(o, list):
        return [x for v in o for x in _latin_leaks(v, field)]
    return []


@pytest.mark.parametrize("chart", ["ananya-1995", "raiganj-2003", "varanasi-1990"])
def test_hindi_output_has_no_english_leaks(chart):
    art = compute_vedic_chart_artifact(CHART_INPUTS[chart])
    out = {"r": build_reading(art, EVAL_NOW, "hi"),
           "p": evaluate_predictions_enriched(art, EVAL_NOW, 5, lang="hi"),
           "m": evaluate_remedies(art, "hi")}
    assert _latin_leaks(out) == []


def test_hindi_reading_snapshot_for_ananya():
    expected = json.loads(GOLDEN_HI.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(snapshot_hi(), ensure_ascii=False)) == expected


def test_default_language_is_english():
    art = compute_vedic_chart_artifact(CHART_INPUTS["ananya-1995"])
    assert build_reading(art, EVAL_NOW) == build_reading(art, EVAL_NOW, "en")
    assert build_reading(art, EVAL_NOW, "fr") == build_reading(art, EVAL_NOW, "en")


def test_lang_query_param_on_stateless_endpoints():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    body = {"birthDate": "2003-08-29", "birthTime": "12:22", "timezoneName": "Asia/Kolkata",
            "latitude": 25.6167, "longitude": 88.1233}
    hi = client.post("/api/v1/charts/reading?lang=hi", json=body).json()
    assert hi["language"] == "hi"
    assert DEVANAGARI.search(hi["reading"]["sections"][0]["title"])
    en = client.post("/api/v1/charts/reading", json=body).json()
    assert en["language"] == "en" and en["reading"]["sections"][0]["title"] == "Lagna & temperament"
    rem = client.post("/api/v1/charts/remedies?lang=hi", json=body).json()
    assert rem["language"] == "hi" and DEVANAGARI.search(rem["remedies"][0]["title"])
    pred = client.post("/api/v1/charts/predictions?lang=hi", json=body).json()
    assert DEVANAGARI.search(pred["predictions"][0]["headline"])
