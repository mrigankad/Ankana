import { describe, expect, it } from "vitest";

import { aspectRows, cycle35, dormantData, masnuiData, pakkaGhar, planetHouseEntries } from "./data";
import {
  detectMasnui,
  detectRin,
  lkChartFromHouses,
  sleepingHouses,
  sleepingPlanets,
} from "./index";
import type { Planet } from "./index";

/**
 * Checks added by the book audit (docs/lal-kitab-verification.md). Page numbers refer to the
 * 1952 Goswami/Vashisth edition; pdf_page - printed_page differs per section of the scan.
 */
describe("page cites (audit)", () => {
  // printed = pdf - offset, read off the page headers of the scan for each planet section
  const offset: Record<string, number> = {
    sun: 16, moon: 14, mars: 11, mercury: 10, jupiter: 16, venus: 13, saturn: 8, rahu: 6, ketu: 4,
  };

  it("planet-house rows use the per-section page offset and are image verified", () => {
    for (const e of planetHouseEntries) {
      expect(e.cite.pdf_page! - e.cite.printed_page!, e.id).toBe(offset[e.planet]);
      expect(e.cite.verified_from_image, e.id).toBe(true);
    }
  });

  it("table cites carry the offsets seen on the page images", () => {
    expect(pakkaGhar.every((r) => r.cite.printed_page === 69 && r.cite.pdf_page === 88)).toBe(true);
    expect(cycle35.every((r) => r.cite.printed_page === 78 && r.cite.pdf_page === 97)).toBe(true);
    expect(dormantData.awakeners.every((r) => r.cite.printed_page === 116 && r.cite.pdf_page === 135)).toBe(true);
    expect(masnuiData.rows.every((r) => r.cite.printed_page === 68 && r.cite.pdf_page === 87)).toBe(true);
  });
});

describe("rules (audit)", () => {
  it("6 to 12 aspect is supported by the prose list and carries no review flag", () => {
    const row = aspectRows.find((r) => r.from === 6)!;
    expect(row.to).toEqual([12]);
    expect(row.strength).toBe(25);
    expect(row.derived).toBe(false);
    expect(row.needs_review).toBe(false);
  });

  it("derived 7th-house aspects stay flagged (book is ambiguous)", () => {
    for (const r of aspectRows.filter((x) => x.derived)) expect(r.needs_review).toBe(true);
  });

  it("cycle sequence matches the p.77 wording", () => {
    expect(cycle35.map((r) => `${r.planet}${r.years}`)).toEqual([
      "jupiter6", "sun2", "moon1", "venus3", "mars6", "mercury2", "saturn6", "rahu6", "ketu3",
    ]);
  });

  it("book worked example (Patiala 1962, p.761): engine agrees on 8 of 9 planets", () => {
    const chart = lkChartFromHouses({
      jupiter: 5, sun: 11, moon: 1, venus: 1, mars: 9, mercury: 12, saturn: 4, rahu: 10, ketu: 4,
    });
    const status = Object.fromEntries(sleepingPlanets(chart).map((s) => [s.planet, s.status]));
    const book: Record<Planet, string> = {
      jupiter: "awake", sun: "dormant", moon: "dormant", venus: "dormant", mars: "dormant",
      mercury: "dormant", saturn: "awake", rahu: "awake", ketu: "awake",
    };
    const diff = (Object.keys(book) as Planet[]).filter((p) => status[p] !== book[p]);
    // Documented divergence: H2 is empty so the literal p.117 rule makes Rahu in H10 dormant,
    // while the book calls it awake. Left for a Lal Kitab expert.
    expect(diff).toEqual(["rahu"]);
  });

  it("anonymised chart A: empty H2 makes H10 planets dormant, three artificial planets form", () => {
    const chart = lkChartFromHouses({
      ketu: 1, mars: 3, rahu: 7, saturn: 8, sun: 10, venus: 10, jupiter: 10, moon: 11, mercury: 11,
    });
    const s = Object.fromEntries(sleepingPlanets(chart).map((x) => [x.planet, x]));
    for (const p of ["sun", "venus", "jupiter"] as Planet[]) {
      expect(s[p].status).toBe("dormant");
      expect(s[p].rule).toBe("h2_empty_h10");
    }
    expect(s.saturn.rule).toBe("own_pakka_ghar");
    expect(s.mars.rule).toBe("own_pakka_ghar");
    // Mars in H3 sends a half aspect to H11, so the Moon there is not unaspected in this variant.
    expect(s.moon.rule).toBe("active_default");
    expect(detectMasnui(chart).map((m) => m.id).sort()).toEqual([
      "masnui_jupiter", "masnui_moon", "masnui_saturn_ketu_like",
    ]);
    expect(detectRin(chart)).toEqual([]);
  });

  it("sample client chart (Pisces lagna): dormant set, father's debt first degree", () => {
    const chart = lkChartFromHouses({
      sun: 1, ketu: 2, mars: 5, moon: 6, rahu: 8, jupiter: 9, venus: 11, mercury: 12, saturn: 12,
    });
    const dormant = sleepingPlanets(chart).filter((s) => s.status === "dormant").map((s) => s.planet).sort();
    expect(dormant).toEqual(["ketu", "rahu", "venus"]);
    expect(sleepingHouses(chart).filter((h) => h.status === "dormant").map((h) => h.house)).toEqual([3, 4, 10]);
    expect(detectMasnui(chart)).toEqual([]);
    expect(detectRin(chart).map((r) => r.id)).toContain("pitri_rin_first_degree");
  });
});
