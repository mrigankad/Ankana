# Nakshatra - Remaining Slices Handoff Plan

> **For agentic workers (Codex / Antigravity / Claude):** Execute slices in
> order; each slice is independently shippable. Within a slice, follow TDD:
> write the failing test, run it, implement, run again, commit. Never mark a
> step done without running the stated command and seeing it pass.

**Repo:** pnpm monorepo. `packages/astrology-core` (deterministic engine),
`apps/api` (Fastify + Prisma/SQLite), `apps/web-practitioner` (Next.js 16).
Run everything from repo root.

**Commands:**
- All tests: `pnpm -r test` (88 passing at handoff)
- Typecheck: `pnpm -r lint`
- E2E: `pnpm exec playwright test` (dev servers auto-start; reuse running ones)
- Dev: `pnpm dev` (web :3000, api :3001)

## Global constraints (apply to every slice)

1. **Deterministic before generative.** No LLM output ever becomes a chart
   fact, strength value, date, or rule outcome. LLM (Slice 7 only) narrates
   and cites computed data.
2. **Evidence by default.** Every rule/yoga/prediction/remedy result carries
   `evidence: string[]` referencing concrete placements, and a
   `confidence` derived from rule coverage + strength values - never model
   self-confidence.
3. **Design system.** All UI uses the tokens in
   `apps/web-practitioner/app/globals.css` (navy `#162A6C`, gold `#D4A017`,
   midnight `#0B1220`, Cinzel headings, Manrope body, JetBrains Mono for all
   numbers/dates/degrees). No new colors, no new fonts, no Tailwind.
4. **Safe advisory posture.** Remedies and health/legal/finance adjacent
   text must include cautions; gemstone recommendations must be gated (see
   Slice 5).
5. **Tests accompany code in the same commit.** Golden astronomical values
   get tolerance-based assertions (state the tolerance in the test).

## Repo gotchas (read before coding)

- `astronomy-engine` is CJS. Import it exactly like
  `packages/astrology-core/src/ephemeris.ts` does (namespace import +
  `default ??` unwrap), or Node ESM (`tsx`) crashes at runtime while vitest
  passes.
- pnpm 10 blocks native build scripts. `better-sqlite3` binding already
  built; if node_modules is wiped, rebuild via
  `cd node_modules/.pnpm/better-sqlite3*/node_modules/better-sqlite3 && npx --yes prebuild-install`.
- Prisma refuses `--force-reset` from agents. The vitest global setup
  (`apps/api/vitest.global-setup.ts`) deletes `test.db` then runs plain
  `prisma db push` - keep that pattern.
- Next dev only allows `localhost` unless listed; `next.config.ts` already
  sets `allowedDevOrigins: ["127.0.0.1"]` and `turbopack.root`. If you see
  "module not found in React Client Manifest", delete
  `apps/web-practitioner/.next` and restart.
- Windows shell: prefer POSIX bash; `/tmp` does not exist.

---

## Slice 1 - Transit engine

**Goal:** For any chart + date, compute the transit snapshot and a multi-year
transit timeline, and show them on the chart page.

**Files:**
- Create `packages/astrology-core/src/transits.ts` + `transits.test.ts`
- Modify `packages/astrology-core/src/index.ts` (exports)
- Modify `apps/api/src/modules/chart-requests/routes.ts` (new endpoint)
- Create `apps/web-practitioner/components/transit-panel.tsx` + test
- Modify `apps/web-practitioner/components/chart-artifact-view.tsx`

**Interfaces (produce exactly these):**
```ts
export interface TransitSnapshot {
  date: string; // ISO
  planets: Array<{
    planet: Planet;
    siderealLongitude: number;
    signIndex: number;
    signName: string;
    retrograde: boolean;
    houseFromLagna: number; // whole-sign house in the natal chart
    houseFromMoon: number;
    nakshatra: string;
  }>;
  sadeSati: { active: boolean; phase: "rising" | "peak" | "setting" | null; evidence: string[] };
  jupiterSummary: { signName: string; houseFromMoon: number; evidence: string[] };
  nodesSummary: { rahuSign: string; ketuSign: string; houseFromLagna: number; evidence: string[] };
}

export interface TransitEvent {
  date: string;
  planet: Planet;
  kind: "ingress" | "retrograde-station" | "direct-station";
  detail: string; // e.g. "Saturn enters Pisces"
}

export function computeTransitSnapshot(natal: VedicChartArtifact, date: Date): TransitSnapshot;
export function computeTransitTimeline(natal: VedicChartArtifact, from: Date, years: number): TransitEvent[];
```

**Implementation notes:**
- Reuse `tropicalLongitude` / `toSidereal` / `isRetrograde` from the engine.
- Sade-sati: Saturn's sidereal sign within 12th, 1st, or 2nd from natal Moon
  sign → phases rising/peak/setting respectively.
- Timeline: sample each planet's sidereal longitude daily (Moon: skip; too
  noisy - exclude Moon from timeline, include in snapshot). Detect sign
  ingress when `floor(lon/30)` changes; detect stations when direction
  flips. Bisect to the day. Cap: Sun..Saturn + mean nodes over `years ≤ 5`.
- API: `GET /api/v1/charts/jobs/:jobId/transits?date=YYYY-MM-DD&years=2`
  → `{ snapshot, timeline }`, 404 if job/artifact missing.
- UI: `TransitPanel` card after Vimshottari section: snapshot table
  (planet, transit sign, house from lagna/Moon, retro badge), sade-sati
  banner when active (gold badge), and a vertical event list (mono dates).

**Tests (must include):**
- Saturn's sidereal sign on 2026-07-09 equals the known value (compute once
  with the engine, assert sign name - self-consistency plus a hand-checked
  golden: Saturn tropical ≈ Pisces in 2026 → sidereal Aquarius/Pisces
  boundary; assert with the engine and tolerance on longitude instead of
  guessing).
- Sade-sati active iff Saturn house-from-Moon ∈ {12,1,2} (construct
  synthetic natal artifacts).
- Timeline events are chronologically ordered, each ingress date's
  before/after signs differ.
- API integration test through Fastify `inject`.

**Commit:** `feat(astrology-core): transit snapshot and timeline` +
`feat(api,web): transit endpoint and panel`.

---

## Slice 2 - Strength engines

**Goal:** Shadbala, Ashtakavarga, Sarvashtakavarga, Vimshopaka; surfaced in
the artifact and UI.

**Files:**
- Create `packages/astrology-core/src/shadbala.ts`, `ashtakavarga.ts`,
  `vimshopaka.ts` + tests
- Modify `chart.ts` to add `strengthMetrics` to `VedicChartArtifact`
- Modify UI planet table: add "Strength" column (Shadbala in rupas +
  required-minimum ratio badge)

**Interfaces:**
```ts
export interface ShadbalaResult {
  planet: Planet;
  sthana: number; dig: number; kala: number;
  cheshta: number; naisargika: number; drik: number;
  totalRupas: number; requiredRupas: number; ratio: number;
}
export interface AshtakavargaResult {
  planet: Planet; // Sun..Saturn
  bindusBySign: number[]; // length 12
}
export interface StrengthMetrics {
  shadbala: ShadbalaResult[];
  ashtakavarga: AshtakavargaResult[];
  sarvashtakavarga: number[]; // length 12, sums
  vimshopaka: Array<{ planet: Planet; score: number }>; // 0-20
}
```

**Implementation notes:**
- Follow standard BPHS formulas. Where a sub-bala needs data we don't have
  (e.g. exact war between planets), document the simplification in a code
  comment and keep the term at its neutral value.
- Ashtakavarga benefic-point tables are fixed matrices - transcribe from
  BPHS (57 total bindus per planet check: Sun 48, Moon 49, Mars 39,
  Mercury 54, Jupiter 56, Venus 52, Saturn 39; total SAV = 337).
- Tests: SAV total equals 337 for any chart; each planet's bindu total
  matches the classical count; Shadbala ratios positive; a golden chart's
  strongest planet is stable across runs.

---

## Slice 3 - Additional dasha systems

**Goal:** Yogini, Ashtottari, Kalachakra, Chara behind the existing
`DashaPeriod` shape; UI switcher.

**Files:** `packages/astrology-core/src/dasha-yogini.ts`, `dasha-ashtottari.ts`,
`dasha-kalachakra.ts`, `dasha-chara.ts` + tests; artifact gains
`dashas: { vimshottari, yogini, ashtottari, kalachakra?, chara? }`
(keep `vimshottari` field for backward compat; UI + API read `dashas`).

**Notes:** Yogini: 8 yoginis, 36-year cycle, start from Moon nakshatra
(index+3) mod 8 rule. Ashtottari: 108 years, applicability rule (Rahu in
kendra/trikona from lagna lord) - compute always, flag `applicable`.
Kalachakra/Chara are complex: acceptable to ship Chara (Jaimini, sign-based,
fixed 12-sign order with years from sign-lord positions) and defer
Kalachakra with an explicit `not-implemented` marker if the formulas can't
be validated against two independent references - do NOT ship unvalidated
math silently.

**UI:** segmented control (navy pills) above the dasha section:
Vimshottari · Yogini · Ashtottari · Chara.

---

## Slice 4 - Rule engine + predictions (`packages/rule-engine`)

**Goal:** Declarative, versioned rule packs producing dated, evidenced,
confidence-scored predictions.

**Files:**
- Create `packages/rule-engine/` (package.json, tsconfig, src/)
- `src/types.ts`, `src/evaluator.ts`, `src/packs/vedic-yogas.ts`,
  `src/packs/vedic-predictions.ts`, tests per file
- API: `POST /api/v1/charts/jobs/:jobId/predictions` (or computed with the
  artifact and stored alongside)
- UI: `PredictionTimeline` component: horizon tabs (Month / Quarter / Year /
  5 Years / Lifetime), domain filter chips (Career, Wealth, Marriage,
  Health, Education, Travel, Spiritual)

**Interfaces:**
```ts
export interface RuleCondition { /* discriminated union:
  planetInHouse, planetInSign, planetDignity, houseLordIn, aspectBetween,
  dashaLordIs, transitInHouse, strengthAtLeast, yogaPresent */ }
export interface Rule {
  id: string; packVersion: string; domain: Domain;
  when: RuleCondition[];           // AND of conditions
  weight: number;                  // contribution to confidence
  effect: "supportive" | "challenging";
  text: string;                    // template with {placeholders}
}
export interface Prediction {
  domain: Domain;
  window: { start: string; end: string };
  headline: string; narrative: string;
  effect: "supportive" | "challenging" | "mixed";
  confidence: number;              // 0-1, from matched-rule weights × strength ratios
  evidence: string[];              // every matched condition, human-readable
  ruleIds: string[];
}
```

**Evaluator contract:** pure function
`evaluate(artifact, strengths, transits, dashas, horizon) → Prediction[]`.
Windows come from dasha period boundaries intersected with major transit
windows. Confidence = normalized sum of matched rule weights, scaled by the
mean Shadbala ratio of the implicated planets, capped 0.95, floored 0.05.
NO free-text generation here - `narrative` is template substitution only.

**Seed content:** ≥40 yoga/dosha rules (include: Neecha Bhanga Raj Yoga,
Vipreet Raj (Harsha/Sarala/Vimala), Dhan yogas, Manglik with cancellation
rules, Pitra dosha, Grahan yoga, Guru Chandal, Daridra) and ≥30 prediction
rules covering all domains. Every rule cites its classical source in a
`source` field (e.g. "BPHS ch. 41").

---

## Slice 5 - Remedies engine

**Goal:** Rule-driven remedies with mandatory cautions.

**Files:** `packages/rule-engine/src/packs/vedic-remedies.ts` + evaluator
extension + UI `RemedyList` card.

**Interface:**
```ts
export interface Remedy {
  kind: "mantra" | "daan" | "fasting" | "puja" | "rudraksha" | "gemstone" | "lifestyle";
  planet: Planet; title: string; practice: string;
  rationale: string; evidence: string[];
  strengthOfRecommendation: "strong" | "moderate" | "optional";
  cautions: string[]; // NEVER empty for gemstone/rudraksha
}
```
**Gemstone gate (hard rule, test it):** only recommend a planet's gemstone
when the planet is a functional benefic for the lagna AND its Shadbala
ratio < 1 AND it is not combust/debilitated without cancellation; otherwise
emit the mantra/daan alternative. UI renders cautions in a warning style
(existing `--warning` token) and a standing disclaimer.

---

## Slice 6 - Practitioner workspace UI

**Goal:** Make the stored data navigable.

**Files:**
- API: `GET /api/v1/clients` (list, workspace-scoped),
  `GET /api/v1/clients/:id` (with birth records + chart requests)
- Web: `app/clients/page.tsx` (table: name, latest chart, created; row
  click → detail), `app/clients/[clientId]/page.tsx` (profile, birth data,
  chart history list with "Open chart" links, "New chart" action),
  nav link "Clients"
- South-Indian chart toggle in `KundaliChart` (`variant="north" | "south"`;
  south = fixed 4×4 grid with signs in fixed cells, houses counted from
  lagna cell)

**E2E:** extend the Playwright spec: after generating a chart, navigate to
Clients, open the client, open the chart from history.

---

## Slice 7 - AI assistant (Ollama)

See the companion plan: `docs/superpowers/plans/2026-07-09-ai-assistant-plan.md`.
Build only after Slice 4 exists (the assistant cites rule outputs).
The operator has **Ollama Pro** (cloud). Key goes in `apps/api/.env` as
`OLLAMA_API_KEY`; never commit it, never log it.

---

## Slice 8 - PDF reports

**Goal:** Branded report PDF from existing components.

**Approach:** `apps/web-practitioner/app/reports/[jobId]/print/page.tsx` -
a print-optimized page (white background, no nav, page-break CSS) rendering
chart + kundali + dashas + yogas + predictions + remedies; API endpoint
`POST /api/v1/reports/:jobId` runs Playwright chromium `page.pdf()` against
that route and stores the PDF (new Prisma model `Report`, file on disk under
`apps/api/storage/reports/`). UI: "Download PDF report" gold button on the
chart page. Test: PDF file is created, >50KB, starts with `%PDF`.

---

## Slice 9 - Hardening

- Auth: email+password with session cookies (lucia or hand-rolled +
  argon2), `Workspace` + `Membership` Prisma models, all queries
  workspace-scoped (replace hardcoded `ws_1`).
- Worker: move chart computation to `apps/worker` polling a `jobs` table;
  API returns `queued` and the UI polls the status URL (it already handles
  `completed`/`failed`).
- Audit: `AuditEvent` model; emit on client create/read, chart generate,
  report render, assistant query.
- CI: GitHub Actions - pnpm install, `pnpm -r lint`, `pnpm -r test`,
  Playwright with `LOCATION_PROVIDER=static`.
- Postgres: keep SQLite default; add `DATABASE_URL` postgres support via
  Prisma provider switch documented in `docs/deployment-strategy.md`.

## Definition of done (every slice)

1. `pnpm -r lint` and `pnpm -r test` pass.
2. New behavior has tests written before implementation.
3. UI changes screenshot-verified in a real browser at 1280px and 390px.
4. Playwright e2e still passes.
5. Conventional commit(s) pushed per task, not one mega-commit.
