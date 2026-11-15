# Vedic Calculation Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic Vedic calculation engine (`packages/astrology-core`) and wire it into the existing chart-request pipeline so a practitioner can queue a chart and view a computed birth chart artifact (planets, lagna, panchang, divisional charts, Vimshottari dasha, yogas with evidence).

**Architecture:** A pure, dependency-light TypeScript package computes everything from birth date/time/timezone/lat/lon. `astronomy-engine` (pure JS, MIT) supplies tropical ecliptic-of-date longitudes and sidereal time; all Vedic derivations (ayanamsa, rashi, nakshatra, vargas, dashas, yogas) are platform code with unit tests and self-consistency golden tests. The API computes the artifact synchronously when a chart request is created (queue semantics preserved: 202 + job status), stores it in the in-memory store next to chart requests, and exposes a GET artifact endpoint consumed by a new chart view page in the practitioner app.

**Tech Stack:** TypeScript, astronomy-engine, Zod, Vitest, Fastify, Next.js.

## Global Constraints

- Deterministic before generative: no LLM in this slice; all outputs from validated algorithms.
- Explainability by default: every yoga result carries an `evidence[]` array of chart facts.
- `calculationMetadata` records engine version, ayanamsa name/value, and UTC/Julian day inputs (reproducibility requirement from docs/astrology-calculation-engine.md).
- Vedic module lives behind `computeVedicChartArtifact(input)`; no Vedic logic leaks into apps.
- Sidereal zodiac with Lahiri ayanamsa; whole-sign houses for v1; mean lunar node for Rahu.
- Tolerances: ayanamsa ±0.05°, planetary longitudes validated by golden values ±0.2°, ascendant validated by sunrise self-consistency ±2.5°.

---

### Task 1: Package scaffold + time/Julian-day module

**Files:**
- Create: `packages/astrology-core/package.json`, `tsconfig.json`
- Create: `packages/astrology-core/src/time.ts`
- Test: `packages/astrology-core/src/time.test.ts`

**Interfaces:**
- Produces: `toUtcDate(birthDate: string, birthTime: string, timezoneName: string): Date` (IANA tz → UTC via Intl offset probing), `julianDay(date: Date): number`.

Key algorithm: derive the tz offset with `Intl.DateTimeFormat(..., { timeZone })` by formatting a candidate UTC instant and iterating until the wall-clock matches (two passes handle DST edges). `julianDay = date.getTime()/86400000 + 2440587.5`.

Tests: `2020-06-15 12:00 Asia/Kolkata` → `06:30Z`; a US DST date in `America/New_York` (EDT −4); JD of `2000-01-01T12:00Z` = 2451545.0.

### Task 2: Ephemeris adapter (tropical longitudes, speed, sidereal time)

**Files:**
- Create: `packages/astrology-core/src/ephemeris.ts`
- Test: `packages/astrology-core/src/ephemeris.test.ts`

**Interfaces:**
- Produces: `tropicalLongitude(body: EphemerisBody, date: Date): number` (geocentric ecliptic-of-date, degrees 0–360) for sun..saturn; `meanLunarNode(date: Date): number` (Meeus polynomial); `isRetrograde(body, date): boolean` (longitude delta over ±6h); `greenwichSiderealDegrees(date: Date): number` (astronomy-engine `SiderealTime` × 15).

Golden tests: Sun on 2000-01-01T12:00Z ≈ 280.37° ±0.2; mean node on J2000 ≈ 125.04° ±0.1; Mercury retrograde sample window; Sun never retrograde.

### Task 3: Ayanamsa + zodiac mapping (rashi, nakshatra, pada, lords)

**Files:**
- Create: `packages/astrology-core/src/ayanamsa.ts`, `src/zodiac.ts`
- Test: `packages/astrology-core/src/zodiac.test.ts`

**Interfaces:**
- Produces: `lahiriAyanamsa(date: Date): number` (≈23.853° at J2000 + 50.2877″/yr + quadratic term), `toSidereal(tropical: number, date: Date): number`, `signOf(lon): { index, name, lord, degreesInSign }`, `nakshatraOf(lon): { index, name, lord, pada }`, sign classification helpers (movable/fixed/dual, odd/even).

Tests: Lahiri at 2000-01-01 in [23.80, 23.90]; at 2020-01-01 in [24.08, 24.19]; 0° → Aries/Ashwini pada 1; 133°20′ → Leo, Magha ends/Purva Phalguni starts boundary; nakshatra lords follow Vimshottari order (Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury).

### Task 4: Ascendant (lagna) + whole-sign houses

**Files:**
- Create: `packages/astrology-core/src/ascendant.ts`, `src/houses.ts`
- Test: `packages/astrology-core/src/ascendant.test.ts`

**Interfaces:**
- Produces: `tropicalAscendant(date: Date, latitude, longitude): number` using RAMC = GST + geographic longitude; `asc = atan2(cos RAMC, −(sin RAMC · cos ε + tan φ · sin ε))` normalized to the correct semicircle; mean obliquity (Meeus). `wholeSignHouses(ascSiderealLon): House[]` - 12 houses from asc sign, each with sign + lord.

Self-consistency tests: at sunrise (astronomy-engine `SearchRiseSet`) ascendant ≈ Sun tropical longitude ±2.5°; ascendant advances ≈ 30° per 2 sidereal hours ±5°.

### Task 5: Planetary states - dignities, combustion, retrograde

**Files:**
- Create: `packages/astrology-core/src/dignities.ts`
- Test: `packages/astrology-core/src/dignities.test.ts`

**Interfaces:**
- Produces: exaltation/debilitation table (deep degrees), own-sign + moolatrikona tables, naisargika friendship table, `dignityOf(planet, siderealLon): Dignity` (`exalted|moolatrikona|own|friend|neutral|enemy|debilitated`), `isCombust(planet, planetTropLon, sunTropLon, retrograde): boolean` with classical orbs (Moon 12, Mars 17, Mercury 14/12R, Jupiter 11, Venus 10/8R, Saturn 15).

Tests: Sun 10° Aries exalted; Saturn 20° Libra exalted; Moon in Scorpio debilitated; Jupiter friend of Sun; combustion orb boundaries.

### Task 6: Panchang (tithi, karana, yoga, vara, hora)

**Files:**
- Create: `packages/astrology-core/src/panchang.ts`
- Test: `packages/astrology-core/src/panchang.test.ts`

**Interfaces:**
- Produces: `computePanchang(sunSidereal, moonSidereal, localWeekday): Panchang` - tithi index/name/paksha from `(moon − sun)/12°`; karana from 6° halves (7 movable cycling + 4 fixed at ends); nitya yoga from `(sun + moon)/13°20′`; vara name from weekday.

Tests: moon−sun = 0..12° → Shukla Pratipada; 180° → Purnima boundary; karana fixed names at cycle ends; yoga index for synthetic sums.

### Task 7: Divisional charts (D1, D2, D3, D7, D9, D10, D12, D30, D60)

**Files:**
- Create: `packages/astrology-core/src/vargas.ts`
- Test: `packages/astrology-core/src/vargas.test.ts`

**Interfaces:**
- Produces: `vargaSign(chart: VargaKey, siderealLon: number): number` with classical mappings: D9 `(sign*9 + part) % 12`; D7 `(sign*7 + part) % 12`; D12 `(sign + part) % 12`; D60 `(sign + part) % 12` (0.5° parts); D3 parts → same/5th/9th; D10 odd from same sign, even from 9th; D2 odd Leo/Cancer, even Cancer/Leo; D30 fixed odd/even trimsamsa spans; `computeVargaCharts(planetLons, ascLon): VargaChartSet`.

Tests: known navamsa values (e.g. 10° Aries → Cancer navamsa? verify: part 3 (10/3.333=3rd index) → Aries+3 = Cancer ✓); Taurus 0° → Capricorn navamsa; D30 span boundaries; every varga output in 0–11.

### Task 8: Vimshottari dasha (Mahadasha → Antardasha → Pratyantardasha)

**Files:**
- Create: `packages/astrology-core/src/dasha-vimshottari.ts`
- Test: `packages/astrology-core/src/dasha-vimshottari.test.ts`

**Interfaces:**
- Produces: `computeVimshottari(moonSiderealLon: number, birthUtc: Date): VimshottariDasha` - lords (Ketu 7, Venus 20, Sun 6, Moon 10, Mars 7, Rahu 18, Jupiter 16, Saturn 19, Mercury 17; total 120y), balance from fraction of nakshatra traversed, 3 nested levels with ISO start/end dates (year = 365.2425 d), each period `{ level, planet, start, end }`.

Tests: Moon at 0° Ashwini → full Ketu balance (7y); Moon mid-nakshatra → half balance; sequence order; AD durations proportional (`mdYears × adYears / 120`); nesting sums equal parent span ±1 day.

### Task 9: Aspects, conjunctions, yoga detection with evidence

**Files:**
- Create: `packages/astrology-core/src/aspects.ts`, `src/yogas.ts`
- Test: `packages/astrology-core/src/yogas.test.ts`

**Interfaces:**
- Produces: `computeAspects(planetSigns): Aspect[]` (sign-based graha drishti: all 7th; Mars +4/+8; Jupiter +5/+9; Saturn +3/+10), `computeConjunctions(planetSigns)`, `detectYogas(chart): YogaResult[]` where `YogaResult = { key, name, present, description, evidence: string[] }` for: Gajakesari, Budhaditya, Chandra-Mangal, Panch Mahapurusha (all five), Kemadruma, Kaal Sarp.

Tests: synthetic charts asserting each yoga present/absent with evidence strings referencing actual placements.

### Task 10: Chart artifact orchestrator

**Files:**
- Create: `packages/astrology-core/src/chart.ts`, `src/types.ts`, `src/index.ts`
- Test: `packages/astrology-core/src/chart.test.ts`

**Interfaces:**
- Consumes: everything above.
- Produces: `computeVedicChartArtifact(input: BirthDataInput): VedicChartArtifact` with `calculationMetadata` (engineVersion, ayanamsa name+value, utc, julianDay), `ascendant`, `planets[]` (lon, sign, nakshatra+pada, house, dignity, retrograde, combust), `houses[]`, `panchang`, `vargas`, `vimshottari`, `yogas`, `aspects`.

Golden test: full artifact for `1990-01-01 10:30 Asia/Kolkata, Varanasi (25.3176, 82.9739)` - assert structural completeness, Sun sidereal sign = Sagittarius (Sun tropical ≈ 280.5 − ayanamsa 23.84 ≈ 256.7), 9 planets, 12 houses, 120-year dasha coverage.

### Task 11: API wiring - compute artifact on chart request + artifact endpoint

**Files:**
- Modify: `apps/api/src/db/client.ts` (add `chartArtifacts`), `apps/api/src/modules/chart-requests/repository.ts`, `routes.ts`, `apps/api/package.json`
- Test: `apps/api/src/modules/chart-requests/artifact.test.ts`

**Interfaces:**
- Produces: `POST /api/v1/charts/generate` now resolves the birth record, computes the artifact, marks the request `completed` (or `failed` with error); `GET /api/v1/charts/jobs/:jobId` includes status; `GET /api/v1/charts/jobs/:jobId/artifact` returns the full artifact or 404/409.

Tests: end-to-end through the Fastify app: create client → birth record → generate → fetch artifact → assert planets/dasha/yogas present; artifact 404 for unknown job.

### Task 12: Chart view UI

**Files:**
- Create: `apps/web-practitioner/app/charts/[jobId]/page.tsx`, `components/chart-artifact-view.tsx`
- Modify: `apps/web-practitioner/components/client-intake-form.tsx` (link to chart after queueing)
- Test: `apps/web-practitioner/components/chart-artifact-view.test.tsx`

Renders: birth metadata, planet table (sign, degrees, nakshatra/pada, house, dignity, flags), lagna, panchang card, Vimshottari mahadasha timeline with expandable antardashas, detected yogas with evidence lists, varga summary. Test asserts planet table + yoga evidence render from a fixture artifact.

### Task 13: Full verification + e2e

Run `pnpm -r lint`, `pnpm -r test`, and the Playwright e2e (extended to click through to the chart view). Commit.

## Self-Review

- **Spec coverage:** covers ephemeris, ayanamsa, lagna, rashi/nakshatra/pada, houses, dignities/combustion/retrograde, panchang, 9 vargas, Vimshottari 3 levels, aspects, 9 yogas with evidence, pipeline wiring, UI. Deferred (future plans): Shadbala/Ashtakavarga, other dasha systems, transits, remedies, AI assistant, PDF.
- **Placeholder scan:** none; formulas specified inline.
- **Type consistency:** artifact type defined once in Task 10 `types.ts`, consumed by API (Task 11) and UI fixture (Task 12).
