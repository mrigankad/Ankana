# Python Backend + Deep Reading MVP - Design

_Date: 2026-07-19 · Status: approved direction (user: "Everything", "Full Python port", "backend in FastAPI")_

## Problem

The MVP output for a real chart (golden case: **29 Aug 2003, 12:22 IST, Raiganj, West Bengal - Scorpio lagna, Anuradha 4**) is unsatisfying:

1. **Shallow** - predictions are one-line stubs ("career - rahu MD / jupiter AD"); there is no
   interpretive reading at all (no lagna analysis, planet-in-house/sign meanings, house-by-house,
   nakshatra, varga, or dasha-phala text).
2. **Partly wrong** - yoga detection over-fires: all five Pancha Mahapurusha yogas at once
   (Mars in Aquarius cannot give Ruchaka), Kemadruma alongside Sunapha/Anapha/Durudhara
   (mutually exclusive), Kaal Sarp despite Mars sitting outside the Rahu–Ketu axis.
3. Remedies emit `type: undefined` (field bug).

The user additionally wants the backend rebuilt in **FastAPI with a full Python port** of the
calculation engine (no TS compute sidecar).

## Goals

- Trustworthy yoga/dosha detection with classical conditions, exclusions, and cancellations.
- A full deterministic **interpretation layer**: sectioned reading with citations for every claim.
- Real **prediction prose** per dasha/transit window with evidence + confidence.
- **FastAPI backend** (`services/api-py`) with the engine ported to Python, replacing the
  Fastify/TS API at the same route contract so the Next.js app keeps working.
- Parity proven by **golden fixtures** exported from the validated TS engine (126 tests).

## Non-goals (this cycle)

- Auth/RBAC, Postgres, deployment (next cycle).
- Porting the Next.js frontend.
- Removing the TS engine immediately - it stays until Python parity is proven, then the TS API is retired.

## Architecture

```
services/api-py/               FastAPI app (uvicorn), SQLite via SQLModel
  app/main.py                  app factory, CORS, /health
  app/routes/                  clients, charts, locations, dashboard, reports, audit, assistant, panchang
  app/db/                      SQLModel models + migrations (mirrors Prisma schema)
packages-py/
  nakshatra_core/              engine port: time, zodiac, ephemeris (pyswisseph),
                               ayanamsa (Lahiri), ascendant, houses (whole-sign), dignities,
                               panchang, vargas (D1..D60 subset), vimshottari, yogini,
                               aspects, transits, ashtakavarga, shadbala, vimshopaka,
                               yogas (CORRECTED), chart.py -> VedicChartArtifact (same JSON shape)
  nakshatra_rules/             rule engine port + expanded prediction packs, remedies (type fixed)
  nakshatra_interpret/         NEW interpretation engine (deterministic KB + composer,
                               optional Ollama polish step)
tests: pytest per module; tools/export-golden.ts dumps TS golden values to
       tests/golden/*.json; parity tests assert Python matches within tolerance
       (longitudes ±0.05°, same sign/nakshatra/pada/house on all golden charts).
```

**Ephemeris**: `pyswisseph` (Swiss Ephemeris, Moshier fallback - no data files needed).
TS engine uses astronomy-engine; small arcsecond-level differences are expected and the
tolerance accounts for them. Lahiri ayanamsa via `swe.set_sid_mode(SIDM_LAHIRI)`.

**Artifact contract**: Python emits the exact `VedicChartArtifact` JSON shape the web app and
`shared-types` already consume, extended with `interpretation` (new) and `engineVersion`
bumped ("py-1.0.0"). Self-healing recompute in the repository layer carries over.

**API contract**: identical paths (`/api/v1/clients`, `/api/v1/charts/generate`,
`/api/v1/charts/jobs/{id}[/artifact|/predictions|/remedies|/transits|/assistant]`,
`/api/v1/locations/search`, `/api/v1/dashboard/summary`, `/api/v1/panchang/today`,
`/api/v1/reports/{id}`, `/api/v1/audit-events`), same response envelopes.
The web app switches via `NEXT_PUBLIC_API_BASE_URL` only.

## Component design

### 1. Corrected yogas (`nakshatra_core/yogas.py`)
- Pancha Mahapurusha: planet in own/moolatrikona/exalted sign AND in a kendra from lagna.
- Lunar group: Sunapha/Anapha/Durudhara from non-Sun planets flanking Moon; Kemadruma only
  when none of these hold (plus kendra-Moon cancellation).
- Kaal Sarp: all 7 classical planets strictly within one Rahu→Ketu arc; else absent.
- Every result: `{name, category, strength, evidence[], cancellations[]}`.
- Property test: contradictory yogas never co-fire; golden test on the Raiganj chart
  (expected: Budhaditya, Gajakesari checks re-derived by hand, no Mahapurusha for Mars, no Kaal Sarp,
  no Kemadruma).

### 2. Interpretation engine (`nakshatra_interpret`)
Deterministic KB (Python dicts/YAML) + composer producing `InterpretationArtifact`:
sections = lagna & temperament; planet-by-planet (sign × house × dignity × retro/combust ×
shadbala band); house-by-house (occupants + lord placement + aspects + SAV band);
yoga meanings; D9/D10 highlights; dasha phala (running + next MD/AD given natal roles);
birth panchang notes. Every paragraph carries `evidence[]` citations (placement/rule ids).
Optional `polish=ollama` step rewrites section prose when the model is reachable; output
labeled `aiPolished: true`; silent fallback to deterministic text.

### 3. Richer predictions (`nakshatra_rules`)
Windows from MD/AD overlap (as today) plus transit overlays (sade-sati phases, Jupiter
returns). Each prediction: headline, 2–4 sentence body from (MD lord role × AD lord role ×
mutual relation × dignity × strength), confidence from Shadbala/SAV bands, evidence list,
linked remedy when a weak functional benefic drives the window. Remedy `type` bug fixed.

### 4. FastAPI app
SQLModel models mirroring the Prisma schema (Client, BirthRecord, ChartRequest/Job,
Artifact, AuditEvent); SQLite file db (own file, fresh migrations); Nominatim + offline
fallback geocoding port; assistant endpoint ports the grounded tool-loop contract to
Python (Ollama HTTP); simple in-process rate limit as today; audit middleware.

## Error handling
- Unknown timezone/place → 422 with field errors (as today's Zod behavior).
- Ephemeris failure → 500 with audit event; never partial artifacts.
- Assistant: model unreachable → 503 with deterministic-answer fallback message.

## Testing
- pytest unit tests per module (TDD), golden parity fixtures exported from TS.
- Route tests via httpx TestClient mirroring existing Fastify tests.
- Existing Playwright e2e re-pointed at FastAPI once routes are up.

## Build order
1. Scaffold `services/api-py` + `packages-py` (uv, pytest, ruff) + golden export tool.
2. Engine core: time → zodiac → ephemeris → ayanamsa → ascendant → houses → dignities → panchang.
3. Vargas, Vimshottari, Yogini, aspects, transits.
4. Strengths: Ashtakavarga/SAV, Shadbala, Vimshopaka.
5. **Corrected yogas** (golden: Raiganj chart).
6. chart.py artifact composer + parity test.
7. Rule engine + richer predictions + remedies fix.
8. Interpretation engine.
9. FastAPI routes + DB + assistant + reports.
10. Web app pointed at FastAPI; Full Reading tab; e2e.
