# Nakshatra Chart AI — Gap Analysis & Roadmap

_Date: 2026-08-02 · Status: planning (build best-in-class grounded assistant)_

## Phase status

| Phase | Status |
|-------|--------|
| 1 Per-chart memory (local + Prisma + history) | **Done** |
| 2 Streaming + tool status + stop | **Done** |
| 3 Grounding hardener + lifeStory tools | **Done** |
| 4 Eval suite | **Done** |
| 5 Classical RAG (vectors) | **Done** |

A practitioner/client assistant that is **chart-native**: available on every chart, remembers **that** chart’s conversation, answers only from computed facts + optional classical knowledge, and never invents placements. Quality = grounding + memory + UX + evaluation — not “more LLM.”

Architecture principle (unchanged):

```
Compute (artifact / engines) → Tools → LLM interprets → Cite → Validate
```

Vectors are optional later for **classical text RAG**, never for chart math or primary memory.

---

## Assistant overhaul (in scope with Phase 1)

Not a polish pass — rebuild the assistant experience so it feels chart-native and durable.

### UX overhaul
- Clear header: **Chart Assistant** + “Memory for this chart only” + lagna/dasha chip
- Message bubbles (user navy / assistant white) instead of flat Q/A blocks
- Citation chips `[n]` as buttons opening fact details
- Empty state with chart-derived suggestions + short grounding blurb
- Composer: textarea (Enter send / Shift+Enter newline), clear-thread control
- Busy state: “Consulting the chart…” with disabled input
- Offline/error banner stays fail-soft

### Memory overhaul
- Persist thread keyed by `jobId` (localStorage now; Prisma next)
- Send last N history turns to the model on every ask
- Switching charts loads that chart’s thread only
- Explicit **Clear conversation** for current chart

### Intelligence overhaul (same PR where cheap)
- `askAssistant(..., history)` in orchestrator
- System prompt note: prior turns are about **this** chart only
- Suggested prompts include one Your Life / life-stage question when useful

### Deferred to Phase 2+ (not this overhaul PR)
- SSE streaming, stop button, Prisma conversations, vector RAG, citation→scroll highlight

---

## What we already have (strengths)

| Capability | Status |
|------------|--------|
| Per-job API `POST .../jobs/:jobId/assistant` | Shipped |
| Tool loop (max 6 rounds) over computed data | Shipped |
| Tools: birth chart, dashas, yogas, strengths, transits, predictions, remedies | Shipped |
| Citation registry from tool calls + normalize | Shipped |
| System prompt: grounding, refusals, advisory footer | Shipped |
| UI panel on chart page + suggested prompts from artifact | Partial |
| Mock client for CI (`OLLAMA_MOCK=1`) | Shipped |
| Rate limiting on assistant route | Shipped |

This is a solid **grounded MVP**. It is not yet a best-in-class product assistant.

---

## Current gaps (ranked)

### P0 — Must fix for “best AI” credibility

1. **No per-chart memory**  
   Thread is React `useState` only. Refresh loses chat. Switching charts remounts empty. Backend `askAssistant` sends **only the current question** — no prior turns.  
   *Impact:* Feels amnesiac; follow-ups (“what about that house?”) fail.

2. **No server-side conversation persistence**  
   Original plan’s `Conversation` / `Message` models were never built. No audit trail of Q&A beyond a thin audit event.  
   *Impact:* Can’t resume across devices; can’t train evals; multi-practitioner later breaks.

3. **No streaming**  
   Plan called for SSE token stream + “consulting dashas…” tool status. Today: one-shot JSON wait.  
   *Impact:* Feels slow/offline; no stop button.

4. **Weak post-answer grounding check**  
   Citations exist from tools used, but no check that every factual sentence has a `[n]`, and no claim-vs-artifact validator.  
   *Impact:* Model can still drift in prose between citations.

5. **Assistant discoverability / always-on chart help**  
   Dock exists but is easy to miss; not deep-linked (`?assistant=open`); not clearly “for this chart only.”  
   *Impact:* Users don’t experience “AI on every chart.”

### P1 — Quality & product depth

6. **Tools don’t expose Deep reading / Your Life**  
   New deterministic `lifeStory` + reading sections aren’t assistant tools.  
   *Impact:* Assistant can’t summarize childhood/dasha chapters the UI already has.

7. **No conversation compression / windowing**  
   When memory lands, unbounded history will blow context. Need last-N + optional summary.  
   *Impact:* Cost, latency, and forgotten early facts without a summary.

8. **Citation UX incomplete**  
   Plan: chips → popover → scroll/highlight chart section. Today: plain markdown + citation list.  
   *Impact:* Trust is harder to feel.

9. **Eval harness thin**  
   Unit tests with mock Ollama; no golden Q→must-cite / must-refuse suite; no live regression.  
   *Impact:* Can’t measure “best” objectively.

10. **Model/ops clarity**  
    Default model env; no boot health ping surfaced in UI; offline banner exists but no “retry / model status.”

### P2 — Later differentiators (not first)

11. **Classical knowledge RAG (vectors)**  
    Embed BPHS / house karaka notes / remedy glossaries. Retrieve *interpretation language* only; placements still from tools.  
    *Do not* use vectors as chart memory.

12. **Multi-chart / client-level memory**  
    “Compare this chart to last year’s reading” — needs client-scoped store + strict identity rules.

13. **Practitioner notes injection**  
    Optional: attach session notes the AI may quote with citation type `note`.

14. **Voice / WhatsApp / export transcript**  
    After core chat is excellent.

---

## What we will *not* do first

- **Vector DB as primary memory** — wrong tool for per-chart Q&A; fuzzy retrieval risks wrong-chart facts.
- **LLM-first chart computation** — already rejected; keep Swiss/engine truth.
- **One global chat across all charts** — violates “memory per chart.”

---

## Recommended phases

### Phase 1 — Per-chart memory (next build)

**Goal:** Every chart has its own durable thread; follow-ups work.

1. **Client persistence (fast path)**  
   - Key: `nk-assistant-thread:${jobId}` in `localStorage` (or IndexedDB if large).  
   - Load on mount; save after each exchange; clear/reset control.  
   - Isolates charts immediately.

2. **API: accept history**  
   - `POST .../assistant` body: `{ question, history?: { role, content }[] }`.  
   - `askAssistant` prepends last N turns (e.g. 12 messages) after system prompt, before new question.  
   - Still bind tools to **this** job’s artifact only.

3. **Server persistence (right path)**  
   - Prisma: `AssistantConversation(chartRequestId unique)`, `AssistantMessage(role, content, citationsJson, toolsUsedJson, createdAt)`.  
   - `GET .../jobs/:jobId/assistant/thread` + persist on each answer.  
   - Prefer server as source of truth; hydrate UI from API, localStorage as offline cache.

4. **UX**  
   - Show “Memory for this chart only” subtitle.  
   - “Clear conversation” scoped to current `jobId`.  
   - Empty state suggestions stay chart-derived.

**Exit criteria:** Reopen same chart after refresh → thread restored. Open different chart → different thread. Follow-up question references prior answer correctly under mock + live smoke.

### Phase 2 — Streaming + tool status + stop

- SSE (or ReadableStream) from API; UI appends tokens.  
- Status line while tools run (`consulting dashas…`).  
- AbortController / stop button.  
- Keep fail-soft: offline banner, chart unaffected.

### Phase 3 — Grounding hardener + richer tools

- Add tools: `get_reading_summary`, `get_life_story(lens?)` (deterministic JSON from reading/lifeStory).  
- Post-check: flag answers with astrological nouns but no `[n]`.  
- Optional: lightweight claim extractor vs artifact fields (planet/sign/house whitelist).  
- Citation chips → highlight planet/dasha/transit DOM ids.

### Phase 4 — Eval suite (“best” becomes measurable)

- Golden set: 30–50 questions on Raiganj + 2 other fixtures.  
- Assert: citations nonempty for factual answers; refusals for banned topics; no invented planet/sign pairs.  
- CI: mock path always; `@live` optional against Ollama.

**Shipped:** `packages/ai-orchestrator/src/eval/` — 41 cases across `raiganj-2003`, `varanasi-1990`, `newyork-1985`; mock harness always in CI; `@live` suite via `RUN_LIVE_EVAL=1`.

### Phase 5 — Classical RAG (vectors) — only after 1–4

- Corpus: curated classical snippets + internal significations (not random web).  
- Retrieve top-k passages; tool `search_classical(query)` returns text **with source ids**.  
- Prompt rule: classical text may color *meaning*; numbers/placements still from chart tools.  
- Vector store = knowledge library, **not** conversation memory.

**Shipped:** `packages/ai-orchestrator/src/classical/` — curated corpus + in-process TF-IDF cosine retrieval; `search_classical` tool; system prompt locks placements to chart tools. Hermetic (no external vector DB) so CI stays offline.

### Polish (post Phase 5)

- Deep-link: `/charts/:jobId?assistant=open` opens the dock and stays synced in the URL.  
- `GET /api/v1/assistant/health` + UI ready/offline banner.  
- History windowing: when threads exceed 10 messages, prepend a continuity summary of dropped turns.

---

## Suggested near-term sequence (this week)

| Order | Work | Why |
|-------|------|-----|
| 1 | Phase 1 localStorage + history in `askAssistant` | Unlocks “memory per chart” fast |
| 2 | Phase 1 Prisma thread API | Durable / multi-device |
| 3 | Phase 2 streaming | Perceived quality jump |
| 4 | Phase 3 lifeStory/reading tools + citation UX | Aligns AI with Your Life / Deep reading |
| 5 | Phase 4 evals | Protect quality as we add RAG |
| 6 | Phase 5 vectors (optional) | Classical depth without breaking grounding |

---

## Success metrics

- **Isolation:** 0 cross-chart thread leaks in tests.  
- **Continuity:** ≥95% of sessions restore last thread on revisit (same browser / account).  
- **Grounding:** 100% of factual answers in golden set have ≥1 citation; 0 hallucinated placements in eval.  
- **Latency:** First token &lt; 2s (stream); full answer &lt; 30s p95 for typical Q.  
- **Trust UX:** Citation click scrolls to chart evidence (Phase 3).

---

## Open decisions (confirm before Phase 1 server work)

1. **Memory scope v1:** localStorage-only first, or Prisma in the same PR?  
   *Recommendation:* localStorage + history payload in one PR; Prisma immediately after.  
2. **History window:** last 8 exchanges vs 12 messages + rolling summary?  
   *Recommendation:* last 10 messages, no summary until Phase 2.  
3. **Who owns the thread:** one conversation per `chartRequestId` (simplest) vs multiple named threads?  
   *Recommendation:* one thread per chart for v1.

---

## Spec / plan links

- Original vision: `docs/superpowers/plans/2026-07-09-ai-assistant-plan.md`  
- Your Life (tool fuel later): `docs/superpowers/specs/2026-08-02-your-life-reading-design.md`  
- This roadmap: `docs/superpowers/plans/2026-08-02-chart-ai-roadmap.md`
