# Python Engine Core (Plan A of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the FastAPI-bound Python workspace and port the deterministic engine core (time → ephemeris → ayanamsa → zodiac → ascendant → houses → dignities → panchang), proven equal to the TS engine by golden fixtures.

**Architecture:** Single installable Python project at `services/api-py` with `src/nakshatra_core` (engine), later `nakshatra_rules`, `nakshatra_interpret`, `app` (FastAPI). Golden fixtures are exported once from the validated TS engine (`tools/export-golden.mjs`, run with tsx) and pinned in `services/api-py/tests/golden/`. Every ported module is TDD'd against those fixtures.

**Tech Stack:** Python 3.13, pyswisseph (Moshier mode, no data files), zoneinfo (stdlib), pytest, ruff. TS side: tsx one-shot exporter.

**Follow-on plans:** B - vargas/dashas/aspects/transits/strengths; C - corrected yogas + rule engine + interpretation engine; D - FastAPI routes/DB/assistant + web cutover.

## Global Constraints

- Formula parity: port the TS formulas **exactly** (same Lahiri approximation `23.85306 + (5028.796195·t + 1.1054348·t²)/3600`, same mean-node polynomial) - do NOT substitute swisseph's built-in sidereal modes, or golden pada/sign assertions will drift.
- Golden tolerance: longitudes within ±0.05°; discrete outputs (sign index, nakshatra index, pada, house) must match exactly.
- Golden chart #1 is always the Raiganj chart: `2003-08-29 12:22 Asia/Kolkata, lat 25.6167, lon 88.1233` (expected: Scorpio lagna 14.96°, Anuradha pada 4; Sun Leo/Magha-4 house 10 moolatrikona; Mercury Virgo exalted retrograde house 11; Venus Leo combust house 10).
- JSON field names in any emitted artifact stay camelCase (match `VedicChartArtifact`).
- Commit after every green test cycle; conventional-commit messages; run `ruff check` before each commit.

---

### Task 1: Python workspace scaffold

**Files:**
- Create: `services/api-py/pyproject.toml`, `services/api-py/src/nakshatra_core/__init__.py`, `services/api-py/tests/test_smoke.py`, `services/api-py/.venv` (not committed), `services/api-py/.gitignore`

**Interfaces:**
- Produces: importable package `nakshatra_core`; `pytest` runnable from `services/api-py`.

- [ ] Step 1: `pyproject.toml` with `[project] name="nakshatra-api" requires-python=">=3.13"`, deps `pyswisseph`, dev deps `pytest`, `ruff`, `fastapi`, `uvicorn`, `httpx` (fastapi group used in Plan D but installed now); `[tool.pytest.ini_options] pythonpath=["src"]`; `[tool.ruff] line-length=100`.
- [ ] Step 2: `python -m venv .venv` then `.venv/Scripts/pip install -e .[dev]` - verify pyswisseph wheel installs on cp313/win; if no wheel, fall back to adding `skyfield` instead and note it in the plan before proceeding.
- [ ] Step 3: smoke test `import nakshatra_core; import swisseph` passes under pytest.
- [ ] Step 4: Commit `feat(api-py): python workspace scaffold with pyswisseph`.

### Task 2: Golden fixture exporter

**Files:**
- Create: `tools/export-golden.mjs` (runs TS engine via tsx), `services/api-py/tests/golden/charts.json`

**Interfaces:**
- Produces: `charts.json` = array of `{ label, input: BirthDataInput, artifact: VedicChartArtifact }` for 3 charts: (1) Raiganj golden chart, (2+3) two existing reference charts from `packages/astrology-core/src/chart.test.ts`.

- [ ] Step 1: exporter imports `computeVedicChartArtifact` from `@astro/astrology-core`, computes the 3 charts, writes pretty JSON. Run with `apps/api/node_modules/.bin/tsx tools/export-golden.mjs`.
- [ ] Step 2: verify file contains 3 artifacts, Raiganj ascendant signName "Scorpio".
- [ ] Step 3: Commit `feat(api-py): golden parity fixtures exported from TS engine`.

### Task 3: time module

**Files:**
- Create: `src/nakshatra_core/time.py`, `tests/test_time.py`

**Interfaces:**
- Produces: `to_utc_datetime(birth_date: str, birth_time: str, timezone_name: str) -> datetime` (aware, UTC); `julian_day(dt: datetime) -> float`.

- [ ] Step 1: failing tests - for each golden chart, `julian_day(to_utc_datetime(...)) == artifact.calculationMetadata.julianDay` (abs tol 1e-6) and ISO string equals `utcDateTime`.
- [ ] Step 2: implement with `zoneinfo.ZoneInfo` (naive local → `replace(tzinfo=zone)` → `astimezone(UTC)`); `julian_day = unix_seconds/86400 + 2440587.5`.
- [ ] Step 3: green, ruff, commit `feat(api-py): time module with golden julian-day parity`.

### Task 4: ephemeris module

**Files:**
- Create: `src/nakshatra_core/ephemeris.py`, `tests/test_ephemeris.py`
- Reference: `packages/astrology-core/src/ephemeris.ts` (source of truth for mean-node polynomial and retrograde probe interval)

**Interfaces:**
- Produces: `normalize_degrees(x) -> float`; `tropical_longitude(body: str, dt: datetime) -> float` for sun..saturn via `swe.calc_ut(jd_ut, planet, FLG_MOSEPH)`; `mean_lunar_node(dt) -> float` (ported polynomial); `is_retrograde(body, dt) -> bool` (swisseph speed < 0; sun/moon always False).

- [ ] Step 1: failing tests - for each golden chart and each of the 7 bodies, `|tropical + lahiri - sidereal_golden| mod 360 < 0.05`; rahu = mean node matches golden rahu within 0.01; retrograde flags equal golden.
- [ ] Step 2: implement; note astronomy-engine emits geometric geocentric ecliptic-of-date - use `FLG_MOSEPH | FLG_TRUEPOS` first, drop `FLG_TRUEPOS` if parity is worse; pick whichever passes tolerance on all three charts.
- [ ] Step 3: green, ruff, commit `feat(api-py): swisseph ephemeris with TS parity`.

### Task 5: ayanamsa + zodiac

**Files:**
- Create: `src/nakshatra_core/ayanamsa.py`, `src/nakshatra_core/zodiac.py`, `tests/test_zodiac.py`
- Reference: `packages/astrology-core/src/ayanamsa.ts`, `zodiac.ts`

**Interfaces:**
- Produces: `lahiri_ayanamsa(dt)`, `to_sidereal(trop, dt)`; constants `SIGN_NAMES`, `SIGN_LORDS`, `NAKSHATRA_NAMES`, `NAKSHATRA_LORD_CYCLE`, `NAKSHATRA_SPAN`; `sign_of(lon) -> SignPosition`, `nakshatra_of(lon) -> NakshatraPosition` (dataclasses with index/name/lord/pada/degrees_in_sign/fraction_traversed), `is_odd_sign`, `sign_modality`.

- [ ] Step 1: failing tests - for every golden planet + ascendant: sign index/name, nakshatra name, pada match exactly.
- [ ] Step 2: port formulas verbatim from TS.
- [ ] Step 3: green, ruff, commit `feat(api-py): lahiri ayanamsa and zodiac mapping`.

### Task 6: ascendant + whole-sign houses

**Files:**
- Create: `src/nakshatra_core/ascendant.py`, `src/nakshatra_core/houses.py`, `tests/test_ascendant.py`
- Reference: `packages/astrology-core/src/ascendant.ts`, `houses.ts` (port the exact obliquity/LST formulas; do not use swe.houses unless the ported formula fails parity)

**Interfaces:**
- Produces: `compute_ascendant(dt, latitude, longitude) -> float` (sidereal lagna longitude); `whole_sign_houses(asc_sign_index) -> list[House]`; `house_of(planet_sign_index, asc_sign_index) -> int`.

- [ ] Step 1: failing tests - golden ascendant longitude ±0.05°, sign/nakshatra/pada exact; each golden planet's house number exact.
- [ ] Step 2: port; verify against all three charts.
- [ ] Step 3: green, ruff, commit `feat(api-py): sidereal ascendant and whole-sign houses`.

### Task 7: dignities + combustion + panchang

**Files:**
- Create: `src/nakshatra_core/dignities.py`, `src/nakshatra_core/panchang.py`, `tests/test_dignities.py`, `tests/test_panchang.py`
- Reference: `packages/astrology-core/src/dignities.ts`, `panchang.ts`

**Interfaces:**
- Produces: `dignity_of(planet, sign_index, degrees_in_sign) -> str`; `is_combust(planet, planet_lon, sun_lon, retrograde) -> bool`; `compute_panchang(dt) -> Panchang` (tithi/karana/yoga/vara/moon nakshatra dataclasses).

- [ ] Step 1: failing tests - golden dignity and combust flags per planet exact; golden panchang names/indices exact (Raiganj: Shukla Dwitiya, Kaulava, Sadhya, Shukravara, Uttara Phalguni-2).
- [ ] Step 2: port tables and orbs verbatim.
- [ ] Step 3: green, ruff, commit `feat(api-py): dignities, combustion, panchang`.

### Task 8: parity report gate

**Files:**
- Create: `tests/test_parity_core.py`

- [ ] Step 1: one table-driven test sweeping all golden charts × all core fields ported so far; prints a parity summary on failure.
- [ ] Step 2: full suite green; `ruff check` clean; commit `test(api-py): core parity gate over golden charts`.
- [ ] Step 3: update `docs/roadmap-status.md` "Python port" section: Plan A done, Plan B next.
