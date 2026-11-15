# AI assistant live evaluation (real models, no API cost)

Date: 2026-11-14. First time the Ankana assistant eval ran against real models. Everything
went through the local logins (`claude_code` provider kind = the `claude` CLI on the
user's own login; `ollama_local`). No API key was used and the Anthropic API was never
called directly. The reported `cost_usd` in the raw summaries is notional (list price of
the equivalent API tokens), not money spent.

## How to run

```
cd services/api-py
python -m ankana_ai.eval --provider claude_code --model haiku \
    --transcripts out.records.json --json out.summary.json          # full suite (118 cases)
python -m ankana_ai.eval --provider claude_code --model sonnet --limit 30   # stratified sample
python -m ankana_ai.eval --provider ollama_local --model qwen3:8b --limit 30
python -m ankana_ai.eval --provider claude_code --model haiku --no-gate --cases refuse-1,refuse-2
```

Flags added: `--provider` (any kind in `connections.KINDS`), `--model` (forced for every
call), `--base-url`, `--limit N` (deterministic round-robin sample across refusal / benign /
ported / golden by language, `--seed`), `--cases id,id`, `--transcripts` (one record per
case, written after every case so a killed run keeps its results). Cases run one at a time
(concurrency 1). Each record holds latency, rounds, claims checked and failed on the first
pass, rewrites, dropped sentences, refusal correctness, gated flag, the final answer and the
raw transcript (every model reply with usage and per-call seconds). Without `--provider`
the command is the unchanged mock eval used by CI.

## Results

Latency is wall clock per case for cases that called a model (gated refusals cost 0 s and
are excluded). First-pass claim accuracy is the share of declared claims correct before the
rewrite policy.

| | haiku, full suite | sonnet, 30 sampled | haiku, gate off, refusal prompts only |
|---|---|---|---|
| Cases / model-calling cases | 118 / 77 | 30 / 18 | 26 / 26 |
| Cases passed | 115 (97.5%) | 30 (100%) | 26 (100%) |
| Claims checked, first pass | 412 | 127 | n/a |
| Claim accuracy, first pass | 89.8% (42 wrong) | 100% | n/a |
| Cases that needed a rewrite | 6 | 0 | n/a |
| Sentences dropped by the policy | 13 (3 cases) | 0 | n/a |
| Shipped error rate (independent re-check) | 0 for facts the policy kept; but see failure 1 to 3 | 0 | n/a |
| Refusal recall | 41/41 (all by the gate) | 12/12 | 26/26 by the model alone |
| Over-refusal on benign near misses | 0/10 | 0/4 | n/a |
| Hinglish and Hindi answer cases | 14/14 pass | 6/6 pass | refusals 11/11 |
| Mean model rounds | 2.09 | 2.00 | 1.00 |
| Latency p50 / p95 | 16.7 s / 30.1 s | 12.3 s / 14.8 s | 9.1 s / 12.8 s |

Ollama `qwen3:8b` (5.2 GB, pulled free, fits the disk): not measurable on this machine. It
runs 70% on CPU; the first call of the first case took more than 10 minutes with the
(now fixed) 4096-token window, and two earlier cases hit the 120 s client timeout. A full
assistant turn needs two or more calls of about 6k prompt tokens each. After the fix
one case (an-moon) completed: 639 s, 3 rounds, no wrong claims but the nakshatra claim was
missing, so it failed the golden check. At that speed 30 cases would take 5 hours or more, so
no sample metrics are reported. The two provider bugs found while trying are fixed
below; a GPU box or a smaller prompt is needed to evaluate local models properly.

Failures before the fixes were all in one place: the three `*-transits` cases ("what do
current transits look like, including sade sati") failed for haiku (3 of 3) and for sonnet
(3 of 3). Sonnet on five targeted cases before the fix: 2 passed, 3 failed, first-pass claim
accuracy 27.8% (10 of 36).

## Before / after (same cases, same models)

| Cases | Before | After |
|---|---|---|
| haiku: rg/vn/ny-transits | 0/3 pass, 3 partial answers | 3/3 pass, status verified, 22/22 claims right first pass |
| sonnet: rg/vn/ny-transits | 0/3 pass, 7 sentences dropped | 3/3 pass, status verified, 18/18 claims right first pass |
| Hinglish refusal text | English text (gate) | Hinglish text (unit tested, not model dependent) |
| Ollama request | 4096 context, thinking on, 120 s | 16384 context, thinking off, 600 s (env override) |

## Failures, worst first, with root cause

Only six distinct case/model failures exist (all one root cause), so the list continues with
the near misses that needed a rewrite.

1. **haiku ny-transits.** First reply put transit Saturn in Pisces and Jupiter in Leo, all
   correct for the sky, as `planet_sign` claims citing `get_transits`. The verifier compared
   them to the natal chart (Saturn natal Libra, Jupiter natal Capricorn), "corrected" them
   and the user saw `Saturn is in Libra 29.02 deg, house 10` as the fix. Wrong and
   confidently shipped. Root cause: no claim type or check for transits (A).
2. **haiku vn-transits.** Same: "Saturn in Pisces, second house" flagged against natal
   Sagittarius, replaced by natal facts after a rewrite the model could not satisfy (it was
   right the first time). Root cause (A).
3. **haiku rg-transits.** Same; also "Saturn sits in your fifth house" judged against natal
   house 8. Root cause (A).
4. **sonnet rg-, vn-, ny-transits.** Identical pattern, three more answers where correct
   statements were replaced by natal facts ("Could not verify this statement. Chart data:
   Saturn is in Gemini ..."). Root cause (A). Stronger models do not help: the verifier is
   the bug.
5. **haiku rg-strengths (rewrite).** The model attached a `planet_sign` claim with no sign to
   a Shadbala sentence because no claim type fits. Verifier rejected it ("missing sign"),
   a wasted round. Root cause (B): prompt did not say that facts without a claim type
   take an empty claims list.
6. **haiku vn-career (rewrite, 2 of 6 claims wrong).** Career answer mixed transit
   statements with natal claim types; rewrite needed. Root cause (A) in part.
7. **haiku an-hi-moon (rewrite).** First draft said "your Moon is not in Pisces, it is in
   Leo" (Hindi). The undeclared-claim scan flagged the negated sign. Rewrite fixed it. Root
   cause (C): the scan does not understand negation. Harmless today (one extra round), noted.
8. **Hinglish refusal (all 6 gated Hinglish refusals).** The deterministic gate answered a
   Hinglish question in English because only `en` and `hi` texts existed. Not scored as a
   failure by the harness, found by reading transcripts. Root cause (D), fixed.
9. **Ollama truncation.** `OllamaProvider` sent no `num_ctx`, so Ollama used 4096 tokens and
   silently cut the system rules and chart digest (about 6k tokens). Root cause (E), fixed.
10. **Ollama timeout and thinking.** Fixed 120 s HTTP timeout and qwen3 thinking left on.
    Root cause (E), fixed.

Not a failure but worth knowing: with `claude_code` the model picks the feminine form in
Hinglish refusals ("kar sakti hoon") while the gate texts use the masculine; Hinglish
answers keep English sign names (Leo, Scorpio) and "6th bhava" rather than Hindi names. Both
read naturally to a practitioner. Hindi (Devanagari) answers were clean in 14/14 cases.

## Fixes

A. **Transit claims** (`verifier.py`, `tools.py`, `prompt.py`, `assistant.py`). New claim types
   `transit_sign` (planet, sign, house from the natal lagna) and `sade_sati` (present),
   checked against `compute_transit_snapshot` at the question's reference date (the
   `Verifier` now takes `now`). A `planet_sign` or `planet_house` claim that cites the
   `get_transits` result is treated as a transit claim, so models that ignore the new
   types are still judged against the sky. The undeclared "planet in sign" scan compares
   with the sky when a transit word (`transit`, `gochar`, `sade sati`) appears just before
   the match, and still uses the natal chart otherwise. The prompt tells the model which
   type to use.
B. **Prompt**: facts with no claim type (Shadbala, remedies) stay in text with empty claims.
D. **Hinglish refusal texts** for all six categories (`safety.py`).
E. **OllamaProvider**: `num_ctx` 16384 (`ANKANA_OLLAMA_NUM_CTX`), `num_predict` from the
   request, `think: false`, timeout 600 s (`ANKANA_OLLAMA_TIMEOUT`).

Tests: `tests/test_ai_live_eval_fixes.py` (11 tests) covers transit and sade sati checks,
re-routing of cited transit claims, sky versus natal in the scan, no reference date, Hinglish
refusal, the Ollama request shape and the sample selector. Mock eval and the full suite stay
green, ruff clean.

## Remaining risks

- Only claim types the verifier knows are checked. Undeclared statements are only scanned
  for "planet in sign". Examples seen in real answers and not verified: "Guru is lord of the
  1st and 10th" (house lord, true here), Shadbala ratios, prediction windows, remedies. A
  wrong house-lord or yoga mentioned in prose passes. Next step: extend the scan to house
  lords and yoga names.
- Negated statements ("not in Pisces") can trigger the scan and cost a rewrite round.
- Sample sizes are small: 118 cases on one chart family (Ananya plus three older fixtures),
  one run per model, no repeat runs, no temperature control through the CLI. Sonnet saw 30
  of 118 cases and none of the three transit cases in its sample (they were run separately).
- The model alone refused all 26 refusal prompts (haiku), but the gate is what ships; its
  recall on unseen phrasings is not measured by this suite (all prompts are known to the
  regexes' authors).
- Local models are unverified. qwen3:8b needs a GPU or a trimmed prompt; the protocol uses
  native tool calling for Ollama, which small models do unreliably.
- The CLI path costs about 10 to 30 s per answer and no token streaming. p95 of 30 s is
  acceptable for an assistant but not for inline lookups.
- Costs shown in summaries are notional for `claude_code`; real spend is the user's plan
  quota.
