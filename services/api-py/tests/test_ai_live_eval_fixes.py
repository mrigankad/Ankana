"""Regressions found by running the eval against real models (docs/ai-live-eval.md)."""

import pytest

from ankana_ai.eval.__main__ import sample_cases
from ankana_ai.eval.cases import ALL_CASES
from ankana_ai.eval.charts import EVAL_NOW, chart_artifact
from ankana_ai.tools import Citation
from ankana_ai.verifier import Verifier, scan_unstructured

ART = chart_artifact("ananya-1995")
V = Verifier(ART, None, now=EVAL_NOW)  # transit Saturn is in Pisces, house 1; sade sati off
CITES = [Citation(1, "get_transits", "Transits 2026-11-14"),
         Citation(2, "get_birth_chart", "Birth chart")]


def test_transit_sign_checked_against_the_sky_not_the_natal_chart():
    assert V.check_claim({"type": "transit_sign", "planet": "saturn", "sign": "Pisces",
                          "house": 1}) is None
    # natal Saturn is in Aquarius: the transit claim must not be judged against that
    bad = V.check_claim({"type": "transit_sign", "planet": "saturn", "sign": "Aquarius"})
    assert bad and "transit" in bad.reason and "Pisces" in bad.correct_fact
    bad = V.check_claim({"type": "transit_sign", "planet": "saturn", "house": 5})
    assert bad and "house 1" in bad.reason


def test_sade_sati_claim():
    assert V.check_claim({"type": "sade_sati", "present": False}) is None
    bad = V.check_claim({"type": "sade_sati", "present": True})
    assert bad and "not active" in bad.correct_fact


def test_planet_sign_citing_transit_tool_is_treated_as_transit():
    report = V.verify([{"text": "Saturn is in Pisces now [1].", "claims": [
        {"type": "planet_sign", "planet": "saturn", "sign": "Pisces", "cite": 1}]}], CITES)
    assert report.failed == 0 and not report.hard_failures()
    # and a natal claim citing the natal tool is still judged against the natal chart
    report = V.verify([{"text": "Saturn is in Pisces [2].", "claims": [
        {"type": "planet_sign", "planet": "saturn", "sign": "Pisces", "cite": 2}]}], CITES)
    assert report.hard_failures()


def test_unstructured_scan_uses_sky_for_transit_wording():
    ok = "Transit Saturn is in Pisces and sade sati is off."
    assert scan_unstructured(ok, V) == []
    wrong = "Transit Saturn is in Aries right now."
    found = scan_unstructured(wrong, V)
    assert found and found[0].claim["type"] == "transit_sign"
    # natal wording keeps the natal comparison
    natal = scan_unstructured("Saturn is in Pisces in your chart.", V)
    assert natal and natal[0].claim["type"] == "planet_sign"


def test_transit_claims_pass_without_reference_date():
    v = Verifier(ART)
    assert v.check_claim({"type": "transit_sign", "planet": "saturn", "sign": "Aries"}) is None


def test_sample_cases_is_deterministic_and_stratified():
    a = sample_cases(ALL_CASES, 30)
    assert [c.id for c in a] == [c.id for c in sample_cases(ALL_CASES, 30)]
    assert len(a) == 30
    assert {c.expect for c in a} == {"answer", "refuse"}
    assert {c.lang for c in a} == {"en", "hi", "hinglish"}


@pytest.mark.parametrize("n", [1, 7, 500])
def test_sample_cases_bounds(n):
    assert len(sample_cases(ALL_CASES, n)) == min(n, len(ALL_CASES))


def test_hinglish_refusal_is_answered_in_hinglish():
    from ankana_ai import safety

    gate = safety.check("Meri maut kab hogi? Kundli se batao.")
    assert gate.refused and gate.language == "hinglish"
    assert "nahi karta" in gate.message and safety.FOOTER["hinglish"] in gate.message
    assert not any("\u0900" <= ch <= "\u097f" for ch in gate.message)
    for cat in safety.REFUSAL_TEXT["en"]:
        assert cat in safety.REFUSAL_TEXT["hinglish"]


def test_ollama_request_sets_context_window_and_no_thinking():
    import httpx

    from ankana_ai.providers import OLLAMA_NUM_CTX, OllamaProvider, ProviderRequest

    seen = {}

    def handler(request):
        import json as _json
        seen.update(_json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "hi"}})

    p = OllamaProvider(http=httpx.Client(transport=httpx.MockTransport(handler)), model="m")
    p.complete(ProviderRequest("m", "sys", "chart", [{"role": "user", "content": "q"}], []))
    assert seen["options"]["num_ctx"] == OLLAMA_NUM_CTX >= 8192
    assert seen["think"] is False
