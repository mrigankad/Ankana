import { describe, expect, it } from "vitest";

import {
  ASHTAKAVARGA_PLANETS,
  computeAshtakavarga,
  computeSarvashtakavarga,
  type AshtakavargaInput,
} from "./ashtakavarga";
import type { Planet } from "./dignities";

const SAMPLE: AshtakavargaInput = {
  signs: {
    sun: 8,
    moon: 10,
    mercury: 9,
    venus: 9,
    mars: 7,
    jupiter: 2,
    saturn: 8,
    rahu: 9,
    ketu: 3,
  } as Record<Planet, number>,
  ascendantSign: 10,
};

describe("computeAshtakavarga", () => {
  const results = computeAshtakavarga(SAMPLE);

  it("reproduces the classical bindu totals regardless of chart", () => {
    const expectedTotals: Record<string, number> = {
      sun: 48,
      moon: 49,
      mars: 39,
      mercury: 54,
      jupiter: 56,
      venus: 52,
      saturn: 39,
    };

    for (const result of results) {
      expect(result.totalBindus).toBe(expectedTotals[result.planet]);
    }
  });

  it("keeps every sign's bindus within 0..8 (eight contributors)", () => {
    for (const result of results) {
      for (const bindus of result.bindusBySign) {
        expect(bindus).toBeGreaterThanOrEqual(0);
        expect(bindus).toBeLessThanOrEqual(8);
      }
      expect(result.bindusBySign).toHaveLength(12);
    }
  });

  it("shifts with the contributor positions", () => {
    const shifted = computeAshtakavarga({
      ...SAMPLE,
      signs: Object.fromEntries(
        Object.entries(SAMPLE.signs).map(([p, s]) => [p, (s + 1) % 12]),
      ) as Record<Planet, number>,
      ascendantSign: (SAMPLE.ascendantSign + 1) % 12,
    });

    const original = results.find((r) => r.planet === "sun")!;
    const moved = shifted.find((r) => r.planet === "sun")!;
    // Whole chart rotated by one sign: bindus rotate with it.
    expect(moved.bindusBySign).toEqual([
      original.bindusBySign[11],
      ...original.bindusBySign.slice(0, 11),
    ]);
  });

  it("covers all seven classical planets", () => {
    expect(results.map((r) => r.planet)).toEqual(ASHTAKAVARGA_PLANETS);
  });
});

describe("computeSarvashtakavarga", () => {
  it("always sums to the classical 337 bindus", () => {
    const sav = computeSarvashtakavarga(computeAshtakavarga(SAMPLE));
    expect(sav.reduce((a, b) => a + b, 0)).toBe(337);
    expect(sav).toHaveLength(12);
  });
});
