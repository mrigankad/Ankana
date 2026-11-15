import { describe, expect, it } from "vitest";

import fixture from "../fixtures/depth.generated.json";
import { HI_DEPTH } from "../i18n/hi-depth";
import { translate } from "../i18n/translate";
import type { AshtakavargaDepth, DashasDepth, PlanetsDepth } from "./depth";
import { applyAsOf, ashtakavargaView, dashaDate, dashaRows, planetViews, runningKeys, spanText, type T } from "./depth-views";

const en: T = (s, p) => (p ? s.replace(/\{(\w+)\}/g, (m, k: string) => (k in p ? String(p[k]) : m)) : s);
const hi: T = (s, p) => translate("hi", s, p);
const planets = fixture.planets as unknown as PlanetsDepth;
const ashtak = fixture.ashtakavarga as unknown as AshtakavargaDepth;
const vim = fixture.dashas.vimshottari as unknown as DashasDepth;
const yog = fixture.dashas.yogini as unknown as DashasDepth;

describe("planetViews", () => {
  const views = planetViews(planets, en);
  const by = Object.fromEntries(views.map((v) => [v.planet, v]));

  it("covers nine grahas with every fact opening a proof", () => {
    expect(views).toHaveLength(9);
    for (const v of views) {
      for (const f of Object.values(v.facts)) {
        expect(f.proof.title).toContain(v.name);
        expect(f.proof.rule.length).toBeGreaterThan(20);
        expect(f.proof.source).toBeTruthy();
        expect(f.proof.inputs.length).toBeGreaterThan(0);
      }
    }
  });

  it("formats nakshatra, pada, lords and house lordships", () => {
    const moon = by.moon!;
    expect(moon.facts.nakshatra.text).toBe("Magha");
    expect(moon.facts.nakshatraLord.text).toBe("Ketu");
    expect(moon.facts.avastha.text).toBe("Bala");
    expect(moon.facts.pada.text).toMatch(/^pada [1-4]$/);
    expect(moon.facts.lordships.text).toMatch(/^(H\d+ ?)+$/);
    const sun = by.sun!;
    expect(sun.degree).toMatch(/^\d+°\d{2}′$/);
  });

  it("shows nodes as retrograde with no avastha or karaka", () => {
    const rahu = by.rahu!;
    expect(rahu.facts.retrograde.text).toBe("Retrograde");
    expect(rahu.facts.avastha.text).toBe("Not assigned");
    expect(rahu.facts.karaka.text).toBe("Not assigned");
    expect(rahu.facts.combust.text).toBe("Not tested");
  });

  it("puts combustion orb and separation in the proof value", () => {
    const combust = views.filter((v) => v.facts.combust.tone === "bad");
    for (const v of combust) expect(v.facts.combust.proof.value).toMatch(/Combust, [\d.]+° of \d+°/);
  });

  it("translates facts and proofs into Hindi", () => {
    const hv = planetViews(planets, hi);
    const sun = hv.find((v) => v.planet === "sun")!;
    expect(sun.name).toBe("सूर्य");
    expect(sun.facts.avastha.proof.rule).toMatch(/[ऀ-ॿ]/);
    expect(sun.facts.avastha.proof.inputs[0]!.label).toMatch(/[ऀ-ॿ]/);
    expect(sun.facts.karaka.proof.source).toMatch(/[ऀ-ॿ]/);
  });
});

describe("ashtakavargaView", () => {
  const v = ashtakavargaView(ashtak, en);
  const sarva = v.rows.at(-1)!;

  it("builds seven bhinna rows and the sarva row, twelve columns each", () => {
    expect(v.rows).toHaveLength(8);
    expect(v.columns).toHaveLength(12);
    for (const r of v.rows) expect(r.cells).toHaveLength(12);
    expect(sarva.isSarva).toBe(true);
    expect(sarva.total).toBe(337);
    expect(v.columns.filter((c) => c.isLagna)).toHaveLength(1);
    expect(v.columns.find((c) => c.isLagna)!.house).toBe(1);
  });

  it("highlights sarva at 28 or more and 25 or fewer", () => {
    for (const c of sarva.cells) {
      expect(c.tone).toBe(c.value >= 28 ? "high" : c.value <= 25 ? "low" : "mid");
    }
    expect(v.strongest.every((s) => s.value >= 28)).toBe(true);
    expect(v.weakest.every((s) => s.value <= 25)).toBe(true);
  });

  it("totals agree with the cells and the proof lists the contributors", () => {
    for (const r of v.rows.slice(0, 7)) expect(r.cells.reduce((a, c) => a + c.value, 0)).toBe(r.total);
    const cell = v.rows[0]!.cells.find((c) => c.value > 0)!;
    // one proof input per contributor that gave a bindu, plus the "giving none" line
    expect(cell.proof.inputs).toHaveLength(cell.value + 1);
    expect(sarva.cells[0]!.proof.inputs).toHaveLength(7);
  });
});

describe("dashas", () => {
  const now = new Date("2026-11-15T00:00:00Z");

  it("marks exactly one running period per level for Vimshottari", () => {
    const nodes = applyAsOf(vim.mahadashas, now);
    expect(nodes.filter((n) => n.state === "current")).toHaveLength(1);
    expect(runningKeys(nodes)).toHaveLength(3);
  });

  it("re-marks the period against the clock, whatever the stamp", () => {
    const early = applyAsOf(vim.mahadashas, new Date(vim.mahadashas[0]!.start));
    expect(early[0]!.state).toBe("current");
    expect(runningKeys(early)[0]).toBe("0");
  });

  it("yogini stops at antardasha", () => {
    const nodes = applyAsOf(yog.mahadashas, now);
    expect(runningKeys(nodes)).toHaveLength(2);
    const rows = dashaRows({ ...yog, mahadashas: nodes }, new Set(runningKeys(nodes)), en, "Asia/Kolkata");
    expect(Math.max(...rows.map((r) => r.level))).toBe(1);
    expect(rows[0]!.label).toMatch(/\(\w+\)$/);
  });

  it("shows rows for open nodes only and keeps dates exact", () => {
    const nodes = applyAsOf(vim.mahadashas, now);
    const marked = { ...vim, mahadashas: nodes };
    const closed = dashaRows(marked, new Set(), en);
    expect(closed).toHaveLength(9);
    const open = dashaRows(marked, new Set(runningKeys(nodes)), en, "Asia/Kolkata");
    expect(open.length).toBe(9 + 9 + 9);
    expect(open.filter((r) => r.state === "current")).toHaveLength(3);
    expect(open.find((r) => r.level === 2)!.range).toMatch(/^\d{1,2} \w{3} \d{4} to \d{1,2} \w{3} \d{4}$/);
    const maha = open.find((r) => r.level === 0 && r.state === "current")!;
    expect(maha.proof.inputs.map((i) => i.label)).toContain("Balance of the first period at birth (years)");
    const antar = open.find((r) => r.level === 1)!;
    expect(antar.proof.inputs.find((i) => i.label === "Length")!.value).toMatch(/^[\d.]+ × \d+ ÷ 120 = [\d.]+ years$/);
  });

  it("formats dates in the chart time zone and spans readably", () => {
    expect(dashaDate("2026-03-14T20:00:00Z", "Asia/Kolkata")).toBe("15 Mar 2026");
    expect(dashaDate("2026-03-14T20:00:00Z", "UTC")).toBe("14 Mar 2026");
    expect(spanText(7, en)).toBe("7 yr");
    expect(spanText(2.33, en)).toBe("2 yr 4 mo");
    expect(spanText(0.25, en)).toBe("3 mo");
    expect(spanText(0.01, en)).toBe("4 days");
  });
});

describe("Hindi dictionary", () => {
  it("has no en or em dashes in copy", () => {
    for (const [k, v] of Object.entries(HI_DEPTH)) {
      expect(k + v).not.toMatch(/[–—]/);
    }
  });
});
