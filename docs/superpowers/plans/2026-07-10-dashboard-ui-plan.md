# Nakshatra - End-to-End Dashboard UI Plan

> **For agentic workers:** execute phases in order; each phase ships a
> usable UI. Keep the Nakshatra tokens (navy #162A6C, gold #D4A017,
> midnight #0B1220, off-white #FAFAF7, Google Sans / Inter / JetBrains
> Mono, lucide icons). All existing tests must stay green; add tests per
> component as specified.

## Design direction

Pinterest-dashboard inspiration, translated to our brand: **visual-first
masonry boards of insight cards** instead of long single-column pages.
Every card is a self-contained "pin": one insight, one visual anchor
(kundali thumbnail, dasha bar, confidence meter, transit glyph), scannable
in two seconds, expandable for evidence. Density comes from the grid;
calm comes from the palette. The celestial gradient stays reserved for
page heroes and the current-period highlights.

## Component library - recommendation

**Adopt shadcn/ui (Radix primitives + Tailwind CSS v4) plus Recharts for
data visuals.** Rationale:

- shadcn gives accessible, unstyled-by-default primitives we currently
  lack and will need for a real dashboard: `Command` (⌘K palette),
  `Dialog`, `Sheet` (mobile panels), `Tabs`, `DropdownMenu`, `Tooltip`,
  `Popover` (citation cards), `Toast`. We keep full visual control - the
  components are copied into the repo and themed with our existing CSS
  variables (Tailwind v4 reads CSS custom properties natively, so the
  Nakshatra token block migrates as-is).
- lucide is already shadcn's icon convention - zero churn.
- Recharts for the dasha timeline, strength bars, and SAV heat strip -
  replaces hand-rolled divs where interactivity (hover values, brushing)
  earns it. SVG kundali stays custom.
- Cost: introducing Tailwind (build config + class migration as pages are
  touched). Mitigation: migrate per page in phases below; old `nk-*`
  classes coexist until each page is converted. No runtime dependency
  risk - shadcn code lives in our tree.

Alternative if Tailwind is rejected: Radix primitives alone + current
hand-rolled CSS (keeps everything, loses velocity). Decision made 2026-07-10: shadcn + Tremor + Recharts approved by the user.

## Information architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ Sidebar (collapsible, midnight bg)      Topbar: ⌘K search · ws · ⚙ │
│  ✦ Nakshatra                                                       │
│  ◈ Dashboard        /                                              │
│  ◈ Clients          /clients                                       │
│  ◈ Charts           /charts (index of computed charts)             │
│  ◈ Panchang today   /panchang                                      │
│  ◈ Audit log        /audit                                         │
│  ─ New chart (gold CTA)                                            │
└────────────────────────────────────────────────────────────────────┘
```

### 1. `/` - Dashboard home (the "board")
- **Today strip** (full-width, cosmic band, thin): today's tithi ·
  nakshatra · vara · next transit event countdown - all computed live
  from a `GET /api/v1/panchang/today?lat=&lon=` endpoint (new, thin
  wrapper over the engine).
- **KPI tiles** (4-up): Clients · Charts computed · Clients in sade sati
  · Reports generated. Mono numerals, gold accent on deltas. Backed by a
  new `GET /api/v1/dashboard/summary` endpoint.
- **Masonry board** (2–3 CSS columns): recent client cards (lagna glyph,
  current MD badge, last chart date), upcoming transit events card,
  latest predictions card (top-confidence windows across clients),
  recent audit activity card.
- Empty state for a fresh workspace: the gold constellation spot
  illustration (docs/assets/prompts/prompts.md asset 4) + "Start your first chart".

### 2. `/clients` - Client board
- Default **card grid** (Pinterest feel): each card = client name, lagna
  sign glyph + kundali micro-thumbnail (reuse `KundaliChart` at 96px),
  current mahadasha chip, sade-sati indicator, last activity. Hover lift.
- Toggle to the existing table (kept). Search-as-you-type filter box.

### 3. `/clients/[id]` - Client hub
- Header: name, birth data line, current MD/AD chips, actions (New
  chart, Download latest report).
- shadcn `Tabs`: **Overview** (latest chart summary card + prediction
  highlights) · **Charts** (history) · **Predictions** · **Remedies** ·
  **Notes** (new `ClientNote` model: free text, timestamped - the only
  new schema in this plan).

### 4. `/charts/[jobId]` - Chart workspace (rework of current page)
Three-zone desktop layout replacing today's single column:
```
┌──────────┬──────────────────────────────┬───────────────┐
│ LEFT RAIL│  ANALYSIS BOARD (masonry)    │ ASSISTANT DOCK│
│ sticky   │  panchang · planets table    │ (collapsible, │
│ kundali  │  dasha timeline (Recharts)   │  full chat    │
│ + lagna  │  yogas board · strengths     │  thread,      │
│ facts +  │  vargas · predictions ·      │  citation     │
│ section  │  remedies · transits         │  chips jump   │
│ anchors  │  (2-col masonry ≥1280px)     │  to cards)    │
└──────────┴──────────────────────────────┴───────────────┘
```
- Left rail replaces the sticky pill nav; kundali always visible.
- Assistant dock replaces the bottom card; opens via floating gold ✦.
- Below 1100px: rail collapses to the pill nav, assistant becomes a
  `Sheet`.

### 5. `/panchang` - Today page
Full panchang for the practitioner's location (geolocate or saved
default), hora table, day's transit events. Pure engine reuse.

### 6. `/audit` - Audit log
Table over `GET /api/v1/audit-events` with action filter chips.

### 7. Global: ⌘K command palette
shadcn `Command`: search clients (name), jump to charts, "New chart",
"Panchang today". Data from existing list endpoints.

## Phases (each independently shippable)

**Phase 0 - Foundation (decision gate: Tailwind yes/no)**
Install Tailwind v4 + shadcn init; map Nakshatra tokens into
`@theme`; add sidebar + topbar app shell (`components/app-shell.tsx`),
⌘K palette. Existing pages render unchanged inside the new shell.
Test: shell renders nav landmarks; palette opens with mock data.

**Phase 1 - Dashboard home**
`GET /api/v1/dashboard/summary` + `GET /api/v1/panchang/today` (API
tests), KPI tiles, today strip, masonry board with recent clients +
transit feed. Component tests for tiles with fixture data.

**Phase 2 - Clients board + client hub tabs**
Card grid with kundali micro-thumbnails, table toggle, search;
`ClientNote` model + notes tab (Prisma migration + API tests).

**Phase 3 - Chart workspace rework**
Three-zone layout, Recharts dasha timeline (keep `<details>` fallback
for print), assistant dock. Update e2e to click through the new layout.
Print route (`/charts/[id]/print`) keeps the current single-column flow.

**Phase 4 - Panchang today + audit pages + polish**
Responsive audit at 390px, focus-visible sweep, reduced-motion audit,
Lighthouse pass ≥90 accessibility on all pages.

## Definition of done (every phase)
`pnpm -r lint` + `pnpm -r test` + `pnpm exec playwright test` green;
browser screenshots at 1440px and 390px reviewed; no regression to the
PDF print route.
