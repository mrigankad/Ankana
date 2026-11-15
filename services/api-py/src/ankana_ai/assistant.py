"""The assistant: gate -> route -> tool loop -> structured answer -> verify.

Policy on factual mismatch (see verifier.py): one rewrite attempt with the
corrections fed back, then any sentence that still disagrees with the chart is
replaced by the verified chart fact and flagged "could not verify". Interpretive
sentences with no chart claim pass through untouched.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from . import safety
from .config import MAX_TOOL_ROUNDS, cost_usd
from .prompt import SYSTEM_PROMPT, chart_digest, language_directive
from .providers import Provider, ProviderRequest
from .routing import route
from .telemetry import record_usage
from .tools import (
    SUBMIT_TOOL,
    CitationRegistrar,
    LalKitabProvider,
    StubLalKitab,
    ToolContext,
    execute_tool,
    tool_definitions,
    tool_status_label,
)
from .verifier import Verifier, format_feedback, scan_unstructured

MAX_HISTORY_MESSAGES = 10

UNVERIFIED_TEXT = {
    "en": "Could not verify this statement. Chart data: {fact}.",
    "hi": "यह कथन सत्यापित नहीं हो सका। कुंडली का तथ्य: {fact}।",
    "hinglish": "Yeh statement verify nahi ho saka. Kundli ka tathya: {fact}.",
}
GIVE_UP_TEXT = {
    "en": "I could not ground an answer in the chart data within the allowed steps. Please rephrase the question.",
    "hi": "मैं अनुमत चरणों में कुंडली के आँकड़ों पर आधारित उत्तर नहीं दे सका। कृपया प्रश्न दूसरे शब्दों में पूछें।",
    "hinglish": "Main allowed steps mein kundli ke data par based answer nahi de saka. Kripya sawal doosre shabdon mein poochhiye.",
}


@dataclass
class AskResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    refused: bool = False
    refusal_category: str | None = None
    language: str = "en"
    model: str | None = None
    tier: str | None = None
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    rounds: int = 0
    claims: list[dict] = field(default_factory=list)  # final claims after policy

    def as_dict(self) -> dict:
        return {
            "answer": self.answer, "citations": self.citations, "toolsUsed": self.tools_used,
            "verification": self.verification, "refused": self.refused,
            "refusalCategory": self.refusal_category, "language": self.language,
            "model": self.model, "tier": self.tier, "usage": self.usage,
            "costUsd": round(self.cost_usd, 6), "rounds": self.rounds,
        }


def _normalize(text: str) -> str:
    text = re.sub(r"【(\d+)[^】]*】", r"[\1]", text)
    text = re.sub(r"\[(\d+)\s*,\s*(\d+)\]", r"[\1][\2]", text)
    return text.replace("—", "-").replace("–", "-").replace("−", "-")


def window_history(history: list[dict] | None) -> list[dict]:
    """Last N plain-text turns, each capped; continuity only."""
    cleaned = []
    for turn in history or []:
        role, content = turn.get("role"), (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content[:4000]})
    cleaned = cleaned[-MAX_HISTORY_MESSAGES:]
    # The API requires the first message to be from the user.
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    # Collapse consecutive same-role turns.
    merged: list[dict] = []
    for m in cleaned:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append(dict(m))
    return merged


def _pick_language(detected: str, claimed: object) -> str:
    """Trust deterministic detection for Hindi/Hinglish; the model decides only for English."""
    if detected != "en":
        return detected
    return claimed if claimed in ("en", "hi", "hinglish") else "en"


def _coerce_sentences(payload: dict) -> list[dict] | None:
    sentences = payload.get("sentences")
    if not isinstance(sentences, list) or not sentences:
        return None
    out = []
    for s in sentences:
        if not isinstance(s, dict) or not isinstance(s.get("text"), str):
            return None
        claims = s.get("claims") or []
        if not isinstance(claims, list) or not all(isinstance(c, dict) for c in claims):
            return None
        out.append({"text": s["text"].strip(), "claims": claims})
    return out


class _Run:
    """Mutable state for one question."""

    def __init__(self) -> None:
        self.rounds = 0
        self.usage: dict[str, int] = {}
        self.cost = 0.0
        self.tools_used: list[str] = []
        self.nudged = False
        self.last_text = ""
        self.model_refused = False
        self.pending_submit_id = ""
        self.pending_others: list[dict] = []


def ask(
    provider: Provider,
    artifact: dict,
    question: str,
    *,
    now: datetime | None = None,
    history: list[dict] | None = None,
    lalkitab: LalKitabProvider | None = None,
    deep: bool = False,
    use_gate: bool = True,
    allow_rewrite: bool = True,
    max_rounds: int = MAX_TOOL_ROUNDS,
    on_status: Callable[[str], None] | None = None,
) -> AskResult:
    now = now or datetime.now(tz=UTC)
    language = safety.detect_language(question)

    if use_gate:
        gate = safety.check(question)
        if gate.refused:
            return AskResult(
                answer=gate.message or "", refused=True, refusal_category=gate.category,
                language=gate.language,
                verification={"status": "gated", "claimsChecked": 0, "claimsFailed": 0},
            )

    choice = route(question, deep=deep)
    lk = lalkitab or StubLalKitab()
    ctx = ToolContext(artifact=artifact, now=now, lalkitab=lk)
    registrar = CitationRegistrar()
    verifier = Verifier(artifact, lk, now=now)
    tools = tool_definitions(lk_enabled=True)
    run = _Run()

    messages: list[dict] = window_history(history)
    note = language_directive(language)
    stamp = f"Reference date: {now.date().isoformat()}\n" + (f"{note}\n" if note else "")
    stamp += f"Question: {question}"
    if messages and messages[-1]["role"] == "user":
        messages.pop()  # keep strict user/assistant alternation
    messages.append({"role": "user", "content": stamp})

    system, digest = SYSTEM_PROMPT, chart_digest(artifact)

    def drive() -> dict | None:
        """Run the tool loop until submit_answer. Returns its input, or None."""
        while run.rounds < max_rounds:
            resp = provider.complete(ProviderRequest(
                model=choice.model, system=system, chart_context=digest,
                messages=messages, tools=tools, effort=choice.effort))
            run.rounds += 1
            for k, v in resp.usage.items():
                run.usage[k] = run.usage.get(k, 0) + (v or 0)
            call_cost = cost_usd(choice.model, resp.usage)
            run.cost += call_cost
            record_usage(provider, resp.model or choice.model, resp.usage, call_cost)
            if resp.stop_reason == "refusal":
                run.model_refused = True
                return None
            calls = resp.tool_calls
            if not calls:
                run.last_text = resp.text
                if run.nudged or not resp.content:
                    return None
                run.nudged = True
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content":
                                 "Call submit_answer now with sentences and structured claims."})
                continue
            messages.append({"role": "assistant", "content": resp.content})
            submit = next((c for c in calls if c["name"] == SUBMIT_TOOL), None)
            if submit is not None:
                run.pending_submit_id = submit["id"]
                run.pending_others = [c for c in calls if c is not submit]
                return submit["input"]
            messages.append({"role": "user", "content": _run_tools(calls)})
        return None

    def _run_tools(calls: list[dict]) -> list[dict]:
        blocks = []
        for call in calls:
            name = call["name"]
            if on_status:
                on_status(tool_status_label(name))
            args = call.get("input") if isinstance(call.get("input"), dict) else {}
            result = execute_tool(name, ctx, args)
            cit = registrar.register(name, args, result.summary, result.anchor)
            run.tools_used.append(name)
            blocks.append({
                "type": "tool_result", "tool_use_id": call["id"],
                "content": json.dumps({"citationIndex": cit.index, "summary": result.summary,
                                       "data": result.data}, ensure_ascii=False, default=str),
            })
        return blocks

    def give_up(status: str = "unverified") -> AskResult:
        text = GIVE_UP_TEXT.get(language, GIVE_UP_TEXT["en"])
        return _finish(text, status, [], 0, 0, language)

    def _finish(text: str, status: str, claims: list[dict], checked: int, failed: int,
                lang: str, extra: dict | None = None, refused: bool = False) -> AskResult:
        footer = safety.footer_for(lang)
        body = _normalize(text).strip()
        if footer not in body:
            body = f"{body} {footer}"
        verification = {"status": status, "claimsChecked": checked, "claimsFailed": failed,
                        **(extra or {})}
        return AskResult(
            answer=body, citations=[c.as_dict() for c in registrar.citations],
            tools_used=list(dict.fromkeys(run.tools_used)), verification=verification,
            refused=refused, language=lang, model=choice.model, tier=choice.tier,
            usage=dict(run.usage), cost_usd=run.cost, rounds=run.rounds, claims=claims,
        )

    # ---- first attempt
    payload = drive()
    if payload is None:
        if run.model_refused:
            return _finish("I am not able to help with that request.", "refused", [], 0, 0,
                           language, refused=True)
        return _unstructured(run.last_text, verifier, language, _finish, give_up)

    lang = _pick_language(language, payload.get("language"))
    if payload.get("refusal") is True:
        text = " ".join(s.get("text", "") for s in payload.get("sentences", []) if isinstance(s, dict))
        return _finish(text or "I am not able to help with that request.", "refused", [], 0, 0,
                       lang, refused=True)

    sentences = _coerce_sentences(payload)
    report = verifier.verify(sentences, registrar.citations) if sentences else None
    first_checked = report.checked if report else 0
    first_failed = report.failed if report else 0
    rewrites = 0

    needs_rewrite = sentences is None or bool(report.hard_failures())
    if needs_rewrite and allow_rewrite and run.rounds < max_rounds:
        rewrites = 1
        if sentences is None:
            feedback = ("VERIFIER_FEEDBACK: submit_answer was malformed. Provide a non-empty "
                        "sentences list, each with text and claims.")
        else:
            feedback = format_feedback(report.hard_failures(), sentences)
        results = [{"type": "tool_result", "tool_use_id": run.pending_submit_id,
                    "content": feedback, "is_error": True}]
        results += _run_tools(run.pending_others)
        messages.append({"role": "user", "content": results})
        payload2 = drive()
        sentences2 = _coerce_sentences(payload2) if payload2 else None
        if sentences2:
            lang = _pick_language(language, payload2.get("language"))
            sentences = sentences2
            report = verifier.verify(sentences, registrar.citations)

    if sentences is None or report is None:
        return give_up()

    # ---- policy: drop / flag sentences that still disagree with the chart
    final_failures = report.hard_failures()
    out_sentences: list[str] = []
    final_claims: list[dict] = []
    dropped: list[dict] = []
    surfaced: set[str] = set()
    for i, s in enumerate(sentences):
        if i in final_failures:
            facts = []
            for m in final_failures[i]:
                if m.correct_fact not in surfaced:
                    surfaced.add(m.correct_fact)
                    facts.append(m.correct_fact)
            dropped.append({"sentence": s["text"], "reasons": [m.reason for m in final_failures[i]]})
            if facts:
                tmpl = UNVERIFIED_TEXT.get(lang, UNVERIFIED_TEXT["en"])
                out_sentences.append(tmpl.format(fact="; ".join(facts)))
            continue
        text = s["text"]
        for c in s["claims"]:
            cite = c.get("cite")
            if isinstance(cite, int) and f"[{cite}]" not in text:
                text += f" [{cite}]"
            final_claims.append(c)
        out_sentences.append(text)

    if not dropped:
        status = "rewritten" if rewrites else "verified"
    else:
        status = "partial"
    soft = [m.as_dict() for ms in report.mismatches.values() for m in ms if m.soft]
    return _finish(
        " ".join(out_sentences), status, final_claims, report.checked,
        sum(len(v) for v in final_failures.values()), lang,
        extra={"rewrites": rewrites, "firstPassChecked": first_checked,
               "firstPassFailed": first_failed, "dropped": dropped, "warnings": soft},
    )


def _unstructured(text: str, verifier: Verifier, language: str, finish, give_up) -> AskResult:
    """Model never called submit_answer: only ship text that has no visible conflict."""
    if not text.strip():
        return give_up()
    conflicts = scan_unstructured(text, verifier)
    if conflicts:
        facts = "; ".join(dict.fromkeys(m.correct_fact for m in conflicts))
        tmpl = UNVERIFIED_TEXT.get(language, UNVERIFIED_TEXT["en"])
        return finish(tmpl.format(fact=facts), "partial", [], 0, len(conflicts), language,
                      extra={"dropped": [{"sentence": text, "reasons": [m.reason for m in conflicts]}]})
    return finish(text, "unverified", [], 0, 0, language,
                  extra={"note": "no structured claims; text not verified"})
