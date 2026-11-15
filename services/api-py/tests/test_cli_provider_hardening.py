"""CLI subprocess providers: env scrubbing, output and time caps, argument safety."""

import json
import subprocess
import sys

import pytest

from ankana_ai import llm_providers as lp
from ankana_ai.llm_providers import ClaudeCodeProvider, ProviderError, valid_model
from ankana_ai.providers import ProviderRequest

PY = sys.executable


def test_child_env_is_scrubbed(monkeypatch):
    for k in ("ANKANA_SECRET_KEY", "API_DATABASE_URL", "AUTH_SIGNING_KEY_PEM",
              "ANTHROPIC_API_KEY", "AZURE_STORAGE_CONNECTION_STRING", "SMTP_PASSWORD"):
        monkeypatch.setenv(k, "leak-me")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/keep")
    proc = lp._run([PY, "-c", "import os,json;print(json.dumps(dict(os.environ)))"], "", 20, None)
    seen = json.loads(proc.stdout)
    assert not [k for k in seen if "leak" in seen[k]]
    assert "PATH" in {k.upper() for k in seen} and seen.get("CLAUDE_CONFIG_DIR") == "/keep"


def test_large_prompt_goes_through_stdin_and_is_not_truncated():
    prompt = "x" * 2_000_000
    proc = lp._run([PY, "-c", "import sys;print(len(sys.stdin.read()))"], prompt, 30, None)
    assert proc.stdout.strip() == "2000000"


def test_output_is_capped_and_the_child_is_killed(monkeypatch):
    monkeypatch.setattr(lp, "MAX_CLI_OUTPUT_BYTES", 200_000)
    with pytest.raises(lp.CliOutputTooLarge):
        lp._run([PY, "-c", "import sys\nwhile True: sys.stdout.write('y'*65536); sys.stdout.flush()"],
                "", 30, None)


def test_timeout_kills_the_child():
    with pytest.raises(subprocess.TimeoutExpired):
        lp._run([PY, "-c", "import time;time.sleep(30)"], "", 1, None)


def test_provider_maps_oversize_and_timeout_to_provider_errors(monkeypatch):
    def too_big(*a):
        raise lp.CliOutputTooLarge("big")

    def slow(*a):
        raise subprocess.TimeoutExpired("x", 1)

    req = ProviderRequest(model="sonnet", system="s", chart_context="", messages=[
        {"role": "user", "content": "q"}], tools=[], max_tokens=10)
    for runner in (too_big, slow):
        with pytest.raises(ProviderError):
            ClaudeCodeProvider(binary="claude", runner=runner).complete(req)


@pytest.mark.parametrize("bad", ["--dangerously-skip-permissions", "x\" & calc & \"", "a b",
                                 "m;rm -rf /", "$(id)", "-m", "a\nb", ""])
def test_unsafe_model_names_are_refused(bad):
    assert not valid_model(bad)


@pytest.mark.parametrize("good", ["sonnet", "claude-sonnet-4-5-20250929", "qwen3:32b",
                                  "gpt-oss:120b", "models/gemini-2.5-pro", "o4-mini"])
def test_normal_model_names_pass(good):
    assert valid_model(good)


def test_cli_provider_refuses_a_bad_model_before_spawning():
    called = []
    req = ProviderRequest(model="--evil", system="s", chart_context="", messages=[
        {"role": "user", "content": "q"}], tools=[], max_tokens=10)
    p = ClaudeCodeProvider(binary="claude", runner=lambda *a: called.append(a))
    with pytest.raises(ProviderError):
        p.complete(req)
    assert not called


def test_prompt_is_never_in_argv():
    seen = {}

    def runner(args, stdin, timeout, cwd):
        seen.update(args=args, stdin=stdin)
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": "{}"}), "")

    req = ProviderRequest(model="sonnet", system="SECRET-PROMPT-TEXT", chart_context="",
                          messages=[{"role": "user", "content": "q"}], tools=[], max_tokens=10)
    ClaudeCodeProvider(binary="claude", runner=runner).complete(req)
    assert not any("SECRET-PROMPT-TEXT" in a for a in seen["args"])
    assert "SECRET-PROMPT-TEXT" in seen["stdin"]


def test_fallback_errors_do_not_echo_raw_exception_text():
    from ankana_ai.connections import ChainEntry, FallbackProvider

    class Boom:
        name = "boom"

        def complete(self, request):
            raise RuntimeError("https://internal.example/?key=sk-SECRET")

    req = ProviderRequest(model="m", system="s", chart_context="", messages=[], tools=[],
                          max_tokens=1)
    with pytest.raises(ProviderError) as exc:
        FallbackProvider([ChainEntry("anthropic", "1", Boom())]).complete(req)
    assert "sk-SECRET" not in str(exc.value) and "RuntimeError" in str(exc.value)
