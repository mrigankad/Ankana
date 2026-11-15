import { describe, expect, it } from "vitest";

import ketuJson from "../data/planet_house/ketu.json";
import rahuJson from "../data/planet_house/rahu.json";
import saturnJson from "../data/planet_house/saturn.json";
import venusJson from "../data/planet_house/venus.json";
import { PLANET_ORDER } from "./types";

const FILES = ["venus", "saturn", "rahu", "ketu"] as const;
const planets = new Set<string>(PLANET_ORDER);

const JSONS: Record<string, unknown> = {
  venus: venusJson,
  saturn: saturnJson,
  rahu: rahuJson,
  ketu: ketuJson,
};

function load(name: string) {
  return JSONS[name] as { planet: string; rows: any[] };
}

function checkClause(c: any) {
  const keys = Object.keys(c);
  expect(keys).toHaveLength(1);
  if ("in" in c) {
    expect(c.in.planets.length).toBeGreaterThan(0);
    for (const p of c.in.planets) expect(planets.has(p)).toBe(true);
    for (const h of c.in.houses) expect(h >= 1 && h <= 12).toBe(true);
  } else if ("together" in c) {
    expect(c.together).toHaveLength(2);
    for (const p of c.together) expect(planets.has(p)).toBe(true);
  } else if ("empty" in c) {
    for (const h of c.empty) expect(h >= 1 && h <= 12).toBe(true);
  } else {
    expect(c.alone).toBe(true);
  }
}

describe.each(FILES)("planet_house/%s.json", (name) => {
  const data = load(name);

  it("has 12 houses with unique ids", () => {
    expect(data.planet).toBe(name);
    expect(data.rows).toHaveLength(12);
    expect(data.rows.map((r) => r.house)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    expect(data.rows.map((r) => r.id)).toEqual(
      Array.from({ length: 12 }, (_, i) => `${name}_h${i + 1}`),
    );
  });

  it("every row has a valid cite and schema", () => {
    for (const r of data.rows) {
      expect(r.planet).toBe(name);
      expect(r.status).toBe("done");
      expect(typeof r.theme).toBe("string");
      expect(typeof r.needs_review).toBe("boolean");
      expect(r.cite.vol).toBe("II");
      expect(Number.isInteger(r.cite.printed_page)).toBe(true);
      expect(Number.isInteger(r.cite.pdf_page)).toBe(true);
      expect(typeof r.cite.section).toBe("string");
      expect(["high", "medium", "low"]).toContain(r.cite.ocr_confidence);
      expect(typeof r.cite.verified_from_image).toBe("boolean");
      expect(r.conditions.length).toBeGreaterThan(0);
      for (const c of r.conditions) {
        expect(["benefic", "malefic", "neutral"]).toContain(c.tone);
        expect(typeof c.effect).toBe("string");
        expect(c.effect.length).toBeGreaterThan(0);
        expect(typeof c.needs_review).toBe("boolean");
        if (c.when !== null) {
          expect(Array.isArray(c.when)).toBe(true);
          for (const cl of c.when) checkClause(cl);
        }
      }
      for (const rem of r.remedies) {
        expect(typeof rem.text).toBe("string");
        expect(rem.delivery === null || typeof rem.delivery === "string").toBe(true);
        for (const k of ["action", "item", "venue", "duration"]) {
          expect(rem[k] === null || typeof rem[k] === "string").toBe(true);
        }
      }
    }
  });
});
