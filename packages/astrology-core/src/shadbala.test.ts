import { describe, expect, it } from "vitest";

import type { Planet } from "./dignities";
import { computeShadbala, type ShadbalaInput } from "./shadbala";
import { computeVimshopaka } from "./vimshopaka";

function input(overrides: Partial<ShadbalaInput> = {}): ShadbalaInput {
  return {
    longitudes: {
      sun: 130, // Leo 10 (moolatrikona)
      moon: 42, // Taurus 12 (exalted around 3 Taurus)
      mars: 275, // Capricorn 5
      mercury: 160, // Virgo 10
      jupiter: 95, // Cancer 5 (exalted)
      venus: 350, // Pisces 20
      saturn: 195, // Libra 15 (exalted)
      rahu: 60,
      ketu: 240,
    } as Record<Planet, number>,
    ascendantLongitude: 125, // Leo lagna
    moonSunElongation: 90,
    retrograde: {
      sun: false,
      moon: false,
      mars: false,
      mercury: false,
      jupiter: false,
      venus: false,
      saturn: true,
      rahu: true,
      ketu: true,
    } as Record<Planet, boolean>,
    isDayBirth: true,
    ...overrides,
  };
}

describe("computeShadbala", () => {
  const results = computeShadbala(input());

  it("scores all seven planets with positive components", () => {
    expect(results).toHaveLength(7);
    for (const r of results) {
      expect(r.totalRupas).toBeGreaterThan(0);
      expect(r.sthana).toBeGreaterThan(0);
      expect(r.ratio).toBeGreaterThan(0);
    }
  });

  it("gives full uccha bala at deep exaltation and none at debilitation", () => {
    const exalted = computeShadbala(
      input({ longitudes: { ...input().longitudes, sun: 10 } }),
    ).find((r) => r.planet === "sun")!;
    const debilitated = computeShadbala(
      input({ longitudes: { ...input().longitudes, sun: 190 } }),
    ).find((r) => r.planet === "sun")!;

    // Uccha contributes up to 60 virupas inside sthana.
    expect(exalted.sthana - debilitated.sthana).toBeGreaterThan(50);
  });

  it("grants dig bala at the power house", () => {
    // Jupiter strongest in the 1st: put Jupiter in the lagna sign.
    const inLagna = computeShadbala(
      input({ longitudes: { ...input().longitudes, jupiter: 128 } }),
    ).find((r) => r.planet === "jupiter")!;
    const opposite = computeShadbala(
      input({ longitudes: { ...input().longitudes, jupiter: 308 } }),
    ).find((r) => r.planet === "jupiter")!;

    expect(inLagna.dig).toBe(60);
    expect(opposite.dig).toBe(0);
  });

  it("swings paksha bala with the lunar phase", () => {
    const fullMoon = computeShadbala(input({ moonSunElongation: 180 })).find(
      (r) => r.planet === "moon",
    )!;
    const newMoon = computeShadbala(input({ moonSunElongation: 2 })).find(
      (r) => r.planet === "moon",
    )!;
    expect(fullMoon.kala).toBeGreaterThan(newMoon.kala);
  });

  it("rewards retrograde motion with cheshta bala", () => {
    const results2 = computeShadbala(input());
    expect(results2.find((r) => r.planet === "saturn")!.cheshta).toBe(60);
    expect(results2.find((r) => r.planet === "mars")!.cheshta).toBe(30);
  });

  it("is deterministic", () => {
    expect(computeShadbala(input())).toEqual(computeShadbala(input()));
  });
});

describe("computeVimshopaka", () => {
  it("keeps every score within 0..20", () => {
    const scores = computeVimshopaka(input().longitudes);
    expect(scores).toHaveLength(7);
    for (const { score } of scores) {
      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThanOrEqual(20);
    }
  });

  it("scores an all-own-sign planet near the maximum", () => {
    // Sun in Leo 5 deg: own in D1; varga dignities vary but should
    // clearly beat a debilitated Sun.
    const strong = computeVimshopaka({
      ...input().longitudes,
      sun: 125,
    } as Record<Planet, number>).find((s) => s.planet === "sun")!;
    const weak = computeVimshopaka({
      ...input().longitudes,
      sun: 190,
    } as Record<Planet, number>).find((s) => s.planet === "sun")!;

    expect(strong.score).toBeGreaterThan(weak.score);
  });
});
