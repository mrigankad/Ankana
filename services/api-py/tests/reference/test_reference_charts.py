"""Run every reference chart against the providers.

- swiss: must meet the full tolerances (it generated the provisional truth, so this
  guards reproducibility; once cases are replaced by JHora exports it becomes the
  real parity test).
- astronomy: known to miss the tolerances (see docs/engine-accuracy.md). The strict
  test is xfail; the envelope test pins today's measured error so it cannot silently
  get worse.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import runner  # noqa: E402

CASES = runner.load_cases()
IDS = [c["id"] for c in CASES]
SCHEMA = json.loads((Path(__file__).parent / "schema.json").read_text(encoding="utf-8"))

# Measured astronomy-engine worst cases (docs/engine-accuracy.md) with headroom.
ENVELOPE = {"ayanamsa": 40, "ascendant": 40, "rahu": 40, "moon": 40, "sunrise": 700,
            "sunset": 700}
ENVELOPE_PLANET = 45
ENVELOPE_DASHA_DAYS = 6


def _swiss_or_skip():
    pytest.importorskip("swisseph")
    from nakshatra_core.providers import get_provider

    provider = get_provider("swiss")
    if not provider.using_files:
        pytest.skip("Swiss .se1 data files missing (scripts/fetch_ephe.py)")
    if provider.mean_ayanamsa:
        pytest.skip("ANKANA_AYANAMSA_MEAN set; reference cases use the nutation ayanamsa")
    return provider


def test_cases_match_schema_required_fields() -> None:
    assert len(CASES) >= 11
    for case in CASES:
        for key in SCHEMA["required"]:
            assert key in case, f"{case.get('id')} missing {key}"
        for key in SCHEMA["properties"]["expected"]["required"]:
            assert key in case["expected"], f"{case['id']} expected missing {key}"
        assert len(case["expected"]["vimshottariStarts"]) == 9
        assert set(case["expected"]["planets"]) >= {*runner.BODIES, "rahu", "ketu"}


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_swiss_meets_tolerances(case: dict) -> None:
    provider = _swiss_or_skip()
    bad = [d for d in runner.compare(case, runner.compute(case, provider)) if not d.ok]
    assert not bad, [(d.field, round(d.value, 3), d.unit) for d in bad]


@pytest.mark.xfail(reason="astronomy-engine + approximate ayanamsa misses JHora tolerances",
                   strict=False)
@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_astronomy_meets_tolerances(case: dict) -> None:
    from nakshatra_core.providers import get_provider

    bad = [d for d in runner.compare(case, runner.compute(case, get_provider("astronomy")))
           if not d.ok]
    assert not bad


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_astronomy_stays_within_known_envelope(case: dict) -> None:
    from nakshatra_core.providers import get_provider

    for d in runner.compare(case, runner.compute(case, get_provider("astronomy"))):
        if d.unit == "days":
            assert abs(d.value) <= ENVELOPE_DASHA_DAYS, d
        else:
            assert abs(d.value) <= ENVELOPE.get(d.field, ENVELOPE_PLANET), d
