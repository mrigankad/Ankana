# Your Life (life-story reading) - Design

_Date: 2026-08-02 · Status: approved in brainstorm (Approach A, deterministic only)_

## Problem

Deep reading today is a technical ledger (lagna, planets, houses, yogas, current dasha, vargas, panchang). Practitioners and clients also need a coherent **life narrative** - childhood through later life - grounded in the same chart and Vimshottari timeline, without inventing events or using an LLM.

## Goals

- Deterministic, evidence-cited life chapters (same grounding contract as Deep reading).
- Three lenses in one payload: **hybrid** (default), **age bands**, **dasha chapters**.
- Dual audience: client-facing summary prose + expandable practitioner evidence.
- Ship inside the existing Reading flow (Approach A) - extend `/reading`, no new route, no LLM.

## Non-goals (v1)

- LLM / Ollama polish.
- Separate `/life-story` endpoint or top-level chart tab (deferred; payload can power a tab later).
- Transit triggers inside chapters; Yogini parallel chapters.
- Dated life-event predictions (“married at 28”).
- Replacing Deep reading sections.

## Decisions locked

| Topic | Choice |
|-------|--------|
| Lenses | All three: age bands, dasha chapters, hybrid |
| Audience | Both - client prose + evidence expand |
| Placement | Inside Reading tab, above Deep reading |
| Architecture | Approach A - extend reading payload + UI |
| Generation | Deterministic only (no LLM) |

## Architecture

```
artifact (VedicChartArtifact)
  -> nakshatra_interpret.build_reading()
       -> existing sections[] (unchanged)
       -> build_life_story(artifact, now)  [NEW]
            -> lifeStory { lenses: hybrid | ageBands | dashaChapters }
  -> GET /api/v1/charts/jobs/:id/reading  { reading }
  -> ReadingPanel
       -> Your Life block (lens switcher + chapters)
       -> Deep reading sections (existing)
```

Composer lives in Python (`services/api-py/src/nakshatra_interpret/`). Fastify continues to bridge via `tools/build-reading.py`. FastAPI workspace paths that already call `build_reading()` pick up `lifeStory` automatically.

## Data model

```ts
interface ChartReading {
  generatedAt: string;
  engineVersion: string;
  sections: ChartReadingSection[]; // existing 7
  lifeStory?: LifeStory;
}

interface LifeStory {
  generatedAt: string;
  birthDate: string;
  currentAgeYears: number;
  lenses: {
    hybrid: LifeChapter[];
    ageBands: LifeChapter[];
    dashaChapters: LifeChapter[];
  };
}

interface LifeChapter {
  key: string;
  title: string;
  ageRange: { from: number; to: number | null };
  years?: { start: string; end: string }; // ISO date span when known
  dashas: Array<{
    planet: string;
    level: "mahadasha";
    start: string;
    end: string;
    ageFrom: number;
    ageTo: number;
  }>;
  summary: string; // client-facing
  items: Array<{ title: string; text: string; evidence: string[] }>;
  isCurrent?: boolean;
}
```

### Fixed age bands

| Key | Title | Ages |
|-----|-------|------|
| childhood | Childhood | 0–12 |
| youth | Youth | 13–24 |
| early-adulthood | Early adulthood | 25–40 |
| midlife | Midlife | 41–60 |
| later-life | Later life | 60+ (`to: null`) |

### Dasha chapters

One chapter per Vimshottari mahadasha overlapping birth through the end of the computed tree (practically ~age 100). Title form: `"{Planet} years, age {from}–{to}"` (planet display name capitalized).

### Hybrid

Same five age-band chapters; each summary and items explicitly name mahadasha(s) active in that band.

## Chapter content rules

Deterministic composer reuses `PLANET_SIGNIFICATIONS`, `HOUSE_THEMES`, dignity phrases, and shadbala bands from Deep reading.

### Build order (per chapter)

1. Resolve window (age band and/or mahadasha span) → calendar years from birth + Vimshottari dates.
2. Collect overlapping mahadasha lord(s).
3. Natal promise of each lord: house, sign, dignity, karakas, strength band.
4. Apply life-stage theme weights (below); only claim what the chart supports.
5. Emit `summary` (2–4 sentences, plain language) + 2–4 `items` + `evidence[]` on every item.

### Age-band theme weights

| Band | Emphasize |
|------|-----------|
| Childhood 0–12 | 4th, Moon, lagna lord, early MD tone (home, care, temperament) |
| Youth 13–24 | 3rd / 5th / 9th; learning, peers, identity |
| Early adulthood 25–40 | 7th / 10th / 2nd; career, partnership, resources |
| Midlife 41–60 | 10th / 11th / 8th; authority, gains, transformation |
| Later life 60+ | 9th / 12th / 4th; dharma, release, roots |

### Dasha-chapter rules

- Body = MD lord natal promise + houses ruled from lagna + dignity/strength.
- Optional antardasha color only if an AD spans ≥ ~2 years inside the MD (keep v1 light).
- `isCurrent` when `now` falls inside the period.

### Hybrid rules

- Age-band skeleton + theme weights.
- Summary must name MD(s) in band (“Under Saturn’s years…”).
- Items may include one item per overlapping MD when useful.

### Optional through-line (hybrid only)

One short preface item: lagna + Moon nakshatra + strongest yoga name if any - temperament across chapters, evidence-cited.

### Language constraints

- Thematic timing only (“window for partnership themes”), not dated biographical events.
- No invented yogas, placements, or dasha dates - all from artifact.

## UI (Reading tab)

Inside existing Reading tab, above Deep reading:

1. **Your Life** block (`id="your-life"` or equivalent inside `#reading`)
   - Title + muted meta: birth date · current age · engine version
   - Lens switcher: `Hybrid` (default) · `Age bands` · `Dasha chapters`
   - Chapter cards: title, age span, calendar years, current marker, summary, theme items, evidence `<details>`
2. Separator + existing “Deep reading” sections (unchanged)

Behavior:

- Lens is UI-only (all three arrays in payload). Optional `localStorage` key to remember last lens.
- If `lifeStory` is missing (older engine), hide Your Life; Deep reading still works.
- Visibility remains under `main[data-tab="reading"]`.

Visual language: Precision Ledger (navy / white / black + blue); no new card chrome beyond patterns already used in Reading.

## API

- Route unchanged: `GET /api/v1/charts/jobs/:jobId/reading`
- Additive field `reading.lifeStory`
- Existing `sections` length and keys unchanged (7 sections)
- FastAPI `POST /api/v1/charts/reading` and workspace artifact reads also include `lifeStory` via `build_reading()`

## Implementation sketch

| Piece | Location |
|-------|----------|
| Composer | `services/api-py/src/nakshatra_interpret/life_story.py` |
| Wire-in | `build_reading()` in `reading.py` |
| Export | `nakshatra_interpret/__init__.py` if needed |
| Bridge | `tools/build-reading.py` (passthrough) |
| Types + UI | `apps/web-practitioner/components/reading-panel.tsx` (+ small CSS in `globals.css` if needed) |
| Tests | `services/api-py/tests/test_life_story.py`; extend `test_reading.py`, API `reading.test.ts`, reading-panel test |

## Testing

| Layer | Assert |
|-------|--------|
| Python unit | 5 age-band chapters; dasha chapters cover MDs; hybrid length = 5; every item `evidence.length ≥ 1`; deterministic for fixed `now` |
| Golden (Raiganj) | MD overlaps in childhood/youth match known ages for the fixture |
| API | 7 sections still present; `lifeStory.lenses` has `hybrid`, `ageBands`, `dashaChapters` |
| UI | Hybrid default; evidence details render; missing `lifeStory` does not break panel |

## Error handling

- `lifeStory` is built inside the same `build_reading()` call as `sections`. If the Python process exits non-zero, keep today’s behavior: Fastify returns `reading_engine_unavailable` / `reading_venv_missing` - no partial payload.
- No soft-fail that returns Deep reading without `lifeStory` in v1 (avoids silent degradation). A later revision may soft-fail if needed for rollout.

## Success criteria

- Opening Reading on a completed chart shows Your Life with Hybrid chapters that name real mahadashas and cite evidence.
- Switching to Age bands / Dasha chapters changes presentation without a new network call.
- Deep reading sections remain intact and tested.
- No LLM dependency in the path.

## Future (out of scope)

- Top-level **Your Life** chart tab consuming the same `lifeStory`.
- Optional LLM tone polish behind a hard claim-validator.
- Transit annotations inside chapters.
- PDF report chapter export.
