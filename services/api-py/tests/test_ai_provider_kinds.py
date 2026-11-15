"""Provider kinds: JSON tool protocol, CLI providers (mocked subprocess), HTTP providers (mocked
transport), CLI detection, key encryption, URL policy, presets, fallback and the assistant loop."""

import json
import subprocess
from pathlib import Path

import httpx
import pytest

from ankana_ai import MockProvider, ask
from ankana_ai import connections as cx
from ankana_ai import llm_providers as lp
from ankana_ai.config import HAIKU, OPUS, SONNET
from ankana_ai.eval.charts import EVAL_NOW, chart_artifact
from ankana_ai.providers import OllamaProvider, ProviderRequest, ProviderResponse
from ankana_ai.tools import SUBMIT_TOOL, tool_definitions

ART = chart_artifact("ananya-1995")
TOOLS = tool_definitions()


def req(messages=None, model="m", tools=None) -> ProviderRequest:
    return ProviderRequest(model=model, system="rules", chart_context="digest",
                           messages=messages or [{"role": "user", "content": "Where is my Moon?"}],
                           tools=tools if tools is not None else TOOLS)


def done(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


# ------------------------------------------------------------ JSON protocol
@pytest.mark.parametrize("text", [
    '{"tool_calls":[{"name":"get_birth_chart","arguments":{}}]}',
    '```json\n{"tool_calls":[{"name":"get_birth_chart","arguments":{}}]}\n```',
    'Sure! Here you go:\n{"tool_calls":[{"name":"get_birth_chart","input":{}}]}\nHope that helps.',
    '{"tool_calls":[{"tool":"get_birth_chart","arguments":"{}"}]}',
])
def test_protocol_parses_tool_calls(text):
    blocks = lp.JsonToolProtocol.parse(text, TOOLS)
    assert blocks and blocks[0]["name"] == "get_birth_chart" and blocks[0]["input"] == {}


def test_protocol_parses_submit_and_bare_answer():
    ans = {"language": "en", "sentences": [{"text": "x", "claims": []}]}
    a = lp.JsonToolProtocol.parse(json.dumps({"submit_answer": ans}), TOOLS)
    b = lp.JsonToolProtocol.parse(json.dumps(ans), TOOLS)
    assert a[0]["name"] == b[0]["name"] == SUBMIT_TOOL and a[0]["input"] == ans


@pytest.mark.parametrize("text", [
    "", "no json here", '{"tool_calls":[{"name":"not_a_tool","arguments":{}}]}',
    '{"tool_calls":"x"}', '{"tool_calls":[{"name":"get_birth_chart","arguments":[1]}]}',
    '{"unrelated":1}', '{"tool_calls":[',
])
def test_protocol_rejects_bad_replies(text):
    assert lp.JsonToolProtocol.parse(text, TOOLS) is None


def test_prompt_contains_schemas_transcript_and_rules():
    msgs = [{"role": "user", "content": "Q"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "get_birth_chart", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": '{"citationIndex":1}'}]}]
    prompt = lp.JsonToolProtocol.build_prompt(req(msgs))
    assert '"name":"get_birth_chart"' in prompt and "[TOOL_RESULT get_birth_chart]" in prompt
    assert "submit_answer" in prompt and "ONE JSON object" in prompt and "digest" in prompt


# ------------------------------------------------------------ CLI providers
CLAUDE_ENV = {"result": '{"tool_calls":[{"name":"get_birth_chart","arguments":{}}]}',
              "usage": {"input_tokens": 5, "output_tokens": 7}}


def test_claude_code_calls_cli_without_tools_or_key():
    seen = {}

    def runner(args, stdin, timeout, cwd):
        seen.update(args=args, stdin=stdin)
        return done(json.dumps(CLAUDE_ENV))

    p = lp.ClaudeCodeProvider(model="sonnet", binary="claude", runner=runner)
    r = p.complete(req())
    assert r.tool_calls[0]["name"] == "get_birth_chart" and r.stop_reason == "tool_use"
    assert r.usage["input_tokens"] == 5
    a = seen["args"]
    assert a[:3] == ["claude", "-p", "--output-format"] and a[a.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in a and "--no-session-persistence" in a
    assert "Where is my Moon?" in seen["stdin"]  # prompt via stdin, not argv


def test_cli_reprompts_once_on_bad_json_then_succeeds():
    replies = iter(["I think the Moon is in Cancer.", CLAUDE_ENV["result"]])
    prompts = []

    def runner(args, stdin, timeout, cwd):
        prompts.append(stdin)
        return done(json.dumps({"result": next(replies)}))

    r = lp.ClaudeCodeProvider(binary="claude", runner=runner).complete(req())
    assert r.tool_calls and len(prompts) == 2 and "previous reply was not valid" in prompts[1]


def test_cli_gives_plain_text_after_two_bad_replies():
    n = []

    def runner(args, stdin, timeout, cwd):
        n.append(1)
        return done(json.dumps({"result": "still prose"}))

    r = lp.ClaudeCodeProvider(binary="claude", runner=runner).complete(req())
    assert len(n) == 2 and r.stop_reason == "end_turn" and r.text == "still prose"


def test_claude_code_login_error_is_clear():
    def runner(args, stdin, timeout, cwd):
        return done(json.dumps({"is_error": True, "result": "Please login", "api_error_status": 401}))

    with pytest.raises(lp.ProviderError, match="not logged in"):
        lp.ClaudeCodeProvider(binary="claude", runner=runner).complete(req())


def test_cli_timeout_and_missing_binary(monkeypatch):
    def slow(args, stdin, timeout, cwd):
        raise subprocess.TimeoutExpired("claude", timeout)

    with pytest.raises(lp.ProviderError) as e:
        lp.ClaudeCodeProvider(binary="claude", runner=slow).complete(req())
    assert e.value.retryable
    monkeypatch.setattr(lp.shutil, "which", lambda name: None)
    monkeypatch.delenv("ANKANA_CODEX_BIN", raising=False)
    with pytest.raises(lp.ProviderError, match="not found"):
        lp.CodexProvider().complete(req())


def test_codex_exec_reads_last_message_file(tmp_path):
    seen = {}

    def runner(args, stdin, timeout, cwd):
        seen.update(args=args, cwd=cwd)
        Path(args[args.index("-o") + 1]).write_text(CLAUDE_ENV["result"], encoding="utf-8")
        return done("codex\n...\n")

    p = lp.CodexProvider(model="gpt-x", binary="codex", runner=runner)
    r = p.complete(req(model="claude-sonnet-5-5"))
    a = seen["args"]
    assert r.tool_calls[0]["name"] == "get_birth_chart"
    assert a[:2] == ["codex", "exec"] and "read-only" in a and a[-1] == "-"
    assert a[a.index("-m") + 1] == "gpt-x" and seen["cwd"]  # claude-* ids never reach codex


def test_codex_login_failure():
    def runner(args, stdin, timeout, cwd):
        return done("", "401 Unauthorized: please login", 1)

    with pytest.raises(lp.ProviderError, match="not logged in"):
        lp.CodexProvider(binary="codex", runner=runner).complete(req())


def test_gemini_cli_json_envelope_and_auth_error():
    seen = {}

    def ok(args, stdin, timeout, cwd):
        seen["args"] = args
        return done(json.dumps({"response": CLAUDE_ENV["result"], "stats": {"models": {
            "g": {"tokens": {"prompt": 11, "candidates": 3}}}}}))

    r = lp.GeminiCliProvider(model="gemini-2.5-flash", binary="gemini", runner=ok).complete(req(model=SONNET))
    assert r.tool_calls and r.usage == {"input_tokens": 11, "output_tokens": 3}
    assert seen["args"][seen["args"].index("-m") + 1] == "gemini-2.5-flash"

    def noauth(args, stdin, timeout, cwd):
        return done(json.dumps({"error": {"message": "Please set an Auth method", "code": 41}}))

    with pytest.raises(lp.ProviderError, match="not signed in"):
        lp.GeminiCliProvider(binary="gemini", runner=noauth).complete(req())


def test_cli_status_detects_missing_and_present(monkeypatch):
    monkeypatch.delenv("ANKANA_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(lp.shutil, "which", lambda n: None)
    ok, detail, path = lp.cli_status("claude", "ANKANA_CLAUDE_BIN")
    assert not ok and path is None and "not found" in detail
    monkeypatch.setattr(lp.shutil, "which", lambda n: "/bin/claude")
    ok, detail, path = lp.cli_status(
        "claude", "ANKANA_CLAUDE_BIN", lambda *a: done("2.1.0 (Claude Code)\n"))
    assert ok and detail.startswith("2.1.0") and path == "/bin/claude"
    ok, detail, _ = lp.cli_status("claude", "ANKANA_CLAUDE_BIN", lambda *a: done("", "boom", 1))
    assert not ok


# ------------------------------------------------------------- HTTP providers
def http_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_compatible_native_tools_roundtrip():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "gemini-2.5-flash", "usage": {"prompt_tokens": 9, "completion_tokens": 2},
            "choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "get_birth_chart", "arguments": "{}"}}]}}]})

    p = lp.OpenAICompatibleProvider(cx.GEMINI_OPENAI_URL, "KEY", "gemini-2.5-flash",
                                    http=http_client(handler))
    msgs = [{"role": "user", "content": "Q"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "get_birth_chart", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "{}"}]}]
    r = p.complete(req(msgs, model=SONNET))
    assert seen["url"].endswith("/v1beta/openai/chat/completions") and seen["auth"] == "Bearer KEY"
    assert seen["body"]["model"] == "gemini-2.5-flash"  # claude ids replaced by the configured model
    assert seen["body"]["tools"][0]["type"] == "function"
    roles = [m["role"] for m in seen["body"]["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    assert r.tool_calls[0]["id"] == "c1" and r.stop_reason == "tool_use" and r.usage["input_tokens"] == 9


def test_openai_compatible_http_errors_are_classified():
    p = lp.OpenAICompatibleProvider("https://x/v1", "k", "m", http=http_client(
        lambda r: httpx.Response(429, json={})))
    with pytest.raises(lp.ProviderError) as e:
        p.complete(req())
    assert e.value.retryable and e.value.status == 429

    def boom(request):
        raise httpx.ConnectError("refused")

    p = lp.OpenAICompatibleProvider("https://x/v1", "k", "m", http=http_client(boom))
    with pytest.raises(lp.ProviderError, match="Could not reach"):
        p.complete(req())


def test_ollama_local_and_cloud_use_native_tools_and_key_header():
    seen = []

    def handler(request: httpx.Request):
        seen.append((str(request.url), request.headers.get("authorization"),
                     json.loads(request.content)))
        return httpx.Response(200, json={"message": {"content": "", "tool_calls": [
            {"function": {"name": "get_birth_chart", "arguments": {}}}]},
            "prompt_eval_count": 4, "eval_count": 6})

    local = cx.build_provider("ollama_local", http=http_client(handler))
    cloud = cx.build_provider("ollama_cloud", api_key="OK", http=http_client(handler))
    assert isinstance(local, OllamaProvider)
    r1, r2 = local.complete(req(model=HAIKU)), cloud.complete(req(model="gpt-oss:20b"))
    assert seen[0][0] == "http://localhost:11434/api/chat" and seen[0][1] is None
    assert seen[1][0] == "https://ollama.com/api/chat" and seen[1][1] == "Bearer OK"
    assert seen[1][2]["model"] == "gpt-oss:20b" and seen[0][2]["tools"]
    assert r1.tool_calls and r1.usage == {"input_tokens": 4, "output_tokens": 6}
    assert r2.stop_reason == "tool_use"


def test_anthropic_kind_builds_with_api_key():
    p = cx.build_provider("anthropic", api_key="sk-ant-test")
    assert p.name == "anthropic" and p.client.api_key == "sk-ant-test"


# ------------------------------------------------------- crypto, policy, kinds
def test_key_encryption_roundtrip_and_requirements(monkeypatch):
    monkeypatch.setenv("ANKANA_SECRET_KEY", "unit-test-secret")
    token = cx.encrypt_key("sk-live-123")
    assert token.startswith("v1:") and "sk-live-123" not in token
    assert cx.decrypt_key(token) == "sk-live-123" and cx.decrypt_key(None) is None
    monkeypatch.setenv("ANKANA_SECRET_KEY", "another")
    with pytest.raises(lp.ProviderError, match="cannot be decrypted"):
        cx.decrypt_key(token)
    monkeypatch.delenv("ANKANA_SECRET_KEY")
    with pytest.raises(lp.ProviderError, match="not set"):
        cx.encrypt_key("x")
    assert cx.redact("bad key sk-1", "sk-1") == "bad key ***"


def test_local_provider_gating(monkeypatch):
    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS", raising=False)
    assert not any(cx.kind_allowed(k) for k in cx.LOCAL_KINDS)
    assert cx.kind_allowed("anthropic") and cx.kind_allowed("ollama_cloud")
    a = cx.availability("claude_code")
    assert a["status"] == "disabled" and not a["available"]
    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    assert all(cx.kind_allowed(k) for k in cx.LOCAL_KINDS)


def test_base_url_policy(monkeypatch):
    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS", raising=False)
    assert cx.validate_base_url("https://api.groq.com/openai/v1/", "openai_compatible") \
        == "https://api.groq.com/openai/v1"
    for bad in ("http://api.example.com/v1", "https://localhost:1234/v1",
                "https://127.0.0.1/v1", "https://10.0.0.5/v1", "https://169.254.169.254/",
                "ftp://x", "https://db.internal/v1"):
        with pytest.raises(ValueError):
            cx.validate_base_url(bad, "openai_compatible")
    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    assert cx.validate_base_url("http://localhost:1234/v1", "openai_compatible")


def test_kinds_match_db_check_constraint():
    from app.tenancy.models import AI_KINDS, AI_ROLES

    assert set(AI_KINDS) == set(cx.KIND_NAMES) and AI_ROLES == cx.ROLES
    logos = Path(__file__).resolve().parents[3] / "apps" / "web-practitioner" / "public" / "providers"
    for info in cx.KINDS.values():
        assert (logos / info.logo).exists(), info.logo


# ----------------------------------------------------------- tier + fallback
class Spy:
    name = "spy"

    def __init__(self):
        self.models = []

    def complete(self, request):
        self.models.append(request.model)
        return ProviderResponse([{"type": "text", "text": "ok"}], "end_turn",
                                {"input_tokens": 3, "output_tokens": 2}, request.model)


def test_tiered_provider_maps_claude_tiers_and_forced_model():
    models = cx.merged_models("ollama_cloud", {"fast": "tiny"})
    spy = Spy()
    t = cx.TieredProvider(spy, models)
    for m in (OPUS, SONNET, HAIKU):
        t.complete(req(model=m))
    assert spy.models == ["gpt-oss:120b", "gpt-oss:20b", "tiny"]
    spy2 = Spy()
    cx.TieredProvider(spy2, models, forced="custom").complete(req(model=OPUS))
    assert spy2.models == ["custom"]


class Failing:
    name = "failing"

    def complete(self, request):
        raise lp.ProviderError("connection refused", retryable=True)


def test_fallback_uses_next_and_counts_usage_per_kind():
    chain = cx.FallbackProvider([cx.ChainEntry("openai_compatible", "1", Failing()),
                                 cx.ChainEntry("ollama_cloud", "2", Spy())])
    chain.complete(req())
    chain.complete(req())
    assert chain.usage_by_kind == {"ollama_cloud": {"calls": 2, "tokens": 10}}
    assert "openai_compatible: connection refused" in chain.errors[0]
    dead = cx.FallbackProvider([cx.ChainEntry("a", "1", Failing()), cx.ChainEntry("b", "2", Failing())])
    with pytest.raises(lp.ProviderError, match="All AI connections failed"):
        dead.complete(req())


def view(i, kind, enabled=True, base_url=None):
    return cx.ConnView(str(i), kind, enabled, base_url, cx.merged_models(kind, None))


def test_presets_pick_connection_and_tier(monkeypatch):
    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    conns = [view(1, "ollama_cloud"), view(2, "anthropic"), view(3, "ollama_local"),
             view(4, "gemini", enabled=False)]
    q = {r["role"]: r for r in cx.plan_preset("best_quality", conns)}
    assert q["synthesise"]["connection_id"] == "2" and q["synthesise"]["model"] == OPUS
    c = {r["role"]: r for r in cx.plan_preset("lowest_cost", conns)}
    assert c["synthesise"]["connection_id"] == "3" and c["classify"]["model"] == "qwen3:4b"
    b = {r["role"]: r for r in cx.plan_preset("balanced", conns)}
    assert b["classify"]["model"] == HAIKU and b["report"]["model"] == OPUS
    lo = cx.plan_preset("local_only", conns)
    assert {r["connection_id"] for r in lo} == {"3"}
    assert cx.plan_preset("local_only", [view(1, "anthropic")]) == []
    lm = view(5, "openai_compatible", base_url="http://localhost:1234/v1")
    assert cx.plan_preset("local_only", [lm])[0]["connection_id"] == "5"
    with pytest.raises(ValueError):
        cx.plan_preset("nope", conns)


def test_presets_skip_local_kinds_when_not_allowed(monkeypatch):
    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS", raising=False)
    plan = cx.plan_preset("lowest_cost", [view(1, "ollama_local"), view(2, "ollama_cloud")])
    assert {r["connection_id"] for r in plan} == {"2"}


# --------------------------------------------- the assistant loop, end to end
class MockViaCli(lp.CliProvider):
    """A fake 'CLI model': MockProvider's decision, serialised as the JSON protocol reply.
    Proves tool calls and submit_answer survive prompt -> text -> parse, and the verifier runs."""

    name = "claude_code"
    binary_name = "claude"

    def __init__(self, behavior="faithful"):
        super().__init__()
        self.mock = MockProvider(behavior)
        self.last = None

    def complete(self, request):
        self.last = request
        return super().complete(request)

    def _ask(self, prompt, model):
        resp = self.mock.complete(self.last)
        calls = [{"name": b["name"], "arguments": b["input"]} for b in resp.tool_calls]
        if calls and calls[0]["name"] == SUBMIT_TOOL:
            return "```json\n" + json.dumps({"submit_answer": resp.tool_calls[0]["input"]}) + "\n```", {}
        return "Here:\n" + json.dumps({"tool_calls": calls}), {}


def test_assistant_loop_runs_over_json_tool_protocol_and_verifies():
    res = ask(MockViaCli(), ART, "Where is my Moon?", now=EVAL_NOW)
    assert res.tools_used and not res.refused
    assert res.verification["claimsFailed"] == 0 and res.verification["claimsChecked"] > 0


def test_verifier_still_catches_wrong_claims_over_cli_protocol():
    res = ask(MockViaCli("wrong_always"), ART, "Where is my Moon?", now=EVAL_NOW)
    assert res.verification["claimsFailed"] > 0  # replaced by the chart fact, flagged
    assert "Could not verify" in res.answer


def test_assistant_falls_back_to_next_connection():
    chain = cx.FallbackProvider([cx.ChainEntry("openai_compatible", "1", Failing()),
                                 cx.ChainEntry("mock", "2", MockProvider())])
    res = ask(chain, ART, "Where is my Moon?", now=EVAL_NOW)
    assert res.verification["claimsFailed"] == 0 and res.tools_used
    assert chain.usage_by_kind["mock"]["calls"] == res.rounds
    assert len(chain.errors) == res.rounds  # primary failed on every call, fallback served all
