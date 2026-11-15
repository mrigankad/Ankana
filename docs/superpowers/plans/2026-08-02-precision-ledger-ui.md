# Precision Ledger UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Ship the Precision ledger visual system across web-practitioner: unify tokens, finish chart workspace, align clients/intake, retire gold leftovers.

**Tech:** Next.js app `apps/web-practitioner`, Tailwind v4 + `globals.css` tokens, shadcn where already used.

**Design:** `docs/superpowers/specs/2026-08-02-precision-ledger-design.md`

---

### Task 1: Unify tokens + page ground

**Files:** `apps/web-practitioner/app/globals.css`

- [x] Set `--bg-main` / `--background` to cool ledger ground `#f4f6fb`
- [x] Point all active `var(--gold*)` selectors to navy equivalents
- [x] Make `.nk-btn-gold` / `.nk-badge-gold` thin aliases of navy primary styles
- [x] Soften `.nk-card` to hairline border + minimal shadow (ledger panel)

**Verify:** Hard-refresh `/` - page ground cool white-blue; no warm cream cast.

---

### Task 2: Chart workspace chrome

**Files:**
- `apps/web-practitioner/app/charts/[jobId]/page.tsx`
- `apps/web-practitioner/components/chart-artifact-view.tsx`
- `apps/web-practitioner/app/globals.css` (`.nk-cosmic`, section spacing, tabs)

- [x] Chart page header: quieter title row, primary PDF button stays navy
- [x] Tabs: ledger strip on white, clear active state (already navy - refine spacing)
- [x] Birth banner (`.nk-cosmic`): less “hero gradient”, more structured ledger header
- [x] Panel titles consistent; reduce stacked card noise

**Verify:** Open any completed chart - overview reads as one calm workspace.

---

### Task 3: Clients + intake

**Files:**
- `apps/web-practitioner/app/clients/page.tsx`
- `apps/web-practitioner/app/clients/[clientId]/page.tsx`
- `apps/web-practitioner/components/client-intake-form.tsx`
- `apps/web-practitioner/app/clients/new/page.tsx` (if needed)

- [x] Page heads match dashboard spacing/type
- [x] Client cards use ledger panel language (white, hairline)
- [x] Intake form card + primary CTA navy (already partially done)

**Verify:** `/clients` and `/clients/new` feel same system as dashboard.

---

### Task 4: Retire gold naming in TSX

**Files:** grep `nk-btn-gold|nk-badge-gold|bg-gold` under `apps/web-practitioner`

- [x] Replace remaining class names with `nk-btn-primary` / `nk-badge-navy` or shadcn
- [x] Leave CSS aliases only if needed for print CSS; comment as deprecated

**Verify:** `rg "nk-btn-gold|nk-badge-gold" apps/web-practitioner --glob '*.tsx'` empty.

---

### Task 5: Smoke

- [x] `pnpm --filter @astro/web-practitioner lint`
- [ ] Spot-check `/`, `/clients`, one chart URL in browser
