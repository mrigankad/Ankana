# Nakshatra AI Assistant - End-to-End Plan (Ollama)

> **For agentic workers:** self-contained plan for the grounded astrology
> assistant. Prerequisites: Slices 1–4 of
> `2026-07-09-remaining-slices-handoff.md` (transits, strengths, rule
> engine) so the assistant has computed facts to cite.

**Goal:** A chat assistant on every chart page that answers questions like
"Why is my Saturn mahadasha difficult?", "When will I get married?", "Is
this a good time to change jobs?" - with every claim traceable to computed
chart data, and refusals when the data doesn't support an answer.

## LLM runtime: Ollama (operator has Ollama Pro)

- Env (in `apps/api/.env`, gitignored - NEVER commit or log):
  - `OLLAMA_BASE_URL` - `https://ollama.com` for Ollama Pro cloud, or
    `http://127.0.0.1:11434` for local.
  - `OLLAMA_API_KEY` - required for cloud; sent as
    `Authorization: Bearer <key>`.
  - `OLLAMA_MODEL` - default `qwen3:32b-cloud` class model; must support
    tool calling. Make it configurable; verify at boot with a ping and log
    the model name (not the key).
- Use the native Ollama chat API `POST /api/chat` with `stream: true` and
  `tools` (Ollama supports OpenAI-style tool definitions). Fall back to the
  OpenAI-compatible `/v1/chat/completions` if needed.
- Timeouts: 60s request, abort + user-visible error after that.

## Grounding architecture (the non-negotiable part)

```
User question ─▶ AssistantService
                   1. load artifact + strengths + dashas + transits + predictions
                   2. system prompt (persona + rules + refusal policy)
                   3. LLM with TOOLS (read-only, deterministic):
                        get_birth_chart()        → planets, houses, lagna, panchang
                        get_dashas(system?)      → periods incl. current MD/AD/PD
                        get_transits(date?)      → snapshot + sade-sati
                        get_yogas()              → detected yogas + evidence
                        get_strengths()          → shadbala/SAV summaries
                        get_predictions(domain?, horizon?) → rule-engine output
                   4. stream tokens to client (SSE)
                   5. post-check: extract [n] citation markers; if a factual
                      sentence has no citation, append a caution banner flag
```

- Tools return JSON snippets of ALREADY-COMPUTED data (from the stored
  artifact + engines). Tools never compute new astrology and never call the
  LLM.
- The model must cite: every factual astrological statement carries a
  bracket citation `[1]`, `[2]`… mapping to tool results. The service
  builds the citation registry from actual tool calls and streams it as a
  final SSE event (`event: citations`).
- Refusal policy in the system prompt: no birth-time rectification claims,
  no death/serious-disease/litigation-outcome predictions, no medical,
  legal, or financial instructions (wellness/timing framing only), no
  answers about people not in the loaded chart, no invented chart facts -
  if a tool doesn't return it, say so.
- Conversation persistence: Prisma models
  `Conversation(id, chartRequestId, createdAt)` and
  `Message(id, conversationId, role, content, citationsJson, createdAt)`.
  Audit event per exchange.

## Backend tasks

### Task A1 - `packages/ai-orchestrator`
- `src/ollama-client.ts`: thin fetch wrapper (chat + stream parse, tool-call
  loop with max 6 tool rounds). Unit tests with a mocked fetch.
- `src/tools.ts`: tool schemas + executors taking `(artifactBundle)`;
  executors are pure and tested against a golden artifact.
- `src/system-prompt.ts`: persona ("senior Jyotish practitioner, warm,
  precise, never fatalistic"), grounding rules, citation format, refusal
  policy, advisory disclaimer requirements. Snapshot-test the prompt.
- `src/assistant-service.ts`: orchestrates tool loop, emits
  `token | tool_call | citations | done | error` events. Test with mocked
  Ollama returning canned tool calls.

### Task A2 - API endpoints (`apps/api/src/modules/assistant/`)
- `POST /api/v1/charts/jobs/:jobId/conversations` → creates/returns
  conversation.
- `POST /api/v1/conversations/:id/messages` body `{ content }` → SSE stream
  (`text/event-stream`) of the event types above; persists both messages.
- `GET /api/v1/conversations/:id` → history with citations.
- 503 with a clear message when `OLLAMA_API_KEY`/model unreachable.
- Integration test with mocked orchestrator (no live LLM in CI).

---

## Frontend: end-to-end UX spec

### Placement & navigation
The assistant lives WITH the chart, not as a detached chatbot: a right-side
panel on the chart page, toggled by a floating gold action button. Desktop
≥1100px: docked panel pushes content. Below 1100px: full-height overlay
sheet. Deep link `?assistant=open`.

### Layout (desktop, docked)

```
┌────────────────────────────────────────────────┬───────────────────────────┐
│  ✦ NAKSHATRA                        Clients ▾  │  ✦ Chart Assistant    ✕   │
│                                                │  grounded in this chart   │
│  [celestial band: AQUARIUS LAGNA 20°43′ …]     │───────────────────────────│
│                                                │        (thread)           │
│  ┌ Rashi Chart (D1) ┐  ┌ Panchang ┐            │  ● You                    │
│  │   (kundali SVG)  │  │ …        │            │  Why is my Saturn         │
│  └──────────────────┘  └──────────┘            │  mahadasha difficult?     │
│                                                │                           │
│  Planetary Positions …                         │  ✦ Nakshatra              │
│  Vimshottari Dasha …                           │  Saturn runs your 12th…   │
│                                                │  house [1] while transit  │
│                                                │  Saturn sits over your    │
│                                                │  natal Moon [2] - sade    │
│                                                │  sati's peak phase…       │
│                                                │  ┌─────────────────────┐  │
│                                                │  │ [1] Saturn - Sagitt.│  │
│                                                │  │  11th house, combust│  │
│                                                │  │ [2] Transit Saturn  │  │
│                                                │  │  Aquarius, 1st from │  │
│                                                │  │  Moon · sade sati   │  │
│                                                │  └─────────────────────┘  │
│                                                │───────────────────────────│
│                                                │ Ask about this chart…  ➤  │
│                                                │ Advisory only - not      │
│                                                │ medical/legal/financial. │
└────────────────────────────────────────────────┴───────────────────────────┘
```

### Visual language (existing tokens only)
- Panel: `--bg-card` on `--off-white`, left border `--border-subtle`,
  header uses the wordmark star in gold; title in Cinzel.
- User bubbles: navy `--navy` background, white text, right-aligned,
  radius 12px with one square corner (bottom-right).
- Assistant bubbles: white card, subtle border, left-aligned; the assistant
  avatar is the gold ✦.
- **Citation chips**: inline `[1]` renders as a small gold-tinted badge
  (`--gold` at 14% bg, `--gold-dark` text, JetBrains Mono). Hover/tap opens
  a popover card with the cited chart fact; clicking scrolls the main chart
  page to the relevant section (planet row, dasha row, transit panel) and
  flash-highlights it (2s gold outline; respects reduced motion).
- Streaming: token-by-token append; a thin gold shimmer underline under the
  growing paragraph as the "typing" affordance (no bouncing dots).
- Tool activity: while tools run, a one-line status in mono:
  `consulting dasha timeline…` - never raw JSON.
- Numbers/dates inside answers render in JetBrains Mono via `<span class="data">`.

### States (all must be designed, not accidental)
1. **Empty (first open):** gold star, "Ask about this chart", and 4
   suggested prompt chips built from the actual chart data:
   - "Explain my current {currentMahadasha} mahadasha"
   - "What does my {lagnaSign} lagna say about me?"
   - "{topYogaName} - what does it mean for me?"
   - "What should I watch during the next year?"
2. **Streaming:** input disabled, stop button (square icon) replaces send.
3. **Refusal:** assistant bubble with a navy info bar: "That's outside what
   this chart can support…" - styled calmly, not like an error.
4. **LLM unreachable:** amber banner in-panel: "Assistant is offline -
   chart data is unaffected." Retry button. Chart page never breaks.
5. **Long thread:** virtualized list not required; cap render at last 50
   messages with "Show earlier".
6. **Mobile sheet:** drag handle, full-width input, citations open as
   bottom cards instead of popovers.

### Accessibility & quality floor
- Panel is `role="complementary"` labeled "Chart assistant"; thread is
  `aria-live="polite"`; every citation chip is a real `<button>` with a
  descriptive `aria-label`; focus is trapped in the overlay variant and
  returned to the toggle on close; Esc closes; all interactive elements
  keyboard-reachable; reduced-motion kills shimmer and flash-highlight.
- Persistent footer line inside the panel:
  "Guidance is advisory and never a substitute for medical, legal, or
  financial advice." (matches the app footer copy).

### Frontend tasks

- **Task F1** `components/assistant/assistant-panel.tsx` - shell, open/close
  state (URL param synced), docked/overlay responsive behavior. Test: opens
  from the floating button, focus management.
- **Task F2** `components/assistant/message-thread.tsx` +
  `message-bubble.tsx` - roles, markdown-lite rendering (bold, lists -
  sanitize, no raw HTML), citation chip parsing of `[n]`. Test: a fixture
  message with `[1]` renders a chip that opens the popover with the fact.
- **Task F3** `components/assistant/composer.tsx` - textarea autogrow (max
  5 lines), Enter=send / Shift+Enter=newline, stop-while-streaming. Test:
  disabled during stream, stop emits abort.
- **Task F4** `lib/assistant-client.ts` - SSE consumer (fetch +
  ReadableStream parse), event types mirrored from the API, abort
  controller. Unit test with a synthetic stream.
- **Task F5** Suggested prompts from artifact + empty state. Test: chips
  contain the chart's actual mahadasha planet name.
- **Task F6** Citation → chart cross-highlighting (scroll + flash via
  element ids added to planet rows/dasha rows/transit panel). Test: click
  handler targets the right element id.
- **Task F7** E2E (mock Ollama in the API via `OLLAMA_MOCK=1` env that
  streams a canned cited answer): open chart → open assistant → send
  question → streamed answer with a citation chip → chip highlights the
  planet row. This spec runs in CI; a separate `@live` tagged spec runs
  against real Ollama locally only.

### Definition of done
- All unit + integration tests green without any live LLM (mocks).
- Live smoke test against Ollama Pro succeeds locally (operator provides
  `OLLAMA_API_KEY` in `apps/api/.env`).
- No chart fact in any answer that lacks a citation to a tool result.
- Screenshots at 1280px and 390px reviewed against this spec.
