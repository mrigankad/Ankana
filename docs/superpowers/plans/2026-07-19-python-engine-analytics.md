# Python Engine Analytics (Plan B of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the analytical layers - vargas, Vimshottari + Yogini dashas, aspects/conjunctions, transits, Ashtakavarga/SAV, Shadbala, Vimshopaka - golden-validated against `tests/golden/charts.json`.

**Architecture:** Same pattern as Plan A: each module is an exact port of its TS counterpart in `packages/astrology-core/src/`, TDD'd against the golden artifacts. Task = (failing golden test → port → green → ruff → commit).

**Tech Stack:** Python 3.13, astronomy-engine, pytest.

## Global Constraints

- Same as Plan A (exact formula parity, tolerance ±0.05° longitudes, discrete fields exact, camelCase JSON on serialization later).
- TS sources of truth: `vargas.ts`, `dasha-vimshottari.ts`, `dasha-yogini.ts`, `aspects.ts`, `transits.ts`, `ashtakavarga.ts`, `shadbala.ts`, `vimshopaka.ts`.

---

### Task 1: vargas (D1–D60 subset)
- [ ] Golden test: every varga chart's per-planet sign index matches `artifact.vargas`.
- [ ] Port `varga_sign` + `compute_varga_charts`; green; commit `feat(api-py): varga charts`.

### Task 2: Vimshottari dasha
- [ ] Golden test: birth nakshatra/lord, balance years, all mahadasha lords + ISO start/end (±1 min), antardasha and pratyantardasha structure for first MD.
- [ ] Port; green; commit `feat(api-py): vimshottari dasha`.

### Task 3: Yogini dasha
- [ ] Golden test vs `artifact.yoginiDasha` (same treatment as Task 2).
- [ ] Port; green; commit `feat(api-py): yogini dasha`.

### Task 4: aspects + conjunctions
- [ ] Golden test: full `artifact.aspects` and `artifact.conjunctions` lists match (source, target, type/orb fields).
- [ ] Port; green; commit `feat(api-py): graha drishti aspects and conjunctions`.

### Task 5: Ashtakavarga + Sarvashtakavarga
- [ ] Golden test: per-planet bindu rows and SAV totals equal golden exactly.
- [ ] Port; green; commit `feat(api-py): ashtakavarga and sarvashtakavarga`.

### Task 6: Shadbala + Vimshopaka
- [ ] Golden test: per-planet totals within 1e-6 of golden; component breakdown fields equal.
- [ ] Port; green; commit `feat(api-py): shadbala and vimshopaka strengths`.

### Task 7: transits
- [ ] Golden test: port `transits.ts` API; validate a transit snapshot for 2026-07-19 against TS output exported into `tests/golden/transits.json` (extend exporter).
- [ ] Port; green; commit `feat(api-py): transit engine`.

### Task 8: analytics parity gate
- [ ] Extend `test_parity_core.py` sweep to all Plan B fields; full suite green; commit `test(api-py): analytics parity gate`; tick roadmap Plan B.
