# Master End-to-End Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax. This plan merges Plan D (FastAPI backend completion) and Plan R (research-informed hardening) into one ordered sequence. Plans A–C (engine core, analytics, yogas + interpretation engine) are DONE - 33 pytest green in `services/api-py`.

**Goal:** A complete FastAPI backend serving trustworthy, deep, evidence-cited chart analysis, with the web app cut over to it.

**Tech Stack:** Python 3.13, FastAPI, SQLModel/SQLite, astronomy-engine, pytest; Next.js web app unchanged except API base + new Reading tab.

## Global Constraints
- Golden parity with the TS engine remains binding for all existing fields; new behavior must be additive (new fields) or provably identical on the golden charts.
- Every prediction/reading paragraph carries evidence citations.
- Commit per green test cycle; ruff clean.

---

### Phase 1 - Accuracy hardening (R1)
- [x] 1.1 Boundary-case suite: synthetic longitudes ±0.1°/±0.01° around sign, nakshatra, and pada boundaries; assert deterministic floor behavior; artifact gains additive `boundaryWarnings: [{body, kind, distanceDeg}]` (threshold 0.1°) so the UI can flag birth-time-sensitive charts.
- [x] 1.2 Sunrise-based vara: sunrise/sunset via astronomy-engine rise/set search; vara = weekday of last sunrise at or before birth (calendar weekday only as fallback). Identical on all three golden charts (all born after sunrise); new test with a 03:00 birth asserting previous-day vara. Artifact gains additive `sunrise`/`sunset` ISO fields.
- [x] 1.3 Cross-validation vs jyotishganit (independent engine, JPL DE421, True Chitra ayanamsa): optional dev-dependency; comparison script over golden inputs asserting sign/nakshatra/pada agreement, longitudes within 2 arcmin. Skippable marker if package unavailable.
- [x] 1.4 Document ICRC Lahiri anchor (J2000 = 23.853222°) next to our 23.85306 constant.

### Phase 2 - Rule engine port + richer predictions (D + R5)
- [x] 2.1 Port `nakshatra_rules.remedies` from packages/rule-engine/src/remedies.ts with the `type` field bug fixed; golden test against TS outputs for the Raiganj chart (re-exported fixture).
- [x] 2.2 Port `nakshatra_rules.predictions` (evaluator + vedic-predictions pack), then enrich: each prediction gains `headline`, 2–4 sentence `body` composed from MD/AD lords' natal roles (house, lordships, dignity, mutual relation), `confidence` (low/med/high from Shadbala ratio + SAV bands with numeric drivers in evidence), linked remedy when a weak functional benefic drives the window.
- [x] 2.3 Contradiction surfacing: same-domain opposing rules in overlapping windows merge into a single "tension" prediction listing both sides.
- [x] 2.4 Endpoints: `POST /api/v1/charts/predictions`, `POST /api/v1/charts/remedies` (stateless, artifact computed on the fly), covered by route tests.

### Phase 3 - Persistence + full route surface (D)
- [x] 3.1 SQLModel models mirroring Prisma schema (Client, BirthRecord, ChartRequest, Artifact, AuditEvent); SQLite `services/api-py/data/api.db`.
- [x] 3.2 Clients module: `POST/GET /api/v1/clients`, `GET /api/v1/clients/{id}`, `POST /api/v1/clients/{id}/birth-records`; route tests mirror Fastify tests.
- [x] 3.3 Chart jobs: `POST /api/v1/charts/generate`, `GET /api/v1/charts/jobs/{id}`, `/artifact`, `/predictions`, `/remedies`, `/transits` - same envelopes as TS API; artifact JSON stored; reading included.
- [x] 3.4 Locations: Nominatim search + offline fallback port; `GET /api/v1/locations/search`.
- [x] 3.5 Dashboard summary + `GET /api/v1/panchang/today` + audit events + reports route.

### Phase 4 - Grounded assistant + faithfulness harness (D + R2)
- [ ] 4.1 Port assistant tool-loop to Python (Ollama HTTP), tiered: artifact → rule outputs → refuse; answerability gate before the loop; rate limiting.
- [ ] 4.2 Eval harness: counterfactual perturbation test (mutate artifact, assert answer tracks), claim-level grounding score, ~30-question negative-rejection set. CI target: groundedness ≥ 0.9, rejection recall ≥ 0.9.

### Phase 5 - Web cutover + evidence UX (D + R4)
- [ ] 5.1 `NEXT_PUBLIC_API_BASE_URL` switch; e2e smoke against FastAPI.
- [x] 5.2 Full Reading tab rendering the 7-section reading; evidence collapsed by default (progressive disclosure); boundary warnings surfaced as a "birth-time sensitive" chip.
- [x] 5.3 Predictions timeline consumes enriched predictions (headline/body/confidence).

> **Reality note (2026-08-01):** Web still defaults to Fastify (`:3001`). Deep reading
> bridges via `tools/build-reading.py` → `services/api-py/.venv`. FastAPI (`:8000`)
> has Phases 1–3; cutover is 5.1. TS artifacts now emit `boundaryWarnings` (parity
> with Python) and the chart header shows the birth-time-sensitive chip.
>
> 5.2 landed against the Fastify API via `tools/build-reading.py` bridge to
> `nakshatra_interpret` (same engine FastAPI uses).
> 5.3: `evaluatePredictionsEnriched` ports Python enrich (confidenceBand,
> drivers, tension, linked remedies); timeline shows headline + band badge.

### Phase 6 - Optional LLM polish (R3)
- [ ] 6.1 Polish step: rewrite prose only; post-check extracts numerals/planets/signs/houses from output and asserts presence in source facts, else deterministic fallback; `aiPolished: true` labeling.

Progress log: tick boxes as phases land; roadmap-status.md mirrors this.
