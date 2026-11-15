"""Provider kinds, key encryption, provider construction, routing presets and fallback.

Pure logic (no database): app.ai_connections stores connections per practice and calls in here.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import ipaddress
import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from .config import HAIKU, OPUS, SONNET
from .llm_providers import (
    ClaudeCodeProvider,
    CodexProvider,
    GeminiCliProvider,
    OpenAICompatibleProvider,
    ProviderError,
    cli_status,
)
from .netguard import guarded_client, is_public_ip, resolve_public
from .providers import (
    AnthropicProvider,
    MockProvider,
    OllamaProvider,
    Provider,
    ProviderRequest,
    ProviderResponse,
)

ROLES = ("classify", "narrate", "synthesise", "report")
PRESETS = ("best_quality", "balanced", "lowest_cost", "local_only")
TIERS = ("top", "strong", "fast")
LOCAL_KINDS = ("claude_code", "codex", "gemini_cli", "ollama_local")
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


@dataclass(frozen=True)
class KindInfo:
    kind: str
    label: str
    description: str
    logo: str  # file under apps/web-practitioner/public/providers/
    local: bool  # runs on or through this machine; needs ANKANA_ALLOW_LOCAL_PROVIDERS=1
    requires_key: bool
    requires_base_url: bool
    default_base_url: str | None
    default_models: dict[str, str] = field(default_factory=dict)


def _m(top: str, strong: str, fast: str) -> dict[str, str]:
    return {"top": top, "strong": strong, "fast": fast}


KINDS: dict[str, KindInfo] = {k.kind: k for k in (
    KindInfo("anthropic", "Anthropic API", "Claude through an API key.", "anthropic.svg",
             False, True, False, None, _m(OPUS, SONNET, HAIKU)),
    KindInfo("claude_code", "Claude Code (this computer)",
             "Your own Claude login through the local claude command. No API key.", "claude.svg",
             True, False, False, None, _m("opus", "sonnet", "haiku")),
    KindInfo("ollama_local", "Ollama (this computer)",
             "Open models running on this machine. Free, private, works offline.", "ollama.svg",
             True, False, True, "http://localhost:11434", _m("qwen3:32b", "qwen3:14b", "qwen3:4b")),
    KindInfo("ollama_cloud", "Ollama Cloud", "Open models hosted by Ollama, with an API key.",
             "ollama.svg", False, True, False, "https://ollama.com",
             _m("gpt-oss:120b", "gpt-oss:20b", "gpt-oss:20b")),
    KindInfo("gemini", "Google Gemini API", "Gemini through a Google AI API key.",
             "googlegemini.svg", False, True, False, GEMINI_OPENAI_URL,
             _m("gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite")),
    KindInfo("gemini_cli", "Gemini CLI (this computer)",
             "Your own Google login through the local gemini command.", "googlegemini.svg",
             True, False, False, None, _m("gemini-2.5-pro", "gemini-2.5-flash",
                                          "gemini-2.5-flash-lite")),
    KindInfo("codex", "Codex CLI (this computer)",
             "Your own ChatGPT or OpenAI login through the local codex command.", "openai.svg",
             True, False, False, None, _m("", "", "")),
    KindInfo("openai_compatible", "OpenAI-compatible",
             "OpenAI, OpenRouter, Groq, LiteLLM, LM Studio, vLLM or any /chat/completions server.",
             "openai.svg", False, False, True, "https://api.openai.com/v1",
             _m("gpt-4.1", "gpt-4.1", "gpt-4.1-mini")),
    KindInfo("mock", "Offline sample", "Built-in deterministic stand-in. No network.",
             "ankana.svg", False, False, False, None, _m("mock", "mock", "mock")),
)}
KIND_NAMES = tuple(KINDS)


# ------------------------------------------------------------------ policy
def local_providers_allowed() -> bool:
    return os.environ.get("ANKANA_ALLOW_LOCAL_PROVIDERS", "").strip().lower() in ("1", "true", "yes")


def kind_allowed(kind: str) -> bool:
    return kind not in LOCAL_KINDS or local_providers_allowed()


def validate_base_url(url: str | None, kind: str) -> str | None:
    """Normalised base URL, or ValueError. On hosted deployments (local providers not
    allowed) the URL must be https and must not point at a loopback or private host."""
    if not url:
        return None
    url = url.strip().rstrip("/")
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("base URL must start with http:// or https://")
    if local_providers_allowed():
        return url
    if parts.scheme != "https":
        raise ValueError("base URL must use https on a hosted deployment")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("base URL must not point at a local or internal host")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        if re.fullmatch(r"[0-9a-fx.]+", host):  # 2130706433, 0x7f.1: the OS resolver accepts these
            raise ValueError("base URL must use a hostname or a plain IP address") from None
        return url  # a name: resolved and checked on every request (netguard), not just here
    if not is_public_ip(host.strip("[]")):
        raise ValueError("base URL must not point at a private address")
    return url


def is_local_host(url: str | None) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    if host in ("localhost", "") or host.endswith((".local", ".localhost")):
        return host != ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


# ----------------------------------------------------------------- secrets
MIN_PRODUCTION_SECRET_LENGTH = 24


def _secret() -> str:
    """ANKANA_SECRET_KEY, or "" when unusable. Key Vault placeholders are a single space, which
    must count as unset, and a short secret is refused in production (it is hashed straight
    into the Fernet key, so its entropy is the key's entropy: use 32+ random characters)."""
    secret = os.environ.get("ANKANA_SECRET_KEY", "").strip()
    if os.environ.get("API_ENV") == "production" and len(secret) < MIN_PRODUCTION_SECRET_LENGTH:
        return ""
    return secret


def _fernet():
    from cryptography.fernet import Fernet

    secret = _secret()
    if not secret:
        raise ProviderError("ANKANA_SECRET_KEY is not set (or too short for production); "
                            "API keys cannot be stored.")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def secret_key_configured() -> bool:
    return bool(_secret())


def encrypt_key(plain: str) -> str:
    return "v1:" + _fernet().encrypt(plain.encode()).decode()


def decrypt_key(token: str | None) -> str | None:
    if not token:
        return None
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(token.removeprefix("v1:").encode()).decode()
    except InvalidToken as e:
        raise ProviderError("Stored API key cannot be decrypted (ANKANA_SECRET_KEY changed?).") from e


def redact(message: str, secret: str | None) -> str:
    return message.replace(secret, "***") if secret else message


# ----------------------------------------------------------------- building
def merged_models(kind: str, models: dict[str, str | None] | None) -> dict[str, str]:
    base = dict(KINDS[kind].default_models)
    for tier, value in (models or {}).items():
        if value and tier in TIERS:
            base[tier] = value
    return base


def build_provider(kind: str, *, base_url: str | None = None, api_key: str | None = None,
                   models: dict[str, str] | None = None, http: Any | None = None,
                   runner: Any | None = None) -> Provider:
    """Construct the provider for a connection. `http` and `runner` are test seams."""
    models = merged_models(kind, models)
    info = KINDS[kind]
    url = base_url or info.default_base_url
    if http is None and not local_providers_allowed() and kind in (
            "ollama_cloud", "gemini", "openai_compatible", "ollama_local"):
        # Hosted deployment: outbound calls go through the SSRF guard (DNS rebinding safe).
        http = guarded_client(timeout=120.0)
    if kind == "anthropic":
        import anthropic

        if base_url and not local_providers_allowed():
            # The Anthropic SDK brings its own HTTP stack, so the transport guard cannot wrap
            # it; refuse a custom endpoint that does not resolve to public addresses now.
            from urllib.parse import urlparse

            parts = urlparse(base_url)
            try:
                resolve_public(parts.hostname or "", parts.port or 443)
            except Exception as exc:
                raise ProviderError(f"Anthropic base URL is not allowed: {exc}") from exc
        return AnthropicProvider(anthropic.Anthropic(api_key=api_key, base_url=base_url or None))
    if kind in ("ollama_local", "ollama_cloud"):
        return OllamaProvider(base_url=url, api_key=api_key, model=models["strong"], http=http)
    if kind in ("gemini", "openai_compatible"):
        return OpenAICompatibleProvider(url or "", api_key, models["strong"], http=http)
    if kind == "claude_code":
        return ClaudeCodeProvider(model=models["strong"], runner=runner)
    if kind == "codex":
        return CodexProvider(model=models["strong"], runner=runner)
    if kind == "gemini_cli":
        return GeminiCliProvider(model=models["strong"], runner=runner)
    if kind == "mock":
        return MockProvider()
    raise ValueError(f"unknown provider kind: {kind}")


_CLAUDE_TIER = {HAIKU: "fast", SONNET: "strong", OPUS: "top"}


class TieredProvider:
    """Maps the assistant's Claude tier ids to the connection's own models. A forced model
    (from the routing table) wins over the tier."""

    def __init__(self, inner: Provider, models: dict[str, str], forced: str | None = None):
        self.inner, self.models, self.forced = inner, models, forced
        self.name = inner.name

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        tier = _CLAUDE_TIER.get(request.model, "strong")
        model = self.forced or self.models.get(tier) or self.models.get("strong") or ""
        return self.inner.complete(dataclasses.replace(request, model=model))


@dataclass
class ChainEntry:
    kind: str
    connection_id: str
    provider: Provider


class FallbackProvider:
    """Tries each entry in order; the next one is used when a call raises."""

    name = "fallback"

    def __init__(self, entries: list[ChainEntry]):
        if not entries:
            raise ValueError("fallback chain is empty")
        self.entries = entries
        self.usage_by_kind: dict[str, dict[str, int]] = {}
        self.errors: list[str] = []

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        failures: list[str] = []
        for entry in self.entries:
            try:
                resp = entry.provider.complete(request)
            except Exception as e:
                failures.append(f"{entry.kind}: "
                                f"{e if isinstance(e, ProviderError) else type(e).__name__}")
                self.errors.append(failures[-1])
                continue
            slot = self.usage_by_kind.setdefault(entry.kind, {"calls": 0, "tokens": 0})
            slot["calls"] += 1
            slot["tokens"] += sum(int(resp.usage.get(k) or 0)
                                  for k in ("input_tokens", "output_tokens"))
            return resp
        raise ProviderError("All AI connections failed. " + "; ".join(failures))


# ------------------------------------------------------------------ presets
_TIERS_BY_PRESET: dict[str, dict[str, str]] = {
    "best_quality": {"classify": "strong", "narrate": "top", "synthesise": "top", "report": "top"},
    "balanced": {"classify": "fast", "narrate": "strong", "synthesise": "strong", "report": "top"},
    "lowest_cost": {"classify": "fast", "narrate": "fast", "synthesise": "fast", "report": "strong"},
    "local_only": {"classify": "fast", "narrate": "strong", "synthesise": "strong", "report": "strong"},
}
_QUALITY_ORDER = ["anthropic", "claude_code", "codex", "gemini", "gemini_cli", "openai_compatible",
                  "ollama_cloud", "ollama_local", "mock"]
_COST_ORDER = ["ollama_local", "ollama_cloud", "gemini", "gemini_cli", "openai_compatible",
               "claude_code", "codex", "anthropic", "mock"]
_ORDER = {"best_quality": _QUALITY_ORDER, "balanced": _QUALITY_ORDER, "lowest_cost": _COST_ORDER,
          "local_only": _COST_ORDER}


@dataclass(frozen=True)
class ConnView:
    """What preset planning needs to know about a connection."""

    id: str
    kind: str
    enabled: bool
    base_url: str | None
    models: dict[str, str]


def plan_preset(preset: str, conns: list[ConnView]) -> list[dict]:
    """Routes [{role, connection_id, model}] for a preset, or [] when nothing fits."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset}")
    usable = [c for c in conns if c.enabled and kind_allowed(c.kind)]
    if preset == "local_only":
        usable = [c for c in usable if c.kind == "ollama_local" or (
            c.kind == "openai_compatible" and is_local_host(c.base_url))]
    order = _ORDER[preset]
    usable.sort(key=lambda c: order.index(c.kind))
    if not usable:
        return []
    chosen = usable[0]
    return [{"role": role, "connection_id": chosen.id,
             "model": chosen.models.get(_TIERS_BY_PRESET[preset][role]) or None}
            for role in ROLES]


def availability(kind: str, *, runner: Any | None = None) -> dict:
    """Is this kind usable right now on this server? Cloud kinds only need a key."""
    info = KINDS[kind]
    allowed = kind_allowed(kind)
    out = {"available": True, "status": "ready", "detail": "", "allowed": allowed}
    if not allowed:
        out.update(available=False, status="disabled",
                   detail="Local providers are turned off on this server "
                          "(set ANKANA_ALLOW_LOCAL_PROVIDERS=1 on a self-hosted install).")
        return out
    cli = {"claude_code": ("claude", "ANKANA_CLAUDE_BIN"), "codex": ("codex", "ANKANA_CODEX_BIN"),
           "gemini_cli": ("gemini", "ANKANA_GEMINI_BIN")}
    if kind in cli:
        ok, detail, _ = cli_status(cli[kind][0], cli[kind][1], runner)
        out.update(available=ok, status="ready" if ok else "not_installed", detail=detail)
    elif kind == "ollama_local":
        out.update(_probe_ollama(info.default_base_url or ""))
    elif info.requires_key:
        out.update(status="needs_key", detail="Add an API key to connect.")
    return out


def _probe_ollama(base_url: str) -> dict:
    import httpx

    try:
        r = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=1.5)
        r.raise_for_status()
        names = [m.get("name") for m in (r.json().get("models") or [])]
        detail = f"Ollama is running with {len(names)} model(s)."
        return {"available": True, "status": "ready" if names else "no_models", "detail": detail
                if names else "Ollama is running but no models are pulled yet (ollama pull <model>).",
                "models": names}
    except Exception:
        return {"available": False, "status": "not_running",
                "detail": "Ollama is not running on this computer (start it or install from ollama.com)."}
