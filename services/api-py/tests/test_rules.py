import json
from datetime import datetime
from pathlib import Path

import pytest

from nakshatra_rules import evaluate_predictions, evaluate_remedies

GOLDEN = Path(__file__).parent / "golden" / "rules.json"


@pytest.fixture(scope="module")
def golden_rules(golden_charts: list[dict]) -> dict:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    data["natal"] = next(
        c["artifact"] for c in golden_charts if c["label"] == data["natalLabel"]
    )
    return data


def test_predictions_match_golden(golden_rules: dict) -> None:
    from_date = datetime.fromisoformat(golden_rules["from"].replace("Z", "+00:00"))
    result = evaluate_predictions(
        golden_rules["natal"], from_date, golden_rules["horizonYears"]
    )
    golden = golden_rules["predictions"]
    assert len(result) == len(golden)
    for mine, gold in zip(result, golden, strict=True):
        label = gold["headline"]
        assert mine["domain"] == gold["domain"], label
        assert mine["headline"] == gold["headline"], label
        assert mine["narrative"] == gold["narrative"], label
        assert mine["effect"] == gold["effect"], label
        assert abs(mine["confidence"] - gold["confidence"]) < 1e-9, label
        assert mine["evidence"] == gold["evidence"], label
        assert mine["ruleIds"] == gold["ruleIds"], label
        assert mine["window"]["start"] == gold["window"]["start"], label


def test_remedies_match_golden(golden_rules: dict) -> None:
    result = evaluate_remedies(golden_rules["natal"])
    golden = golden_rules["remedies"]
    assert len(result) == len(golden)
    for mine, gold in zip(result, golden, strict=True):
        assert mine == gold, gold["title"]
