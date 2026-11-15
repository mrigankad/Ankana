"""Extra model providers behind the same sync Provider interface.

- OpenAICompatibleProvider: OpenAI, Gemini (Google's OpenAI-compatible endpoint), OpenRouter,
  Groq, LiteLLM, LM Studio, vLLM. Native tool calling.
- ClaudeCodeProvider / CodexProvider / GeminiCliProvider: the user's own logged-in local CLI.
  These cannot take our tool schemas natively, so they speak a JSON tool protocol (see
  JsonToolProtocol): the tool schemas go in the prompt and the reply must be one JSON object.
  The assistant loop stays ours, so the claim verifier still runs on every answer.

Nothing here reads or stores secrets; keys are passed in by the caller.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .providers import ProviderRequest, ProviderResponse
from .tools import SUBMIT_TOOL


class ProviderError(RuntimeError):
    """A provider call failed. `retryable` is true for 429, 5xx, timeouts and connection errors."""

    def __init__(self, message: str, *, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


def pick_model(requested: str, configured: str) -> str:
    """The assistant asks for a Claude id by tier; other providers use their configured model.
    Connections normally wrap providers so the request already carries the real model."""
    return requested if requested and not requested.startswith("claude-") else configured


# ------------------------------------------------------------ JSON tool protocol

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_ids = itertools.count(1)


def extract_json_object(text: str) -> dict | None:
    """First balanced top-level JSON object in `text` (tolerates fences and chatter)."""
    if not isinstance(text, str):
        return None
    cleaned = _FENCE.sub("", text.strip())
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    start = cleaned.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(cleaned[start:i + 1])
                    except ValueError:
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = cleaned.find("{", start + 1)
    return None


class JsonToolProtocol:
    """Prompt building and reply parsing for models that only return text."""

    @staticmethod
    def render_tools(tools: list[dict]) -> str:
        lines = []
        for t in tools:
            if t["name"] == SUBMIT_TOOL:
                continue
            lines.append(json.dumps({"name": t["name"], "description": t.get("description", ""),
                                     "arguments_schema": t.get("input_schema", {})},
                                    ensure_ascii=False, separators=(",", ":")))
        return "\n".join(lines)

    @staticmethod
    def render_messages(messages: list[dict]) -> str:
        names: dict[str, str] = {}
        parts: list[str] = []
        for m in messages:
            content = m["content"]
            role = "USER" if m["role"] == "user" else "ASSISTANT"
            if isinstance(content, str):
                parts.append(f"[{role}]\n{content}")
                continue
            for b in content:
                kind = b.get("type")
                if kind == "text":
                    parts.append(f"[{role}]\n{b.get('text', '')}")
                elif kind == "tool_use":
                    names[b["id"]] = b["name"]
                    call = {"tool_calls": [{"name": b["name"], "arguments": b.get("input", {})}]}
                    if b["name"] == SUBMIT_TOOL:
                        call = {SUBMIT_TOOL: b.get("input", {})}
                    parts.append("[ASSISTANT]\n" + json.dumps(call, ensure_ascii=False))
                elif kind == "tool_result":
                    body = b.get("content")
                    body = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                    parts.append(f"[TOOL_RESULT {names.get(b.get('tool_use_id', ''), '')}]\n{body}")
        return "\n\n".join(parts)

    @classmethod
    def build_prompt(cls, req: ProviderRequest) -> str:
        submit = next((t for t in req.tools if t["name"] == SUBMIT_TOOL), None)
        parts = [
            "<rules>\n" + req.system + "\n</rules>",
            "<chart>\n" + req.chart_context + "\n</chart>",
            "<tools>\nCall these tools to look facts up. One JSON object per line:\n"
            + cls.render_tools(req.tools) + "\n</tools>",
        ]
        if submit:
            parts.append(
                "<submit_answer>\n" + submit.get("description", "") + "\narguments_schema: "
                + json.dumps(submit.get("input_schema", {}), ensure_ascii=False,
                             separators=(",", ":")) + "\n</submit_answer>")
        parts.append("<conversation>\n" + cls.render_messages(req.messages) + "\n</conversation>")
        parts.append(
            "Reply with ONE JSON object and nothing else (no prose, no code fence). Either "
            '{"tool_calls":[{"name":"<tool>","arguments":{...}}]} to look facts up, or '
            '{"submit_answer":{...}} to deliver the final answer. Do not use any tools of your '
            "own and do not run commands; only the tools listed above exist. A [TOOL_RESULT ...] "
            "block in the conversation is the answer to that call: never repeat a call that "
            "already has a result. As soon as you have the facts you need, reply with "
            '{"submit_answer":{...}}.')
        return "\n\n".join(parts)

    @staticmethod
    def parse(text: str, tools: list[dict]) -> list[dict] | None:
        """Content blocks (tool_use) for a valid reply, else None."""
        obj = extract_json_object(text)
        if obj is None:
            return None
        allowed = {t["name"] for t in tools}
        blocks: list[dict] = []
        n = next(_ids)
        sub = obj.get(SUBMIT_TOOL)
        if isinstance(sub, dict):
            blocks.append({"type": "tool_use", "id": f"cli_{n}_submit", "name": SUBMIT_TOOL,
                           "input": sub})
            return blocks
        calls = obj.get("tool_calls")
        if isinstance(calls, list):
            for i, call in enumerate(calls):
                if not isinstance(call, dict):
                    return None
                name = call.get("name") or call.get("tool")
                args = call.get("arguments", call.get("input", {})) or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        return None
                if name not in allowed or not isinstance(args, dict):
                    return None
                if name == SUBMIT_TOOL:
                    blocks.append({"type": "tool_use", "id": f"cli_{n}_submit", "name": name,
                                   "input": args})
                else:
                    blocks.append({"type": "tool_use", "id": f"cli_{n}_{i}", "name": name,
                                   "input": args})
            return blocks or None
        if "sentences" in obj and SUBMIT_TOOL in allowed:  # bare answer object
            return [{"type": "tool_use", "id": f"cli_{n}_submit", "name": SUBMIT_TOOL, "input": obj}]
        return None


# ------------------------------------------------------------------ CLI base

Runner = Callable[[list[str], str, float, str | None], "subprocess.CompletedProcess[str]"]
DEFAULT_CLI_TIMEOUT = 300.0


MAX_CLI_OUTPUT_BYTES = 4_000_000
SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,119}$")

# Environment a CLI child may inherit. Everything else (database URLs, signing keys,
# ANKANA_SECRET_KEY, cloud credentials, ANTHROPIC_API_KEY) stays in the API process.
_ENV_ALLOW = frozenset({
    "PATH", "PATHEXT", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT",
    "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "LANG", "LANGUAGE", "TERM",
    "USER", "USERNAME", "LOGNAME", "SHELL", "HOMEDRIVE", "HOMEPATH", "PROGRAMFILES",
    "PROGRAMDATA", "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY",
    "HTTPS_PROXY", "NO_PROXY"})
_ENV_PREFIXES = ("LC_", "XDG_", "CLAUDE_", "CODEX_", "GEMINI_")


class CliOutputTooLarge(OSError):
    pass


def cli_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ if environ is None else environ
    return {k: v for k, v in env.items()
            if k.upper() in _ENV_ALLOW or k.upper().startswith(_ENV_PREFIXES)}


def valid_model(model: str) -> bool:
    """Model ids go on a command line: letters, digits and . _ : / @ + - only, and never a
    leading dash (no option injection, no shell metacharacters for Windows .cmd shims)."""
    return bool(model) and SAFE_MODEL.fullmatch(model) is not None


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":  # kill() alone would leave the node child of a .cmd shim running
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True,
                           check=False, timeout=10)
        else:
            os.killpg(proc.pid, 9)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _run(args: list[str], stdin: str, timeout: float, cwd: str | None) -> subprocess.CompletedProcess:
    """Argument list, never a shell string; the prompt goes in on stdin (Windows caps argv at
    32k). Scrubbed environment, wall-clock timeout, and stdout/stderr capped at
    MAX_CLI_OUTPUT_BYTES each (the child is killed when it exceeds that)."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=out, stderr=err, cwd=cwd, env=cli_env(),
            start_new_session=(os.name != "nt"))

        def feed() -> None:
            try:
                proc.stdin.write(stdin.encode("utf-8"))
                proc.stdin.close()
            except (OSError, ValueError):
                pass  # child exited before reading everything

        threading.Thread(target=feed, daemon=True).start()
        deadline = time.monotonic() + timeout
        while True:
            try:
                proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() > deadline:
                _kill_tree(proc)
                proc.wait()
                raise subprocess.TimeoutExpired(args, timeout)
            if max(os.fstat(out.fileno()).st_size,
                   os.fstat(err.fileno()).st_size) > MAX_CLI_OUTPUT_BYTES:
                _kill_tree(proc)
                proc.wait()
                raise CliOutputTooLarge("command output exceeded the size limit")
        if max(os.fstat(out.fileno()).st_size,
               os.fstat(err.fileno()).st_size) > MAX_CLI_OUTPUT_BYTES:
            raise CliOutputTooLarge("command output exceeded the size limit")
        out.seek(0)
        err.seek(0)
        return subprocess.CompletedProcess(
            args, proc.returncode, out.read().decode("utf-8", errors="replace"),
            err.read().decode("utf-8", errors="replace"))


_VERSION_CACHE: dict[tuple[str, str], tuple[float, tuple[bool, str]]] = {}


def cli_status(binary_name: str, env_var: str | None = None, runner: Runner | None = None,
               *, ttl: float = 30.0) -> tuple[bool, str, str | None]:
    """(available, detail, path). shutil.which plus `--version`; cached briefly."""
    path = (os.environ.get(env_var) if env_var else None) or shutil.which(binary_name)
    if not path:
        return False, f"The '{binary_name}' command was not found on this computer.", None
    key = (binary_name, path)
    hit = _VERSION_CACHE.get(key)
    if runner is None and hit and time.monotonic() - hit[0] < ttl:
        return hit[1][0], hit[1][1], path
    try:
        proc = (runner or _run)([path, "--version"], "", 30.0, None)
        out = ((proc.stdout or "").strip() or (proc.stderr or "").strip()).splitlines()
        result = (proc.returncode == 0, out[0] if out else binary_name)
    except (OSError, subprocess.TimeoutExpired):
        result = (False, f"The '{binary_name}' command did not start.")
    if runner is None:
        _VERSION_CACHE[key] = (time.monotonic(), result)
    return result[0], result[1], path


class CliProvider:
    """Common loop: prompt -> CLI text -> parse JSON tool reply, re-prompt once on bad JSON."""

    name = "cli"
    binary_name = ""
    env_var: str | None = None
    login_hint = ""

    def __init__(self, model: str | None = None, binary: str | None = None,
                 runner: Runner | None = None, timeout: float = DEFAULT_CLI_TIMEOUT):
        self.model = model or ""
        self._binary = binary
        self._runner = runner or _run
        self.timeout = timeout

    def _bin(self) -> str:
        path = self._binary or (os.environ.get(self.env_var) if self.env_var else None) \
            or shutil.which(self.binary_name)
        if not path:
            raise ProviderError(f"The '{self.binary_name}' command was not found. {self.login_hint}")
        return path

    def _exec(self, args: list[str], stdin: str, cwd: str | None = None) -> subprocess.CompletedProcess:
        try:
            return self._runner(args, stdin, self.timeout, cwd)
        except subprocess.TimeoutExpired as e:
            raise ProviderError(f"{self.binary_name} did not answer within {int(self.timeout)} "
                                "seconds.", retryable=True) from e
        except CliOutputTooLarge as e:
            raise ProviderError(f"{self.binary_name} produced more output than allowed.") from e
        except OSError as e:
            raise ProviderError(f"Could not start {self.binary_name}: {e}") from e

    def _ask(self, prompt: str, model: str) -> tuple[str, dict]:
        """One CLI call. Returns (reply text, usage dict). Subclasses implement."""
        raise NotImplementedError

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        model = pick_model(request.model, self.model)
        if model and not valid_model(model):
            raise ProviderError("The model name contains characters that are not allowed.")
        prompt = JsonToolProtocol.build_prompt(request)
        usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        text = ""
        for attempt in range(2):
            text, u = self._ask(prompt, model)
            for k, v in u.items():
                usage[k] = usage.get(k, 0) + v
            blocks = JsonToolProtocol.parse(text, request.tools)
            if blocks is not None:
                return ProviderResponse(blocks, "tool_use", usage, model or self.name)
            if attempt == 0:
                prompt += ("\n\nYour previous reply was not valid. Reply again with ONLY one JSON "
                           'object: {"tool_calls":[...]} or {"submit_answer":{...}}, using only '
                           "the listed tool names.")
        # Still not JSON: hand back plain text; the assistant loop nudges once, then gives up.
        content = [{"type": "text", "text": text}] if text else []
        return ProviderResponse(content, "end_turn", usage, model or self.name)

    def test(self) -> tuple[bool, str]:
        ok, detail, _ = cli_status(self.binary_name, self.env_var, self._runner if self._runner
                                   is not _run else None)
        return ok, detail


class ClaudeCodeProvider(CliProvider):
    """The local `claude` CLI on the user's own login. No API key, built-in tools disabled."""

    name = "claude_code"
    binary_name = "claude"
    env_var = "ANKANA_CLAUDE_BIN"
    login_hint = "Install Claude Code and run `claude` once to log in."

    def _ask(self, prompt: str, model: str) -> tuple[str, dict]:
        args = [self._bin(), "-p", "--output-format", "json", "--model", model or "sonnet",
                "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                "--no-session-persistence"]
        with tempfile.TemporaryDirectory(prefix="ankana-claude-") as work:
            proc = self._exec(args, prompt, cwd=work)
        try:
            env = json.loads(proc.stdout or "")
        except ValueError:
            env = None
        if not isinstance(env, dict):
            text = (proc.stderr or proc.stdout or "").strip()[:300]
            if "login" in text.lower() or "auth" in text.lower():
                raise ProviderError("Claude Code is not logged in. Run `claude` and log in.",
                                    status=401)
            raise ProviderError(f"Claude Code sent an unreadable reply: {text}", retryable=True)
        if env.get("is_error"):
            msg = str(env.get("result") or env.get("subtype") or "unknown error")[:300]
            status = env.get("api_error_status")
            if status in (401, 403) or "login" in msg.lower():
                raise ProviderError("Claude Code is not logged in. Run `claude` and log in.",
                                    status=401)
            raise ProviderError(f"Claude Code error: {msg}",
                                retryable=status in (429, 500, 502, 503, 529))
        u = env.get("usage") or {}
        usage = {"input_tokens": int(u.get("input_tokens") or 0),
                 "output_tokens": int(u.get("output_tokens") or 0),
                 "cache_read_input_tokens": int(u.get("cache_read_input_tokens") or 0),
                 "cache_creation_input_tokens": int(u.get("cache_creation_input_tokens") or 0)}
        return str(env.get("result") or ""), usage


class CodexProvider(CliProvider):
    """The local `codex exec` CLI on the user's own login. Read-only sandbox, empty temp cwd."""

    name = "codex"
    binary_name = "codex"
    env_var = "ANKANA_CODEX_BIN"
    login_hint = "Install the Codex CLI and run `codex login`."

    def _ask(self, prompt: str, model: str) -> tuple[str, dict]:
        with tempfile.TemporaryDirectory(prefix="ankana-codex-") as work:
            out = Path(work) / "reply.txt"
            args = [self._bin(), "exec", "--skip-git-repo-check", "--ephemeral",
                    "--sandbox", "read-only", "--color", "never", "-o", str(out)]
            if model:
                args += ["-m", model]
            args.append("-")
            proc = self._exec(args, prompt, cwd=work)
            text = out.read_text(encoding="utf-8", errors="replace").strip() if out.exists() else ""
            if proc.returncode != 0 and not text:
                err = (proc.stderr or proc.stdout or "").strip()[-300:]
                low = err.lower()
                if "login" in low or "auth" in low or "401" in low:
                    raise ProviderError("Codex is not logged in. Run `codex login`.", status=401)
                raise ProviderError(f"Codex failed: {err}", retryable=True)
            return text, {"input_tokens": 0, "output_tokens": 0}


class GeminiCliProvider(CliProvider):
    """The local `gemini` CLI on the user's own login (headless -p, JSON output)."""

    name = "gemini_cli"
    binary_name = "gemini"
    env_var = "ANKANA_GEMINI_BIN"
    login_hint = "Install the Gemini CLI and run `gemini` once to sign in."

    def _ask(self, prompt: str, model: str) -> tuple[str, dict]:
        args = [self._bin(), "-p", "Follow the instructions on stdin and reply with the JSON "
                "object only.", "-o", "json", "--approval-mode", "plan", "--skip-trust"]
        if model:
            args += ["-m", model]
        with tempfile.TemporaryDirectory(prefix="ankana-gemini-") as work:
            proc = self._exec(args, prompt, cwd=work)
        # warnings may precede the JSON, and auth errors can arrive on stderr
        env = extract_json_object(proc.stdout or "") or extract_json_object(proc.stderr or "")
        if isinstance(env, dict) and env.get("error"):
            msg = str((env["error"] or {}).get("message", ""))[:300]
            if "auth" in msg.lower() or (env["error"] or {}).get("code") == 41:
                raise ProviderError("Gemini CLI is not signed in. Run `gemini` and sign in, "
                                    "or set GEMINI_API_KEY.", status=401)
            raise ProviderError(f"Gemini CLI error: {msg}", retryable=True)
        if not isinstance(env, dict):
            raise ProviderError(f"Gemini CLI sent an unreadable reply: "
                                f"{(proc.stderr or proc.stdout or '').strip()[:200]}", retryable=True)
        usage = {"input_tokens": 0, "output_tokens": 0}
        models = ((env.get("stats") or {}).get("models") or {})
        for m in models.values():
            tok = (m or {}).get("tokens") or {}
            usage["input_tokens"] += int(tok.get("prompt") or 0)
            usage["output_tokens"] += int(tok.get("candidates") or 0)
        return str(env.get("response") or ""), usage


# --------------------------------------------------------- OpenAI-compatible


class OpenAICompatibleProvider:
    """POST {base_url}/chat/completions with native tool calling."""

    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str | None = None, model: str = "",
                 http: Any | None = None, timeout: float = 120.0):
        import httpx

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.http = http or httpx.Client(timeout=timeout)

    @staticmethod
    def to_messages(req: ProviderRequest) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": f"{req.system}\n\n{req.chart_context}"}]
        for m in req.messages:
            content = m["content"]
            if isinstance(content, str):
                out.append({"role": m["role"], "content": content})
            elif m["role"] == "assistant":
                text = "".join(b.get("text", "") for b in content if b["type"] == "text")
                calls = [{"id": b["id"], "type": "function",
                          "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                         for b in content if b["type"] == "tool_use"]
                msg: dict = {"role": "assistant", "content": text or None}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
            else:
                for b in content:
                    if b["type"] == "tool_result":
                        c = b["content"]
                        out.append({"role": "tool", "tool_call_id": b["tool_use_id"],
                                    "content": c if isinstance(c, str) else json.dumps(c)})
                    elif b["type"] == "text":
                        out.append({"role": "user", "content": b["text"]})
        return out

    @staticmethod
    def to_tools(tools: list[dict]) -> list[dict]:
        return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                  "parameters": t["input_schema"]}} for t in tools]

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        import httpx

        model = pick_model(request.model, self.model)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body: dict = {"model": model, "messages": self.to_messages(request),
                      "max_tokens": request.max_tokens}
        if request.tools:
            body["tools"] = self.to_tools(request.tools)
            body["tool_choice"] = "auto"
        try:
            resp = self.http.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        except httpx.HTTPError as e:
            raise ProviderError(f"Could not reach {self.base_url}: {type(e).__name__}",
                                retryable=True) from e
        if resp.status_code >= 400:
            raise ProviderError(f"Provider returned status {resp.status_code}",
                                retryable=resp.status_code in (408, 429) or resp.status_code >= 500,
                                status=resp.status_code)
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content: list[dict] = []
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})
        for i, call in enumerate(msg.get("tool_calls") or []):
            fn = call.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except ValueError:
                    args = {}
            content.append({"type": "tool_use", "id": call.get("id") or f"oai_{next(_ids)}_{i}",
                            "name": fn.get("name", ""), "input": args})
        u = data.get("usage") or {}
        stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else (
            "max_tokens" if choice.get("finish_reason") == "length" else "end_turn")
        return ProviderResponse(content, stop, {"input_tokens": int(u.get("prompt_tokens") or 0),
                                                "output_tokens": int(u.get("completion_tokens") or 0)},
                                data.get("model") or model)
