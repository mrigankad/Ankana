# Nakshatra - Next Build Plan (stability + cutover)

_Date: 2026-08-01 · Status: Session 1–ish in progress_  
_Source: live audit (lint green, rule-engine 21✓, web:3000 / api:3001) + master plan / roadmap_

## 1. Verdict - top risks

1. **Dual backends** - Web talks to Fastify; deep reading shells out to Python. Two sources of truth, fragile spawn path, envelope drift.
2. **Turbopack monorepo root** - Already crashed once (`Next.js package not found` under `apps/web-practitioner/app`). Will keep interrupting UI work.
3. **Stale roadmap checkboxes** - ~~Phases 1–3 largely done but master plan still showed `[ ]`~~ → synced 2026-08-01.

## 2. Fix now (bugs / stability)

| # | Issue | Fix | Files | Done when |
|---|--------|-----|-------|-----------|
| F1 | Duplicate React keys (`saturn Shadbala ratio 0.91`) | Key drivers/evidence with index prefix, not raw string | `prediction-timeline.tsx` | ✅ |
| F2 | Google Sans metric spam | Prefer Next-supported font (`DM Sans`) | `layout.tsx`, `globals.css` | ✅ |
| F3 | Turbopack root fragility | Monorepo `turbopack.root` + root `next` + TS ~5.9.3 | `next.config.ts`, root `package.json` | ✅ (watch) |
| F4 | Reading via `spawn(python)` | Require `.venv`; clear 503 `reading_venv_missing` | `reading.ts`, routes | ✅ |
| F5 | Master plan checkboxes | Mark Phases 1–3 + note Fastify reality | master plan, roadmap | ✅ |

## 3. Build next (ordered slices, max 6)

| # | Slice | Goal | Depends on | Done when |
|---|--------|------|------------|-----------|
| B1 | **FastAPI cutover (5.1)** | Point web at Python API; align envelopes | F3–F5 | e2e on `:8000` |
| B2 | **Reports on FastAPI** | Port stub/PDF reports | B1 | Download PDF works |
| B3 | **Assistant on Python (4.1)** | Port Ollama tool-loop; mock for CI | B1 | Citations against FastAPI |
| B4 | **Faithfulness harness (4.2)** | Groundedness + refusal eval set | B3 | pytest/CI gates |
| B5 | **Blue UI finish** | Replace `nk-btn-gold` / gold badges | F2 | ✅ clients/intake/chart chrome |
| B6 | **Boundary chip** | Surface `boundaryWarnings` | - | ✅ TS + chip |

## 4. Defer this cycle

- New dasha systems (Ashtottari, Kalachakra, Chara)
- Auth / RBAC / Postgres / async worker
- South-Indian chart toggle, consultation notes
- Phase 6 LLM polish
- Wiring full `icons3d` library
- Deleting `apps/api` Fastify (keep until B1–B3 green)

## 5. Recommended sequence (~1 week agent sessions)

| Session | Focus |
|---------|--------|
| **1** | F1–F5 (keys, font, turbopack, reading error UX, docs sync) |
| **2** | B1 envelope audit + run FastAPI beside Fastify; smoke cutover |
| **3** | B2 reports + fix any dashboard/clients field mismatches |
| **4** | B5 blue UI pass on clients/intake/chart chrome |
| **5** | B3 assistant port (mock first) |
| **6** | B6 boundary chip + B4 eval scaffold (even if thresholds soft) |

## 6. Explicit non-goals

- No new astrology calculation engines until cutover is stable
- No more asset-prompt / raw icon churn
- No force-push / destructive git; commit only when asked
