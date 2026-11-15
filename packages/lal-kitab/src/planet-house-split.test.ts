import { describe, expect, it } from "vitest";

import jupiterJson from "../data/planet_house/jupiter.json";
import marsJson from "../data/planet_house/mars.json";
import mercuryJson from "../data/planet_house/mercury.json";
import moonJson from "../data/planet_house/moon.json";
import type { PlanetHouseEntry } from "./data";

const files = { moon: moonJson, mars: marsJson, mercury: mercuryJson, jupiter: jupiterJson } as const;

describe("split planet_house files (moon, mars, mercury, jupiter)", () => {
  for (const [planet, json] of Object.entries(files)) {
    it(`${planet}: 12 houses with cites and valid schema`, () => {
      const rows = json.rows as unknown as PlanetHouseEntry[];
      expect(json.planet).toBe(planet);
      expect(rows.map((r) => r.house)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
      for (const r of rows) {
        expect(r.id).toBe(`${planet}_h${r.house}`);
        expect(r.planet).toBe(planet);
        expect(r.status).toBe("done");
        expect(typeof r.theme).toBe("string");
        expect(r.cite.vol).toBe("II");
        expect(r.cite.printed_page).toBeGreaterThan(0);
        expect(r.cite.pdf_page).toBeGreaterThan(r.cite.printed_page as number);
        expect(r.cite.section.length).toBeGreaterThan(0);
        expect(["high", "medium", "low"]).toContain(r.cite.ocr_confidence);
        expect(typeof r.needs_review).toBe("boolean");
        expect(r.conditions.length).toBeGreaterThan(0);
        for (const c of r.conditions) {
          expect(["benefic", "malefic", "neutral"]).toContain(c.tone);
          expect(c.effect.length).toBeGreaterThan(10);
          expect(typeof c.needs_review).toBe("boolean");
          if (c.when !== null) {
            expect(Array.isArray(c.when)).toBe(true);
            for (const cl of c.when) {
              expect(["in", "together", "empty", "alone"].some((k) => k in cl)).toBe(true);
            }
          }
        }
        for (const rem of r.remedies) {
          expect(rem.text.length).toBeGreaterThan(5);
          expect(rem.delivery === null || typeof rem.delivery === "string").toBe(true);
        }
      }
    });
  }
});
