"""Regenerate tests/golden/interpret_en.json (English interpretation snapshot).

Run with PYTHONPATH=src. The English output must stay byte-identical across
i18n refactors, so only regenerate this when the English prose changes on
purpose.
"""
import json
from pathlib import Path

from ankana_ai.eval.charts import CHART_INPUTS, EVAL_NOW
from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_interpret import build_reading
from nakshatra_rules import evaluate_predictions_enriched, evaluate_remedies

KEYS = ("ananya-1995", "raiganj-2003", "varanasi-1990")


def snapshot() -> dict:
    out = {}
    for key in KEYS:
        art = compute_vedic_chart_artifact(CHART_INPUTS[key])
        out[key] = {
            "reading": build_reading(art, EVAL_NOW),
            "predictions": evaluate_predictions_enriched(art, EVAL_NOW, 5),
            "remedies": evaluate_remedies(art),
        }
    return out


def snapshot_hi() -> dict:
    """Hindi snapshot for the Ananya sample chart (review artefact + regression guard)."""
    art = compute_vedic_chart_artifact(CHART_INPUTS["ananya-1995"])
    return {
        "reading": build_reading(art, EVAL_NOW, "hi"),
        "predictions": evaluate_predictions_enriched(art, EVAL_NOW, 5, lang="hi"),
        "remedies": evaluate_remedies(art, "hi"),
    }


if __name__ == "__main__":
    golden = Path(__file__).resolve().parent.parent / "tests" / "golden"
    for name, data in (("interpret_en.json", snapshot()), ("interpret_hi_ananya.json", snapshot_hi())):
        (golden / name).write_text(
            json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        print("wrote", golden / name)
