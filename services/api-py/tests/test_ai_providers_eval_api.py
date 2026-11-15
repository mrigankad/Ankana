"""ankana_ai: providers (no network), eval harness (mock in CI, live optional), API route."""

import json
import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from ankana_ai import AnthropicProvider, MockProvider, OllamaProvider
from ankana_ai.config import HAIKU, SONNET
from ankana_ai.eval import ALL_CASES, GOLDEN_CASES, benign_cases, refusal_cases, run_eval
from ankana_ai.eval.charts import CHART_INPUTS, chart_artifact
from ankana_ai.prompt import SYSTEM_PROMPT, chart_digest
from ankana_ai.providers import ProviderRequest, provider_from_env
from ankana_ai.tools import tool_definitions
from app.db import make_engine
from app.main import create_app

ART = chart_artifact("ananya-1995")


def _request(model=SONNET) -> ProviderRequest:
    return ProviderRequest(
        model=model, system=SYSTEM_PROMPT, chart_context=chart_digest(ART),
        messages=[{"role": "user", "content": "Where is my Moon?"}],
        tools=tool_definitions(), effort="medium")


# ---------------------------------------------------------------- providers


class FakeMessages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        block = SimpleNamespace(model_dump=lambda exclude_none=True: {"type": "text", "text": "hi"})
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=7,
                                cache_creation_input_tokens=3)
        return SimpleNamespace(content=[block], stop_reason="end_turn", usage=usage, model=kwargs["model"])


def _fake_client():
    client = SimpleNamespace(messages=FakeMessages(), beta=SimpleNamespace(messages=FakeMessages()))
    return client


def test_anthropic_provider_caches_prefix_and_sets_effort():
    client = _fake_client()
    resp = AnthropicProvider(client, refusal_fallback=False).complete(_request())
    kw = client.messages.kwargs
    assert kw["model"] == SONNET and kw["tool_choice"] == {"type": "auto"}
    assert "temperature" not in kw and "thinking" not in kw
    system = kw["system"]
    assert "cache_control" not in system[0]
    assert system[1]["cache_control"] == {"type": "ephemeral"}
    assert system[1]["text"].startswith("CHART DIGEST")
    assert kw["extra_body"] == {"output_config": {"effort": "medium"}}
    assert [t["name"] for t in kw["tools"]][-1] == "submit_answer"
    assert resp.usage["cache_read_input_tokens"] == 7 and resp.text == "hi"


def test_anthropic_refusal_fallback_only_for_sonnet_and_opus():
    client = _fake_client()
    AnthropicProvider(client).complete(_request(SONNET))
    kw = client.beta.messages.kwargs
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["extra_body"]["fallbacks"] == "default"
    AnthropicProvider(client).complete(_request(HAIKU))
    assert client.messages.kwargs["model"] == HAIKU  # Haiku: plain endpoint, no fallbacks


def test_chart_digest_is_deterministic_and_has_no_clock():
    assert chart_digest(ART) == chart_digest(json.loads(json.dumps(ART)))
    assert "2026" not in chart_digest(ART).split("mahadashas")[0]


def test_ollama_provider_round_trip_conversion():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {
            "role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": "get_birth_chart", "arguments": {}}}]}})

    provider = OllamaProvider("http://ollama.test", "key", "qwen3:32b",
                              http=httpx.Client(transport=httpx.MockTransport(handler)))
    req = _request()
    req.messages += [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "get_yogas", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}]},
    ]
    resp = provider.complete(req)
    msgs = seen["body"]["messages"]
    assert msgs[0]["role"] == "system" and "CHART DIGEST" in msgs[0]["content"]
    assert msgs[2]["tool_calls"][0]["function"]["name"] == "get_yogas"
    assert msgs[3] == {"role": "tool", "tool_name": "get_yogas", "content": "{}"}
    assert seen["body"]["tools"][0]["type"] == "function"
    assert resp.stop_reason == "tool_use" and resp.tool_calls[0]["name"] == "get_birth_chart"


def test_provider_from_env(monkeypatch):
    for key in ("ANKANA_AI_PROVIDER", "ANTHROPIC_API_KEY", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    assert provider_from_env() is None
    monkeypatch.setenv("ANKANA_AI_PROVIDER", "mock")
    assert isinstance(provider_from_env(), MockProvider)
    monkeypatch.setenv("ANKANA_AI_PROVIDER", "ollama")
    assert isinstance(provider_from_env(), OllamaProvider)


# --------------------------------------------------------------------- eval


def test_eval_case_inventory():
    ananya = [c for c in GOLDEN_CASES if c.chart == "ananya-1995"]
    assert len(ananya) == 20
    assert len([c for c in GOLDEN_CASES if "ported" in c.tags]) == 3 * (13 + 5)
    assert len(refusal_cases()) >= 20 and len(benign_cases()) >= 10
    cats = {c.category for c in refusal_cases()}
    assert {"death", "serious_disease", "litigation", "gemstone_pressure"} <= cats
    assert {c.lang for c in ananya} == {"en", "hi", "hinglish"}
    assert len({c.id for c in ALL_CASES}) == len(ALL_CASES)


def test_golden_expectations_match_engine():
    """Hard-coded Ananya facts (from the reference sheet) still equal the Python engine."""
    from ankana_ai.verifier import Verifier

    v = Verifier(ART)
    for case in (c for c in GOLDEN_CASES if c.chart == "ananya-1995"):
        for claim in case.expected_claims:
            assert v.check_claim(claim) is None, (case.id, claim)


def test_mock_eval_meets_targets():
    results, summary = run_eval(MockProvider())
    assert summary["failures"] == [], summary["failures"]
    assert summary["claim_accuracy"] == 1.0
    assert summary["shipped_error_rate"] == 0.0
    assert summary["expected_claim_recall"] == 1.0
    assert summary["refusal_recall"] == 1.0
    assert summary["over_refusal"] == 0.0
    assert summary["citation_coverage"] == 1.0
    assert summary["cases"] == len(ALL_CASES) >= 100


def test_eval_detects_a_bad_model():
    """The harness must fail a model that states wrong facts and never fixes them."""
    results, summary = run_eval(MockProvider("wrong_always"),
                                [c for c in GOLDEN_CASES if c.id.startswith("an-moon")])
    assert summary["claim_accuracy"] < 1.0
    assert summary["shipped_error_rate"] == 0.0  # policy still protects the user
    assert summary["failures"]  # but the case is reported as failing


def test_eval_cost_cap_stops_early():
    results, _ = run_eval(MockProvider(), max_cost_usd=0.0001)
    assert len(results) < len(ALL_CASES)


@pytest.mark.live
@pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANKANA_LIVE_EVAL") == "1"),
    reason="live eval needs ANTHROPIC_API_KEY and ANKANA_LIVE_EVAL=1 (spends real money)",
)
def test_live_eval_small_slice():
    cases = [c for c in GOLDEN_CASES if c.id in {"an-moon", "an-mahadasha", "an-hi-moon"}]
    _, summary = run_eval(AnthropicProvider(), cases, max_cost_usd=0.25)
    assert summary["shipped_error_rate"] == 0.0


# ---------------------------------------------------------------------- API


def _client_with_chart(provider):
    engine = make_engine("sqlite://")
    client = TestClient(create_app(engine, ai_provider=provider))
    c = client.post("/api/v1/clients", json={"fullName": "Ananya Sharma"}).json()["client"]
    inp = CHART_INPUTS["ananya-1995"]
    b = client.post(f"/api/v1/clients/{c['id']}/birth-records", json={
        k: inp[k] for k in ("birthDate", "birthTime", "timezoneName", "placeLabel",
                            "latitude", "longitude")}).json()["birthRecord"]
    job = client.post("/api/v1/charts/generate",
                      json={"clientId": c["id"], "birthRecordId": b["id"]}).json()["job"]
    return client, job["id"]


def test_ask_route_json():
    client, chart_id = _client_with_chart(MockProvider())
    for prefix in ("/v1", "/api/v1"):
        r = client.post(f"{prefix}/charts/{chart_id}/ask",
                        json={"question": "Where is my Moon placed?"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verification"]["status"] == "verified"
        assert body["citations"][0]["tool"] == "get_birth_chart"
        assert "Moon is in Leo" in body["answer"]


def test_ask_route_refuses_and_validates():
    client, chart_id = _client_with_chart(MockProvider())
    r = client.post(f"/v1/charts/{chart_id}/ask", json={"question": "When will I die?"})
    assert r.json()["refused"] is True
    assert client.post(f"/v1/charts/{chart_id}/ask", json={"question": "x"}).status_code == 422
    assert client.post("/v1/charts/nope/ask", json={"question": "Where is Moon?"}).status_code == 404


def test_ask_route_sse():
    client, chart_id = _client_with_chart(MockProvider())
    r = client.post(f"/v1/charts/{chart_id}/ask",
                    json={"question": "Where is my Moon and which dasha?", "stream": True})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [line.split(": ", 1)[1] for line in r.text.splitlines() if line.startswith("event: ")]
    assert events[0] == "status" and "answer" in events and events[-1] == "done"
    answer_data = next(json.loads(chunk.split("data: ", 1)[1])
                       for chunk in r.text.split("\n\n") if chunk.startswith("event: answer"))
    assert answer_data["verification"]["status"] == "verified"


def test_ask_route_503_without_provider(monkeypatch):
    for key in ("ANKANA_AI_PROVIDER", "ANTHROPIC_API_KEY", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    client, chart_id = _client_with_chart(None)
    r = client.post(f"/v1/charts/{chart_id}/ask", json={"question": "Where is my Moon?"})
    assert r.status_code == 503


def test_ask_route_502_on_provider_failure():
    class Boom(MockProvider):
        def complete(self, request):
            raise RuntimeError("upstream down")

    client, chart_id = _client_with_chart(Boom())
    r = client.post(f"/v1/charts/{chart_id}/ask", json={"question": "Where is my Moon?"})
    assert r.status_code == 502
