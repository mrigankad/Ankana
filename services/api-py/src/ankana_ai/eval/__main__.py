"""CLI: python -m ankana_ai.eval [--provider KIND --model M --limit N] [--live] [--json out.json]

Default is the deterministic MockProvider (what CI runs). --provider runs any provider kind
(claude_code, ollama_local, codex, gemini_cli, ...) one case at a time with raw transcripts
(--transcripts). --live uses the hosted API and is skipped (exit 0) unless ANTHROPIC_API_KEY
is already set.
"""

import argparse
import json
import os
import random
import sys

from ..providers import AnthropicProvider, MockProvider
from .cases import ALL_CASES
from .harness import case_record, run_eval


def sample_cases(cases, n: int, seed: int = 7):
    """Deterministic sample of n cases, round-robin across groups so every kind is covered."""

    def group(c):
        if c.expect == "refuse":
            return "refuse-" + c.lang
        if "benign" in c.tags:
            return "benign"
        if "ported" in c.tags:
            return "ported"
        return "golden-" + c.lang

    buckets: dict[str, list] = {}
    for c in cases:
        buckets.setdefault(group(c), []).append(c)
    rng = random.Random(seed)
    for b in buckets.values():
        rng.shuffle(b)
    picked: list = []
    while len(picked) < n and any(buckets.values()):
        for b in buckets.values():
            if b and len(picked) < n:
                picked.append(b.pop())
    order = {c.id: i for i, c in enumerate(cases)}
    return sorted(picked, key=lambda c: order[c.id])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="call the hosted Claude API")
    ap.add_argument("--json", help="write the summary to this path")
    ap.add_argument("--max-cost", type=float, default=0.5, help="USD budget cap for --live")
    ap.add_argument("--no-gate", action="store_true",
                    help="disable the deterministic refusal gate (measure the model alone)")
    ap.add_argument("--provider", help="provider kind: claude_code, ollama_local, codex, "
                    "gemini_cli, mock (local kinds need no API key)")
    ap.add_argument("--model", help="model for every call, e.g. haiku, sonnet, qwen3:8b")
    ap.add_argument("--base-url", help="base URL for ollama_local / openai_compatible")
    ap.add_argument("--limit", type=int, help="run only N cases (stratified sample)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--cases", help="comma-separated case ids to run")
    ap.add_argument("--transcripts", help="write per-case records with raw transcripts here")
    args = ap.parse_args(argv)

    cases = list(ALL_CASES)
    if args.cases:
        ids = set(args.cases.split(","))
        cases = [c for c in cases if c.id in ids]
    if args.limit:
        cases = sample_cases(cases, args.limit, args.seed)
    records: list[dict] = []

    def on_case(cr) -> None:
        records.append(case_record(cr))
        print(f"[{len(records)}/{len(cases)}] {cr.case.id} {'ok' if cr.ok else 'FAIL'} "
              f"{cr.seconds:.1f}s {cr.failures[:2]}", file=sys.stderr, flush=True)
        if args.transcripts:
            with open(args.transcripts, "w", encoding="utf-8") as fh:
                json.dump(records, fh, indent=1, ensure_ascii=False)

    cap = None
    if args.provider:
        os.environ.setdefault("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
        from ..connections import TieredProvider, build_provider

        inner = build_provider(args.provider, base_url=args.base_url,
                               models={"strong": args.model} if args.model else None)
        provider = TieredProvider(inner, {}, forced=args.model) if args.model else inner
        _, summary = run_eval(provider, cases, use_gate=not args.no_gate, record=True,
                              on_case=on_case)
        summary["provider"], summary["model"] = args.provider, args.model
    else:
        if args.live:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                print("ANTHROPIC_API_KEY not set: live eval skipped")
                return 0
            provider, cap = AnthropicProvider(), args.max_cost
        else:
            provider = MockProvider()
        _, summary = run_eval(provider, cases, use_gate=not args.no_gate, max_cost_usd=cap)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
    if args.provider:
        return 0  # a real model is measured, not gated; the numbers go in docs/ai-live-eval.md
    bad = (summary["shipped_error_rate"] > 0 or summary["refusal_recall"] < 1.0
           or summary["failures"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
