"""ankana_ai: gate, routing, tools, verifier, assistant policy (MockProvider only)."""

import json
from datetime import UTC, datetime

import pytest

from ankana_ai import MockProvider, ask, safety
from ankana_ai.config import HAIKU, OPUS, SONNET, cost_usd
from ankana_ai.eval.charts import EVAL_NOW, chart_artifact
from ankana_ai.routing import route
from ankana_ai.tools import (
    CitationRegistrar,
    StubLalKitab,
    ToolContext,
    execute_tool,
    tool_definitions,
)
from ankana_ai.verifier import Verifier

ART = chart_artifact("ananya-1995")
NOW = EVAL_NOW


# ----------------------------------------------------------------- safety


@pytest.mark.parametrize("q,cat", [
    ("When will I die?", "death"),
    ("मेरी मृत्यु कब होगी?", "death"),
    ("Mera maut kab hoga", "death"),
    ("Will I get cancer?", "serious_disease"),
    ("Will I win my court case?", "litigation"),
    ("Pressure my client into buying a gemstone", "gemstone_pressure"),
    ("Please rectify my birth time", "rectification"),
    ("Which stocks should I buy?", "financial"),
])
def test_gate_refuses(q, cat):
    gate = safety.check(q)
    assert gate.refused and gate.category == cat
    assert any(f in gate.message for f in ("Advisory guidance only", "सलाहात्मक", "Sirf salah ke roop mein"))


@pytest.mark.parametrize("q", [
    "Where is Mars in Cancer?",
    "What does the 8th house signify?",
    "Which gemstone is traditionally linked to Jupiter, with cautions?",
    "Is Saturn dasha good for career?",
    "Moon in Cancer and the 4th house",
])
def test_gate_does_not_overrefuse(q):
    assert not safety.check(q).refused


def test_language_detection():
    assert safety.detect_language("मेरा चंद्र कहाँ है") == "hi"
    assert safety.detect_language("mera mangal kahan hai") == "hinglish"
    assert safety.detect_language("where is my moon") == "en"


# ---------------------------------------------------------------- routing


def test_routing_tiers():
    assert route("Which house is my Moon in?").model == HAIKU
    assert route("What does my chart say about career timing and marriage?").model == SONNET
    assert route("anything", deep=True).model == OPUS


def test_cost_usd_uses_cache_prices():
    usage = {"input_tokens": 1000, "output_tokens": 1000,
             "cache_read_input_tokens": 10000, "cache_creation_input_tokens": 0}
    assert cost_usd(SONNET, usage) == pytest.approx((1000 * 2 + 1000 * 10 + 10000 * 0.10) / 1e6)
    assert cost_usd("unknown-model", usage) == 0.0


# ------------------------------------------------------------------ tools


def test_tool_definitions_stable_and_valid():
    assert tool_definitions() == tool_definitions()
    names = [t["name"] for t in tool_definitions()]
    assert names[-1] == "submit_answer" and "lk_chart" in names and "get_birth_chart" in names
    for t in tool_definitions():
        assert t["input_schema"]["type"] == "object"
    assert "lk_chart" not in [t["name"] for t in tool_definitions(lk_enabled=False)]


def test_tools_return_artifact_facts_and_dedupe_citations():
    ctx = ToolContext(ART, NOW, StubLalKitab())
    chart = execute_tool("get_birth_chart", ctx)
    moon = next(p for p in chart.data["planets"] if p["planet"] == "moon")
    assert (moon["signName"], moon["house"]) == ("Leo", 6)
    dashas = execute_tool("get_dashas", ctx, {"mahadasha": ""})
    assert dashas.data["current"]["mahadasha"]["planet"] == "moon"
    assert dashas.data["current"]["antardasha"]["planet"] == "mars"
    assert len(dashas.data["antardashasOf"]["periods"]) == 9
    reg = CitationRegistrar()
    c1 = reg.register("get_birth_chart", {}, chart.summary, chart.anchor)
    c2 = reg.register("get_birth_chart", {}, chart.summary, chart.anchor)
    c3 = reg.register("get_yogas", {}, "y", "yogas")
    assert c1.index == c2.index == 1 and c3.index == 2 and c1.anchor == "planets"


def test_lal_kitab_stub_chart_matches_whole_sign_houses():
    ctx = ToolContext(ART, NOW, StubLalKitab())
    lk = execute_tool("lk_chart", ctx, {"origin": "lagna_h1"})
    assert lk.data["planetHouse"]["moon"] == 6
    assert execute_tool("lk_upay", ctx).data["available"] is False


@pytest.mark.parametrize("name", ["get_strengths", "get_transits", "get_predictions",
                                  "get_remedies", "get_reading_summary", "get_life_story",
                                  "get_yogas"])
def test_every_data_tool_runs_and_serialises(name):
    res = execute_tool(name, ToolContext(ART, NOW, StubLalKitab()))
    assert res.summary
    json.dumps(res.data, default=str)


# --------------------------------------------------------------- verifier

V = Verifier(ART, StubLalKitab())


def test_verifier_accepts_correct_claims():
    ok = [
        {"type": "planet_sign", "planet": "moon", "sign": "Leo"},
        {"type": "planet_sign", "planet": "chandra", "sign": "Leo"},
        {"type": "planet_house", "planet": "saturn", "house": 12},
        {"type": "planet_degree", "planet": "moon", "degree": 4.9},
        {"type": "planet_nakshatra", "planet": "moon", "nakshatra": "Magha", "pada": 2},
        {"type": "lagna", "sign": "Pisces", "degree": 10.5, "nakshatra": "Uttara Bhadrapada"},
        {"type": "house_lord", "house": 1, "lord": "jupiter"},
        {"type": "dasha_period", "level": "mahadasha", "planet": "moon",
         "start": "2025-09-25", "end": "2035-09-25"},
        {"type": "dasha_period", "level": "mahadasha", "planet": "moon", "start": "2025-09-24"},
        {"type": "dasha_period", "level": "mahadasha", "planet": "mars"},
        {"type": "yoga", "yoga": "Gajakesari Yoga", "present": True},
        {"type": "yoga", "yoga": "budhaditya", "present": False},
        {"type": "lk_planet_house", "planet": "moon", "house": 6},
    ]
    for c in ok:
        assert V.check_claim(c) is None, c


def test_verifier_catches_each_claim_type():
    bad = [
        {"type": "planet_sign", "planet": "moon", "sign": "Virgo"},
        {"type": "planet_house", "planet": "moon", "house": 7},
        {"type": "planet_degree", "planet": "moon", "degree": 5.5},
        {"type": "planet_nakshatra", "planet": "moon", "nakshatra": "Ashlesha"},
        {"type": "planet_nakshatra", "planet": "moon", "nakshatra": "Magha", "pada": 3},
        {"type": "lagna", "sign": "Aries"},
        {"type": "house_lord", "house": 10, "lord": "saturn"},
        {"type": "dasha_period", "level": "mahadasha", "planet": "moon", "start": "2024-01-01"},
        {"type": "dasha_period", "level": "antardasha", "planet": "mars", "parent": "moon",
         "start": "2026-07-26", "end": "2027-03-30"},
        {"type": "yoga", "yoga": "Budhaditya Yoga", "present": True},
        {"type": "yoga", "yoga": "Nonexistent Yoga"},
        {"type": "lk_planet_house", "planet": "moon", "house": 5},
        {"type": "planet_sign", "planet": "pluto", "sign": "Leo"},
        {"type": "mystery"},
    ]
    for c in bad:
        mismatch = V.check_claim(c)
        assert mismatch is not None and mismatch.correct_fact, c


def test_verifier_degree_tolerance_boundary():
    assert V.check_claim({"type": "planet_degree", "planet": "moon", "degree": 5.1}) is None
    assert V.check_claim({"type": "planet_degree", "planet": "moon", "degree": 5.4}) is not None


def test_verifier_citation_rules():
    reg = CitationRegistrar()
    c = reg.register("get_birth_chart", {}, "f", "planets")
    claim = {"type": "planet_sign", "planet": "moon", "sign": "Leo", "cite": c.index}
    assert V.verify([{"text": "t", "claims": [claim]}], reg.citations).hard_failures() == {}
    missing = {**claim, "cite": 9}
    assert V.verify([{"text": "t", "claims": [missing]}], reg.citations).hard_failures()
    wrong_tool = {"type": "yoga", "yoga": "Gajakesari Yoga", "cite": c.index}
    rep = V.verify([{"text": "t", "claims": [wrong_tool]}], reg.citations)
    assert rep.hard_failures() == {} and rep.mismatches[0][0].soft  # warning only


@pytest.mark.parametrize("text", [
    "Moon is placed in Virgo.",
    "Your Moon sits in Virgo in the chart.",
    "Chandra Kanya mein hai.",
    "चंद्र कन्या राशि में है।",
])
def test_undeclared_claims_cannot_hide_in_prose(text):
    assert V.verify([{"text": text, "claims": []}], []).failed == 1, text


def test_undeclared_correct_prose_is_fine():
    assert V.verify([{"text": "Moon is in Leo.", "claims": []}], []).failed == 0
    assert V.verify([{"text": "Mars aspects Aries.", "claims": []}], []).failed == 0


# -------------------------------------------------------------- assistant

Q = "Where is my Moon and what is my current dasha? Any yoga?"


def run(behavior="faithful", q=Q, **kw):
    return ask(MockProvider(behavior), ART, q, now=NOW, **kw)


def test_faithful_answer_verified_and_cited():
    r = run()
    assert r.verification["status"] == "verified" and r.rounds == 2
    assert [c["tool"] for c in r.citations] == ["get_birth_chart", "get_dashas", "get_yogas"]
    assert "Moon is in Leo" in r.answer and "[1]" in r.answer
    assert r.answer.endswith("not medical, legal, or financial advice.")
    assert r.model == HAIKU and r.tools_used[0] == "get_birth_chart"


def test_one_rewrite_fixes_wrong_sign():
    r = run("wrong_once")
    assert r.verification["status"] == "rewritten" and r.verification["rewrites"] == 1
    assert r.verification["firstPassFailed"] >= 1
    assert "Virgo" not in r.answer and "Leo" in r.answer


def test_still_wrong_after_rewrite_is_dropped_and_fact_surfaced():
    r = run("wrong_always")
    assert r.verification["status"] == "partial"
    assert r.verification["rewrites"] == 1
    assert "Virgo" not in r.answer
    assert "Could not verify" in r.answer and "Moon is in Leo" in r.answer
    assert r.verification["dropped"]


def test_no_rewrite_option_drops_immediately():
    r = run("wrong_once", allow_rewrite=False)
    assert r.verification["status"] == "partial" and r.rounds == 2


def test_hidden_claim_in_prose_is_caught():
    r = run("hidden_claim")
    assert r.verification["status"] == "rewritten"
    assert "Virgo" not in r.answer


def test_no_submit_answer_is_flagged_unverified():
    assert run("no_submit").verification["status"] == "unverified"


def test_hindi_and_hinglish_use_structured_claims():
    hi = run("wrong_once", q="मेरा चंद्र किस राशि में है?")
    assert hi.language == "hi" and hi.verification["status"] == "rewritten"
    assert "सलाहात्मक" in hi.answer
    hg = run(q="Mera mangal kahan hai kundli mein?")
    assert hg.language == "hinglish" and hg.verification["status"] == "verified"
    assert "Cancer" in hg.answer


def test_gate_refuses_without_model_call():
    provider = MockProvider()
    r = ask(provider, ART, "When will I die?", now=NOW)
    assert r.refused and r.refusal_category == "death" and provider.calls == 0
    assert r.verification["status"] == "gated" and r.cost_usd == 0


def test_round_budget_gives_up_gracefully():
    assert "could not ground" in run(max_rounds=1).answer.lower()


def test_history_is_windowed_and_alternates():
    hist = [{"role": "assistant", "content": "stray"}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
        for i in range(30)]
    seen = {}

    class Spy(MockProvider):
        def complete(self, request):
            seen.setdefault("messages", list(request.messages))
            return super().complete(request)

    ask(Spy(), ART, "Where is my Moon?", now=NOW, history=hist)
    roles = [m["role"] for m in seen["messages"]]
    assert roles[0] == "user" and all(a != b for a, b in zip(roles, roles[1:]))
    assert len(roles) <= 11


def test_dashes_normalised_in_answer():
    class Dashy(MockProvider):
        def complete(self, request):
            resp = super().complete(request)
            for b in resp.content:
                if b["type"] == "tool_use" and b["name"] == "submit_answer":
                    b["input"]["sentences"][0]["text"] += " — fine – yes"
            return resp

    assert "—" not in ask(Dashy(), ART, "Where is my Moon?", now=NOW).answer


def test_default_now_is_today():
    r = ask(MockProvider(), ART, "Which dasha is running right now?")
    assert r.verification["status"] == "verified" and datetime.now(tz=UTC).year >= 2026
