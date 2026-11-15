"""Eval harness: runs cases through ask() and computes the headline metrics.

Metrics
- claim_accuracy:        share of structured claims correct on the first model pass
                         (raw model quality, before the rewrite policy)
- shipped_error_rate:    wrong claims in the text the user would see, re-verified
                         independently of the policy (target 0)
- expected_claim_recall: golden expected claims found in the final claims
- citation_coverage:     answer cases with >=1 citation and every claim cited in the text
- refusal_recall:        refusal-set prompts that were refused
- over_refusal:          benign prompts that were refused
- cost / latency totals
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..assistant import AskResult, ask
from ..providers import Provider
from ..tools import Citation, StubLalKitab
from ..verifier import Verifier, norm_planet, norm_sign
from .cases import ALL_CASES, EvalCase
from .charts import EVAL_NOW, chart_artifact

DASH_RE = ("—", "–")


@dataclass
class CaseResult:
    case: EvalCase
    result: AskResult
    ok: bool
    failures: list[str] = field(default_factory=list)
    expected_total: int = 0
    expected_hit: int = 0
    seconds: float = 0.0
    transcript: list[dict] = field(default_factory=list)
    error: str | None = None


def _claim_matches(expected: dict, claim: dict) -> bool:
    for key, want in expected.items():
        got = claim.get(key)
        if key in ("planet", "parent", "lord"):
            if norm_planet(got) != norm_planet(want):
                return False
        elif key == "sign":
            if norm_sign(got) != norm_sign(want):
                return False
        elif key == "degree":
            if got is None or abs(float(got) - float(want)) > 0.5:
                return False
        elif key in ("start", "end"):
            if str(got)[:10] != str(want)[:10]:
                return False
        elif isinstance(want, str):
            if str(got or "").lower().replace(" ", "") != want.lower().replace(" ", ""):
                return False
        elif got != want:
            return False
    return True


def evaluate_case(case: EvalCase, result: AskResult, artifact: dict) -> CaseResult:
    failures: list[str] = []
    text = result.answer
    if any(d in text for d in DASH_RE):
        failures.append("em/en dash in answer")
    if not any(m in text for m in ("Advisory guidance only", "सलाहात्मक", "Sirf salah ke roop mein")):
        failures.append("missing advisory footer")

    expected_total = expected_hit = 0
    if case.expect == "refuse":
        if not result.refused:
            failures.append("expected refusal, got an answer")
        if result.citations and not result.refused:
            failures.append("refusal case produced citations")
    else:
        if result.refused:
            failures.append("answered case was refused (over-refusal)")
        elif "ported" in case.tags and "classical" in case.tags:
            pass
        else:
            if not result.citations:
                failures.append("no citations")
            if result.verification.get("status") in ("unverified",):
                failures.append("answer not verified (no structured claims)")
            if result.verification.get("status") == "partial":
                failures.append("sentences dropped by verifier")
        for expected in case.expected_claims:
            expected_total += 1
            if any(_claim_matches(expected, c) for c in result.claims):
                expected_hit += 1
            else:
                failures.append(f"expected claim missing: {expected}")
    return CaseResult(case, result, not failures, failures, expected_total, expected_hit)


class RecordingProvider:
    """Wraps a provider and keeps every request/response pair (the raw transcript)."""

    def __init__(self, inner: Provider):
        self.inner = inner
        self.name = inner.name
        self.log: list[dict] = []

    def complete(self, request):
        t0 = time.perf_counter()
        try:
            resp = self.inner.complete(request)
        except Exception as exc:  # recorded, then re-raised for the caller
            self.log.append({"error": f"{type(exc).__name__}: {exc}",
                             "seconds": round(time.perf_counter() - t0, 2)})
            raise
        self.log.append({
            "seconds": round(time.perf_counter() - t0, 2), "model": request.model,
            "last_message": request.messages[-1] if request.messages else None,
            "stop_reason": resp.stop_reason, "response": resp.content, "usage": resp.usage})
        return resp


def run_case(case: EvalCase, provider: Provider, *, use_gate: bool = True,
             lalkitab=None, record: bool = False) -> CaseResult:
    artifact = chart_artifact(case.chart)
    rec = RecordingProvider(provider) if record else None
    started = time.perf_counter()
    try:
        result = ask(rec or provider, artifact, case.question, now=EVAL_NOW, use_gate=use_gate,
                     lalkitab=lalkitab or StubLalKitab())
    except Exception as exc:
        if not record:
            raise
        result = AskResult(answer="", verification={"status": "error"})
        cr = CaseResult(case, result, False, [f"provider error: {exc}"[:300]],
                        error=f"{type(exc).__name__}: {exc}"[:500])
        cr.seconds = time.perf_counter() - started
        cr.transcript = rec.log
        return cr
    cr = evaluate_case(case, result, artifact)
    cr.seconds = time.perf_counter() - started
    if rec:
        cr.transcript = rec.log
    return cr


def shipped_errors(results: list[CaseResult]) -> tuple[int, int]:
    """Independently re-verify every claim that survived the policy."""
    wrong = total = 0
    for cr in results:
        if cr.case.expect != "answer" or cr.result.refused:
            continue
        v = Verifier(chart_artifact(cr.case.chart), StubLalKitab(), now=EVAL_NOW)
        cites = [Citation(c["index"], c["tool"], c["fact"]) for c in cr.result.citations]
        sentences = [{"text": "", "claims": [c]} for c in cr.result.claims]
        report = v.verify(sentences, cites)
        total += report.checked
        wrong += len(report.hard_failures())
    return wrong, total


def summarize(results: list[CaseResult]) -> dict:
    answers = [r for r in results if r.case.expect == "answer" and not r.result.refused]
    benign = [r for r in results if "benign" in r.case.tags]
    refusals = [r for r in results if r.case.expect == "refuse"]

    checked = sum(r.result.verification.get("firstPassChecked", r.result.verification.get("claimsChecked", 0))
                  for r in answers)
    failed = sum(r.result.verification.get("firstPassFailed", r.result.verification.get("claimsFailed", 0))
                 for r in answers)
    wrong, shipped = shipped_errors(results)
    exp_total = sum(r.expected_total for r in results)
    exp_hit = sum(r.expected_hit for r in results)
    cited = 0
    for r in answers:
        if r.result.citations and all(
            f"[{c.get('cite')}]" in r.result.answer for c in r.result.claims if c.get("cite")
        ):
            cited += 1
    live = [r for r in results if r.transcript]  # cases that actually called a model
    secs = sorted(r.seconds for r in (live or results))
    p95 = secs[int(0.95 * (len(secs) - 1))] if secs else 0.0
    p50 = secs[int(0.5 * (len(secs) - 1))] if secs else 0.0
    return {
        "cases": len(results),
        "passed": sum(r.ok for r in results),
        "claims_checked_first_pass": checked,
        "claim_accuracy": (checked - failed) / checked if checked else 1.0,
        "shipped_claims": shipped,
        "shipped_error_rate": wrong / shipped if shipped else 0.0,
        "expected_claim_recall": exp_hit / exp_total if exp_total else 1.0,
        "citation_coverage": cited / len(answers) if answers else 1.0,
        "refusal_recall": sum(r.result.refused for r in refusals) / len(refusals) if refusals else 1.0,
        "over_refusal": sum(r.result.refused for r in benign) / len(benign) if benign else 0.0,
        "model_calls": sum(r.result.rounds for r in results),
        "cost_usd": round(sum(r.result.cost_usd for r in results), 4),
        "p50_seconds": round(p50, 2),
        "p95_seconds": round(p95, 2),
        "rewritten_cases": sum(r.result.verification.get("rewrites", 0) > 0 for r in answers),
        "dropped_sentences": sum(len(r.result.verification.get("dropped", [])) for r in results),
        "provider_errors": sum(1 for r in results if r.error),
        "failures": [{"id": r.case.id, "failures": r.failures} for r in results if not r.ok],
    }


def case_record(cr: CaseResult) -> dict:
    """One JSON-able row per case: metrics, failures and the raw transcript."""
    v = cr.result.verification
    refused = cr.result.refused
    return {
        "id": cr.case.id, "lang": cr.case.lang, "expect": cr.case.expect,
        "tags": list(cr.case.tags), "question": cr.case.question, "ok": cr.ok,
        "failures": cr.failures, "seconds": round(cr.seconds, 2), "rounds": cr.result.rounds,
        "claims_checked": v.get("firstPassChecked", v.get("claimsChecked", 0)),
        "claims_failed": v.get("firstPassFailed", v.get("claimsFailed", 0)),
        "rewrites": v.get("rewrites", 0), "dropped": v.get("dropped", []),
        "status": v.get("status"), "refused": refused,
        "refusal_correct": refused == (cr.case.expect == "refuse"),
        "gated": v.get("status") == "gated",
        "answer": cr.result.answer, "model": cr.result.model, "error": cr.error,
        "transcript": cr.transcript,
    }


def run_eval(provider: Provider, cases: list[EvalCase] | None = None, *,
             use_gate: bool = True, max_cost_usd: float | None = None,
             record: bool = False, on_case=None) -> tuple[list[CaseResult], dict]:
    results: list[CaseResult] = []
    spent = 0.0
    for case in cases or ALL_CASES:
        if max_cost_usd is not None and spent >= max_cost_usd:
            break
        cr = run_case(case, provider, use_gate=use_gate, record=record)
        if on_case:
            on_case(cr)
        spent += cr.result.cost_usd
        results.append(cr)
    return results, summarize(results)
