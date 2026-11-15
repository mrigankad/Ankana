"""Model providers behind one interface.

Messages use the Anthropic content-block shape as the neutral format:
  {"role": "user"|"assistant", "content": str | [block, ...]}
  blocks: text | tool_use {id,name,input} | tool_result {tool_use_id,content}
AnthropicProvider passes them through; OllamaProvider converts to its chat
format; MockProvider is a deterministic stand-in that reads tool results.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from .config import HAIKU, MAX_OUTPUT_TOKENS, SONNET
from .tools import SUBMIT_TOOL

# Ollama defaults to a 4096-token window, which silently cuts the rules and chart digest
# (about 6k tokens with the tool schemas). Ask for enough room.
OLLAMA_NUM_CTX = int(os.environ.get("ANKANA_OLLAMA_NUM_CTX", "16384"))


@dataclass
class ProviderRequest:
    model: str
    system: str  # stable rules block
    chart_context: str  # stable chart digest (cache breakpoint after it)
    messages: list[dict]
    tools: list[dict]
    effort: str = "medium"
    max_tokens: int = MAX_OUTPUT_TOKENS


@dataclass
class ProviderResponse:
    content: list[dict]
    stop_reason: str  # end_turn | tool_use | max_tokens | refusal
    usage: dict = field(default_factory=dict)
    model: str = ""

    @property
    def tool_calls(self) -> list[dict]:
        return [b for b in self.content if b.get("type") == "tool_use"]

    @property
    def text(self) -> str:
        return "".join(b.get("text", "") for b in self.content if b.get("type") == "text")


class Provider(Protocol):
    name: str

    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


# ------------------------------------------------------------------ Anthropic


class AnthropicProvider:
    """Hosted Claude with prompt caching of tools + system rules + chart digest.

    Notes for the supported models (Sonnet 5.5 / Opus 5.5 / Haiku 5.5):
    - no temperature/top_p, no forced tool_choice (auto only, tools are strict),
    - thinking is left at the model default (adaptive); depth via output_config.effort,
    - refusal_fallback adds the server-side fallback beta for Sonnet/Opus.
    """

    name = "anthropic"

    def __init__(self, client: Any | None = None, *, refusal_fallback: bool = True):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / auth profile
        self.client = client
        self.refusal_fallback = refusal_fallback

    def _kwargs(self, req: ProviderRequest) -> dict:
        system = [
            {"type": "text", "text": req.system},
            # Breakpoint: caches tools + rules + chart digest as one prefix.
            {"type": "text", "text": req.chart_context, "cache_control": {"type": "ephemeral"}},
        ]
        kwargs: dict = {
            "model": req.model,
            "max_tokens": req.max_tokens,
            "system": system,
            "tools": req.tools,
            "tool_choice": {"type": "auto"},
            "messages": req.messages,
            "extra_body": {"output_config": {"effort": req.effort}},
        }
        return kwargs

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        kwargs = self._kwargs(request)
        use_fallback = self.refusal_fallback and request.model != HAIKU  # Haiku has none
        if use_fallback:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["extra_body"]["fallbacks"] = "default"
            resp = self.client.beta.messages.create(**kwargs)
        else:
            resp = self.client.messages.create(**kwargs)
        usage = {
            "input_tokens": getattr(resp.usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(resp.usage, "output_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        }
        # Thinking blocks must be echoed back unchanged within a conversation.
        content = [b.model_dump(exclude_none=True) for b in resp.content]
        return ProviderResponse(content, resp.stop_reason or "end_turn", usage, resp.model)


# --------------------------------------------------------------------- Ollama


class OllamaProvider:
    """Port of HttpOllamaClient: local daemon or Ollama cloud, no caching."""

    name = "ollama"

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, http: Any | None = None):
        import httpx

        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL")
                         or "http://127.0.0.1:11434").rstrip("/")
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:32b")
        self.http = http or httpx.Client(timeout=float(os.environ.get("ANKANA_OLLAMA_TIMEOUT", "600")))

    @staticmethod
    def to_ollama_messages(req: ProviderRequest) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": f"{req.system}\n\n{req.chart_context}"}]
        names: dict[str, str] = {}
        for m in req.messages:
            content = m["content"]
            if isinstance(content, str):
                out.append({"role": m["role"], "content": content})
                continue
            if m["role"] == "assistant":
                text = "".join(b.get("text", "") for b in content if b["type"] == "text")
                calls = []
                for b in content:
                    if b["type"] == "tool_use":
                        names[b["id"]] = b["name"]
                        calls.append({"function": {"name": b["name"], "arguments": b["input"]}})
                msg: dict = {"role": "assistant", "content": text}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
            else:
                for b in content:
                    if b["type"] == "tool_result":
                        out.append({"role": "tool", "tool_name": names.get(b["tool_use_id"], ""),
                                    "content": b["content"] if isinstance(b["content"], str)
                                    else json.dumps(b["content"])})
                    elif b["type"] == "text":
                        out.append({"role": "user", "content": b["text"]})
        return out

    @staticmethod
    def to_ollama_tools(tools: list[dict]) -> list[dict]:
        return [{"type": "function", "function": {
            "name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
            for t in tools]

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        model = (request.model if request.model and not request.model.startswith("claude-")
                 else self.model)
        resp = self.http.post(
            f"{self.base_url}/api/chat", headers=headers,
            json={"model": model, "messages": self.to_ollama_messages(request), "think": False,
                  "options": {"num_ctx": OLLAMA_NUM_CTX, "num_predict": request.max_tokens},
                  "tools": self.to_ollama_tools(request.tools), "stream": False},
        )
        if resp.status_code >= 400:
            from .llm_providers import ProviderError

            detail = ""
            try:
                detail = str((resp.json() or {}).get("error", ""))[:160]
            except ValueError:
                pass
            raise ProviderError(f"Ollama request failed with status {resp.status_code}"
                                + (f": {detail}" if detail else ""),
                                retryable=resp.status_code in (408, 429) or resp.status_code >= 500,
                                status=resp.status_code)
        data = resp.json()
        payload = data["message"]
        content: list[dict] = []
        if payload.get("content"):
            content.append({"type": "text", "text": payload["content"]})
        for i, call in enumerate(payload.get("tool_calls") or []):
            args = call["function"].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            content.append({"type": "tool_use", "id": f"ollama_{abs(hash(json.dumps(payload)))}_{i}",
                            "name": call["function"]["name"], "input": args})
        has_tool = any(b["type"] == "tool_use" for b in content)
        return ProviderResponse(content, "tool_use" if has_tool else "end_turn",
                                {"input_tokens": int(data.get("prompt_eval_count") or 0),
                                 "output_tokens": int(data.get("eval_count") or 0)}, model)


# ----------------------------------------------------------------------- Mock

_PLANETS = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]
_NEXT_SIGN = {s: n for s, n in zip(
    ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
     "Sagittarius", "Capricorn", "Aquarius", "Pisces"],
    ["Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius",
     "Capricorn", "Aquarius", "Pisces", "Aries"])}
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

_TOOL_KEYWORDS: list[tuple[str, re.Pattern]] = [
    ("get_dashas", re.compile(r"dasha|दशा|period|timing|when", re.I)),
    ("get_yogas", re.compile(r"yoga|dosha|योग", re.I)),
    ("lk_chart", re.compile(r"lal kitab|lalkitab|लाल किताब", re.I)),
    ("get_transits", re.compile(r"transit|sade sati|साढ़े", re.I)),
]


def _focus_planets(question: str) -> list[str]:
    """Planets named in the question (English, Hinglish roman, Devanagari)."""
    from .verifier import _PLANET_WORDS

    found: list[str] = []
    for word, planet in _PLANET_WORDS.items():
        if word.isascii():
            hit = bool(re.search(rf"\b{re.escape(word)}\b", question))
        else:
            hit = word in question
        if hit and planet not in found:
            found.append(planet)
    return found


class MockProvider:
    """Deterministic stand-in for a model; no network, no randomness.

    behavior:
      "faithful"      correct facts straight from the tool results
      "wrong_once"    first submit_answer carries a wrong sign, the rewrite is right
      "wrong_always"  keeps stating the wrong sign even after feedback
      "no_submit"     replies in plain text and never calls submit_answer
      "hidden_claim"  wrong planet-in-sign hidden in prose with an empty claims list
    """

    name = "mock"

    def __init__(self, behavior: str = "faithful"):
        self.behavior = behavior
        self.calls = 0

    # -- helpers
    @staticmethod
    def _question(messages: list[dict]) -> str:
        first = messages[0]["content"]
        return first if isinstance(first, str) else " ".join(
            b.get("text", "") for b in first if b["type"] == "text")

    @staticmethod
    def _called(messages: list[dict]) -> set[str]:
        return {b["name"] for m in messages if m["role"] == "assistant"
                and isinstance(m["content"], list) for b in m["content"]
                if b.get("type") == "tool_use"}

    @staticmethod
    def _results(messages: list[dict]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        names: dict[str, str] = {}
        for m in messages:
            if not isinstance(m["content"], list):
                continue
            for b in m["content"]:
                if b.get("type") == "tool_use":
                    names[b["id"]] = b["name"]
                elif b.get("type") == "tool_result":
                    try:
                        out[names.get(b["tool_use_id"], "")] = json.loads(b["content"])
                    except (json.JSONDecodeError, TypeError):
                        pass
        return out

    @staticmethod
    def _feedback_seen(messages: list[dict]) -> bool:
        for m in messages:
            if isinstance(m["content"], list):
                for b in m["content"]:
                    if b.get("type") == "tool_result" and "VERIFIER_FEEDBACK" in str(b["content"]):
                        return True
        return False

    def _plan_tools(self, question: str) -> list[str]:
        wanted = ["get_birth_chart"]
        for tool, pat in _TOOL_KEYWORDS:
            if pat.search(question):
                wanted.append(tool)
        return wanted

    # -- main
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        messages = request.messages
        question = self._question(messages)
        usage = {"input_tokens": 1200, "output_tokens": 300,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        wanted = [t for t in self._plan_tools(question)
                  if t in {d["name"] for d in request.tools}]
        pending = [t for t in wanted if t not in self._called(messages)]
        if pending:
            content = [{"type": "tool_use", "id": f"mock_{self.calls}_{i}", "name": t, "input": {}}
                       for i, t in enumerate(pending)]
            return ProviderResponse(content, "tool_use", usage, request.model)

        if self.behavior == "no_submit":
            return ProviderResponse(
                [{"type": "text", "text": "Your chart has been consulted [1]."}],
                "end_turn", usage, request.model)

        results = self._results(messages)
        wrong = self.behavior == "wrong_always" or (
            self.behavior == "wrong_once" and not self._feedback_seen(messages))
        hi = bool(_DEVANAGARI.search(question))
        sentences = self._compose(question, results, wrong, hi)
        if self.behavior == "hidden_claim" and not self._feedback_seen(messages):
            moon = next((p for p in results["get_birth_chart"]["data"]["planets"]
                         if p["planet"] == "moon"), None)
            if moon:
                bad = _NEXT_SIGN[moon["signName"]]
                sentences.append({"text": f"Moon is placed in {bad} here.", "claims": []})
        call = {"type": "tool_use", "id": f"mock_{self.calls}_submit", "name": SUBMIT_TOOL,
                "input": {"language": "hi" if hi else "en", "sentences": sentences}}
        return ProviderResponse([call], "tool_use", usage, request.model)

    def _compose(self, question: str, results: dict, wrong: bool, hi: bool) -> list[dict]:
        sentences: list[dict] = []
        chart = results.get("get_birth_chart")
        q = question.lower()
        if chart:
            cite = chart["citationIndex"]
            data = chart["data"]
            asc = data["ascendant"]
            sentences.append({
                "text": (f"आपका लग्न {asc['signName']} है [{cite}]." if hi
                         else f"Your lagna is {asc['signName']} at {asc['degreesInSign']:.1f} degrees [{cite}]."),
                "claims": [{"type": "lagna", "planet": "lagna", "sign": asc["signName"],
                            "degree": asc["degreesInSign"], "nakshatra": asc["nakshatra"],
                            "cite": cite}],
            })
            focus = _focus_planets(q) or ["moon"]
            for pl in focus[:3]:
                body = next(p for p in data["planets"] if p["planet"] == pl)
                sign = _NEXT_SIGN[body["signName"]] if wrong and pl == focus[0] else body["signName"]
                sentences.append({
                    "text": (f"{pl} {sign} राशि में, भाव {body['house']} में है [{cite}]." if hi
                             else f"{pl.capitalize()} is in {sign}, house {body['house']}, "
                                  f"{body['nakshatra']} pada {body['pada']} [{cite}]."),
                    "claims": [{"type": "planet_sign", "planet": pl, "sign": sign, "cite": cite},
                               {"type": "planet_house", "planet": pl, "house": body["house"], "cite": cite},
                               {"type": "planet_nakshatra", "planet": pl,
                                "nakshatra": body["nakshatra"], "pada": body["pada"], "cite": cite}],
                })
        lord_q = re.search(r"(\d{1,2})(?:st|nd|rd|th)? house lord|lord of (?:the )?(\d{1,2})", q)
        if chart and lord_q:
            n = int(lord_q.group(1) or lord_q.group(2))
            h = next((x for x in chart["data"]["houses"] if x["number"] == n), None)
            if h:
                cite = chart["citationIndex"]
                sentences.append({
                    "text": f"House {n} is {h['signName']} and its lord is {h['lord']} [{cite}].",
                    "claims": [{"type": "house_lord", "house": n, "lord": h["lord"],
                                "sign": h["signName"], "cite": cite}],
                })
        dashas = results.get("get_dashas")
        if dashas:
            cite = dashas["citationIndex"]
            md = dashas["data"]["current"]["mahadasha"]
            ad = dashas["data"]["current"]["antardasha"]
            claims = []
            text = f"The running mahadasha is {md['planet']} from {md['start']} to {md['end']} [{cite}]."
            claims.append({"type": "dasha_period", "level": "mahadasha", "planet": md["planet"],
                           "start": md["start"], "end": md["end"], "cite": cite})
            if ad:
                text += f" The antardasha is {ad['planet']} ({ad['start']} to {ad['end']}) [{cite}]."
                claims.append({"type": "dasha_period", "level": "antardasha", "planet": ad["planet"],
                               "parent": md["planet"], "start": ad["start"], "end": ad["end"],
                               "cite": cite})
            sentences.append({"text": text, "claims": claims})
        yogas = results.get("get_yogas")
        if yogas:
            cite = yogas["citationIndex"]
            names = [y["name"] for y in yogas["data"]][:3]
            sentences.append({
                "text": "Present yogas include " + ", ".join(names) + f" [{cite}].",
                "claims": [{"type": "yoga", "yoga": n, "present": True, "cite": cite} for n in names],
            })
        lk = results.get("lk_chart")
        if lk:
            cite = lk["citationIndex"]
            ph = lk["data"]["planetHouse"]
            sentences.append({
                "text": f"In the Lal Kitab chart the Moon sits in house {ph['moon']} [{cite}].",
                "claims": [{"type": "lk_planet_house", "planet": "moon", "house": ph["moon"],
                            "cite": cite}],
            })
        return sentences


def provider_from_env() -> Provider | None:
    """Pick a provider from the environment; None when nothing is configured."""
    choice = (os.environ.get("ANKANA_AI_PROVIDER") or "").lower()
    if choice == "mock":
        return MockProvider()
    if choice == "ollama" or (not choice and os.environ.get("OLLAMA_BASE_URL")
                              and not os.environ.get("ANTHROPIC_API_KEY")):
        return OllamaProvider()
    if choice == "anthropic" or os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    return None


__all__ = [
    "AnthropicProvider", "MockProvider", "OllamaProvider", "Provider", "ProviderRequest",
    "ProviderResponse", "SONNET", "provider_from_env",
]
