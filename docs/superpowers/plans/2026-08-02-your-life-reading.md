# Your Life Reading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic `lifeStory` (hybrid / age bands / dasha chapters) to the existing Deep reading payload and show it above Deep reading in the Reading tab.

**Architecture:** Python `build_life_story()` attached inside `build_reading()`; Fastify bridge passthrough; `ReadingPanel` renders Your Life with a lens switcher.

**Tech Stack:** Python (`nakshatra_interpret`), Fastify reading bridge, Next.js `reading-panel.tsx`

## Global Constraints

- Deterministic only — no LLM
- Additive `reading.lifeStory`; keep 7 existing sections
- Evidence on every item
- Fail-closed with existing reading error path
- Precision Ledger visual language

---

## File map

| File | Role |
|------|------|
| `services/api-py/src/nakshatra_interpret/life_story.py` | NEW composer |
| `services/api-py/src/nakshatra_interpret/reading.py` | Wire `lifeStory` |
| `services/api-py/src/nakshatra_interpret/__init__.py` | Export if needed |
| `services/api-py/tests/test_life_story.py` | NEW unit tests |
| `services/api-py/tests/test_reading.py` | Assert `lifeStory` present |
| `apps/web-practitioner/components/reading-panel.tsx` | Types + UI |
| `apps/web-practitioner/components/reading-panel.test.tsx` | UI tests |
| `apps/web-practitioner/app/globals.css` | Your Life styles |
| `apps/api/.../reading.test.ts` | Assert lenses keys |

---

### Task 1: Python life-story composer + tests

**Files:**
- Create: `services/api-py/src/nakshatra_interpret/life_story.py`
- Create: `services/api-py/tests/test_life_story.py`
- Modify: `reading.py`, `__init__.py`, `test_reading.py`

- [x] Step 1: Write failing tests for structure, evidence, determinism, 5 age bands, hybrid length
- [x] Step 2: Implement `build_life_story(artifact, now)` per spec
- [x] Step 3: Attach in `build_reading`; run pytest until green
- [ ] Step 4: Commit

### Task 2: Reading panel UI

**Files:**
- Modify: `reading-panel.tsx`, `reading-panel.test.tsx`, `globals.css`

- [x] Step 1: Extend types; render Your Life + lens switcher above Deep reading
- [x] Step 2: Tests for hybrid default + missing `lifeStory`
- [ ] Step 3: Commit

### Task 3: API contract smoke

**Files:**
- Modify: `apps/api/src/modules/chart-requests/reading.test.ts`

- [x] Step 1: Assert `lifeStory.lenses` keys when reading succeeds
- [ ] Step 2: Commit

---

## Spec reference

`docs/superpowers/specs/2026-08-02-your-life-reading-design.md`
