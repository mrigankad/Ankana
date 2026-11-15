import { computeVedicChartArtifact } from "@astro/astrology-core";
import { describe, expect, it } from "vitest";

import {
  dataCoverage,
  detectMasnui,
  detectRin,
  lalKitabReport,
  lkAspects,
  lkChart,
  lkChartFromHouses,
  remedies,
  sleepingHouses,
  sleepingPlanets,
  varshphal,
  VARSHPHAL_MAX_AGE,
  yearOfLife,
} from "./index";
import {
  aspectRows,
  cycle35,
  dormantData,
  friendshipTables,
  masnuiData,
  pakkaGhar,
  planetHouseEntries,
  remedyDelivery,
  rinData,
  varshphalData,
} from "./data";

// Ananya Sharma, 15 Mar 1995 06:42, Varanasi (demo chart).
const artifact = computeVedicChartArtifact({
  birthDate: "1995-03-15",
  birthTime: "06:42",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

describe("lkChart (demo chart: Ananya Sharma)", () => {
  const chart = lkChart(artifact);

  it("uses the ascendant as house 1 by default", () => {
    expect(artifact.ascendant.signName).toBe("Pisces");
    expect(chart.origin).toBe("lagna_h1");
    expect(chart.houses[1]).toEqual(["sun"]);
    // house numbers agree with astrology-core whole-sign houses
    for (const p of artifact.planets) {
      expect(chart.planetHouse[p.planet]).toBe(p.house);
    }
    // placements derived from astrology-core for this chart
    expect(chart.planetHouse).toMatchObject({
      sun: 1,
      ketu: 2,
      mars: 5,
      moon: 6,
      rahu: 8,
      jupiter: 9,
      venus: 11,
      mercury: 12,
      saturn: 12,
    });
  });

  it("supports aries_h1 as an option", () => {
    const aries = lkChart(artifact, { origin: "aries_h1" });
    expect(aries.origin).toBe("aries_h1");
    // Sun in Pisces is sign 12 counted from Aries
    expect(aries.planetHouse.sun).toBe(12);
    expect(aries.planetHouse.ketu).toBe(1); // Ketu in Aries
  });

  it("finds dormant planets and houses with citations", () => {
    const sp = sleepingPlanets(chart);
    const by = Object.fromEntries(sp.map((s) => [s.planet, s]));
    expect(by.sun.status).toBe("awake");
    expect(by.sun.rule).toBe("own_pakka_ghar");
    expect(by.jupiter.status).toBe("awake");
    expect(by.venus.status).toBe("dormant"); // H11 unaspected (H3 empty)
    expect(by.venus.awakener).toBe("jupiter");
    expect(by.ketu.status).toBe("dormant"); // H10 empty -> H2 dormant
    expect(by.ketu.rule).toBe("h10_empty_h2");
    expect(by.ketu.awakener).toBe("moon");
    for (const s of sp) expect(s.cite.pdf_page).toBeGreaterThan(0);

    const dormantHouses = sleepingHouses(chart)
      .filter((h) => h.status === "dormant")
      .map((h) => h.house);
    expect(dormantHouses).toEqual([3, 4, 10]);
  });

  it("computes aspects along the book arrows", () => {
    const asp = lkAspects(chart);
    // Mars H5 -> Jupiter H9 (50%).
    const marsToJupiter = asp.find((a) => a.from.planet === "mars" && a.to.planet === "jupiter");
    expect(marsToJupiter?.strength).toBe(50);
    // Rahu H8 -> Ketu H2 (25%, inverse aspect).
    const rahuToKetu = asp.find((a) => a.from.planet === "rahu" && a.to.planet === "ketu");
    expect(rahuToKetu?.strength).toBe(25);
    // Ketu H2 -> Moon H6 (25%).
    expect(asp.find((a) => a.from.planet === "ketu" && a.to.planet === "moon")?.strength).toBe(25);
  });

  it("flags rin with first-degree father debt (Jupiter H9, Mercury H12)", () => {
    const rin = detectRin(chart);
    expect(rin.some((r) => r.id === "pitri_rin_first_degree" && r.planet === "jupiter")).toBe(true);
    expect(rin.every((r) => r.cite.pdf_page! > 0 && typeof r.needs_review === "boolean")).toBe(true);
  });

  it("returns no masnui for this chart", () => {
    expect(detectMasnui(chart)).toEqual([]);
  });
});

describe("rin table detection", () => {
  it("fires on planet in placement house with a listed enemy", () => {
    // Moon in 4 with Ketu -> debt to mother
    const c = lkChartFromHouses({ moon: 4, ketu: 4, sun: 1 });
    const hit = detectRin(c).find((r) => r.id === "matri_rin");
    expect(hit?.basis).toBe("table");
    expect(hit?.with).toEqual(["ketu"]);
  });
  it("does not fire without the enemy planet", () => {
    const c = lkChartFromHouses({ moon: 4, sun: 1 });
    expect(detectRin(c).find((r) => r.id === "matri_rin")).toBeUndefined();
  });
});

describe("masnui detection", () => {
  it("detects artificial planets when both components share a house", () => {
    const c = lkChartFromHouses({ sun: 3, mercury: 3, saturn: 3 });
    const ids = detectMasnui(c).map((m) => m.id);
    expect(ids).toContain("masnui_mars_positive");
    expect(ids).toContain("masnui_mars_negative");
    expect(ids).toContain("masnui_rahu_debilitated");
  });
});

describe("varshphal matrix", () => {
  it("has 100 rows that are each a permutation of 1..12", () => {
    expect(varshphalData.rows).toHaveLength(100);
    expect(VARSHPHAL_MAX_AGE).toBe(100);
    varshphalData.rows.forEach((r, i) => {
      expect(r.age).toBe(i + 1);
      expect([...r.houses].sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    });
  });

  it("H1 column cycles 1,4,9,3,11,5,7,2,12,10,8,6 every 12 years", () => {
    const cycle = [1, 4, 9, 3, 11, 5, 7, 2, 12, 10, 8, 6];
    const h1 = varshphalData.rows.map((r) => r.houses[0]);
    for (let age = 1; age <= 100; age += 1) {
      expect(h1[age - 1]).toBe(cycle[(age - 1) % 12]);
    }
  });

  it("age 33: planets of H1 move to H12 and H2 stays H2 (book worked example)", () => {
    const c = lkChartFromHouses({ sun: 1, moon: 2, mars: 3 });
    const v = varshphal(c, 33);
    expect(v.row).toEqual([12, 2, 6, 10, 8, 3, 9, 1, 5, 7, 4, 11]);
    expect(v.planets.find((p) => p.planet === "sun")?.annualHouse).toBe(12);
    expect(v.planets.find((p) => p.planet === "moon")?.annualHouse).toBe(2);
    expect(v.annualChart.planetHouse.sun).toBe(12);
  });

  it("year 1 keeps H1 in H1, and months map from houses", () => {
    const c = lkChartFromHouses({ sun: 1 });
    const v = varshphal(c, 1);
    expect(v.planets[0].annualHouse).toBe(1);
    expect(v.planets[0].month).toBe("Vaisakh");
  });

  it("rejects ages outside the book matrix", () => {
    const c = lkChartFromHouses({ sun: 1 });
    expect(() => varshphal(c, 0)).toThrow(RangeError);
    expect(() => varshphal(c, 101)).toThrow(RangeError);
  });

  it("35-year cycle positions sum to 35 and map ages", () => {
    expect(cycle35.reduce((s, r) => s + r.years, 0)).toBe(35);
    const c = lkChartFromHouses({ sun: 1 });
    expect(varshphal(c, 1).cycle35).toMatchObject({
      rotation: 1,
      yearInCycle: 1,
      cyclePlanet: "jupiter",
      part: "beginning",
      partRuler: "ketu",
    });
    expect(varshphal(c, 36).cycle35).toMatchObject({ rotation: 2, yearInCycle: 1 });
    expect(varshphal(c, 35).cycle35.cyclePlanet).toBe("ketu");
  });

  it("derives the year of life from a birth date", () => {
    expect(yearOfLife("1995-03-15", new Date("2026-03-14T00:00:00Z"))).toBe(31);
    expect(yearOfLife("1995-03-15", new Date("2026-03-15T00:00:00Z"))).toBe(32);
  });
});

describe("remedies", () => {
  it("ranks upay with citations and the one-at-a-time rule", () => {
    const plan = remedies(lkChart(artifact));
    expect(plan.upay.length).toBeGreaterThan(0);
    expect(plan.upay[0].kind).toBe("rin");
    expect(plan.upay.map((u) => u.rank)).toEqual(plan.upay.map((_, i) => i + 1));
    expect(plan.oneAtATime.durationDays).toEqual([40, 43]);
    expect(plan.oneAtATime.cite.printed_page).toBe(133);
    // exactly one remedy per phase
    expect(plan.schedule).toHaveLength(plan.upay.length);
    expect(new Set(plan.schedule.map((s) => s.phase)).size).toBe(plan.schedule.length);
    for (const u of plan.upay) {
      expect(u.cites.length).toBeGreaterThan(0);
      expect(u.durationDays).toBe(43);
    }
    // sleeping-planet upay deliver by the house of the awakener planet (Jupiter in H9)
    const venusUpay = plan.upay.find((u) => u.kind === "sleeping_planet" && u.planet === "venus");
    expect(venusUpay?.delivery?.house).toBe(9);
    expect(venusUpay?.delivery?.method).toMatch(/temple/i);
  });

  it("matches planet-in-house entries (Sun H7 remedies when Saturn afflicts)", () => {
    const c = lkChartFromHouses({ sun: 7, venus: 7, saturn: 1 });
    const plan = remedies(c);
    expect(
      plan.upay.some((u) => u.kind === "house_entry" && u.planet === "sun" && /milk/i.test(u.action)),
    ).toBe(true);
  });

  it("report aggregates everything", () => {
    const r = lalKitabReport(artifact, { now: new Date("2026-11-14T00:00:00Z") });
    expect(r.origin).toBe("lagna_h1");
    expect(r.varshphal?.age).toBe(32);
    expect(r.varshphal?.row).toEqual([2, 7, 5, 11, 3, 12, 10, 6, 4, 1, 9, 8]);
    expect(r.coverage).toEqual({ planetHouseDone: 108, planetHouseTotal: 108 });
  });
});

describe("data tables", () => {
  const hasCite = (r: { cite: unknown; needs_review: boolean }) => {
    expect(typeof r.needs_review).toBe("boolean");
    const c = r.cite as Record<string, unknown>;
    for (const k of ["vol", "printed_page", "pdf_page", "section", "ocr_confidence"]) {
      expect(c).toHaveProperty(k);
    }
    expect(["I", "II"]).toContain(c.vol);
    expect(["high", "medium", "low"]).toContain(c.ocr_confidence);
  };

  it("every row carries cite + needs_review", () => {
    for (const r of pakkaGhar) hasCite(r);
    for (const r of aspectRows) hasCite(r);
    for (const r of dormantData.awakeners) hasCite(r);
    for (const r of dormantData.self_awakening) hasCite(r);
    for (const r of dormantData.rules) hasCite(r);
    for (const r of rinData.rows) hasCite(r);
    for (const r of masnuiData.rows) hasCite(r);
    for (const r of cycle35) hasCite(r);
    for (const r of remedyDelivery.rows) hasCite(r);
    for (const r of friendshipTables) hasCite(r);
    for (const r of planetHouseEntries) hasCite(r);
  });

  it("pakka ghar matches p.69", () => {
    const m = Object.fromEntries(pakkaGhar.map((r) => [r.planet, r.houses]));
    expect(m).toEqual({
      sun: [1],
      moon: [4],
      mars: [3, 8],
      mercury: [7],
      jupiter: [2, 5, 9, 11],
      venus: [7],
      saturn: [10, 8],
      rahu: [12],
      ketu: [6],
    });
  });

  it("awakening map and ages match pp.115-117", () => {
    expect(dormantData.awakeners.map((a) => a.planet)).toEqual([
      "mars", "moon", "mercury", "moon", "sun", "rahu", "venus", "moon", "jupiter", "saturn", "jupiter", "ketu",
    ]);
    expect(Object.fromEntries(dormantData.self_awakening.map((a) => [a.planet, a.age]))).toEqual({
      jupiter: 16, sun: 22, moon: 24, venus: 25, mars: 28, mercury: 34, saturn: 36, rahu: 42, ketu: 48,
    });
  });

  it("has 9 rin rows, 13 masnui rows, and remedy delivery for 12 houses with H11 empty", () => {
    expect(rinData.rows).toHaveLength(9);
    expect(masnuiData.rows).toHaveLength(13);
    expect(remedyDelivery.rows).toHaveLength(12);
    expect(remedyDelivery.rows.find((r) => r.house === 11)?.no_remedy).toBe(true);
  });

  it("keeps entry text short (paraphrase, not book prose)", () => {
    for (const e of planetHouseEntries) {
      for (const c of e.conditions) expect(c.effect.length).toBeLessThan(220);
      for (const r of e.remedies) expect(r.text.length).toBeLessThan(320);
    }
  });

  it("reports coverage", () => {
    const cov = dataCoverage();
    expect(cov.planet_house).toEqual({ total: 108, done: 108, todo: 0 });
    expect(cov.rin.rows).toBe(9);
  });
});
