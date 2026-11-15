import { describe, expect, it } from "vitest";

import { YOGINI_CYCLE_YEARS, YOGINIS, computeYogini } from "./dasha-yogini";

const BIRTH = new Date("1990-01-01T05:00:00Z");
const DAY_MS = 86_400_000;

describe("computeYogini", () => {
  it("uses the (nakshatra + 3) mod 8 starting rule", () => {
    // Ashwini (nakshatra 1): (1+3)%8 = 4 -> Bhramari (Mars, 4 years).
    const dasha = computeYogini(0, BIRTH);
    expect(dasha.birthNakshatra).toBe("Ashwini");
    expect(dasha.birthYogini).toBe("Bhramari");
    expect(dasha.mahadashas[0].planet).toBe("mars");
  });

  it("gives a full balance at the nakshatra start and half at midpoint", () => {
    expect(computeYogini(0, BIRTH).balanceYears).toBeCloseTo(4, 5);
    expect(computeYogini(360 / 27 / 2, BIRTH).balanceYears).toBeCloseTo(2, 5);
  });

  it("cycles through all eight yoginis summing to 36 years", () => {
    const total = YOGINIS.reduce((sum, y) => sum + y.years, 0);
    expect(total).toBe(YOGINI_CYCLE_YEARS);

    const dasha = computeYogini(45, BIRTH);
    const firstCycle = dasha.mahadashas.slice(0, 8);
    const names = new Set(firstCycle.map((m) => m.name));
    expect(names.size).toBe(8);

    const spanYears =
      (new Date(firstCycle[7].end).getTime() -
        new Date(firstCycle[0].start).getTime()) /
      (365.2425 * DAY_MS);
    expect(spanYears).toBeCloseTo(36, 3);
  });

  it("tiles antardashas exactly across each mahadasha", () => {
    const dasha = computeYogini(100, BIRTH);
    for (const mahadasha of dasha.mahadashas.slice(0, 3)) {
      const children = mahadasha.children!;
      expect(children).toHaveLength(8);
      expect(children[0].start).toBe(mahadasha.start);
      expect(children[7].end).toBe(mahadasha.end);
      expect(children[0].name).toBe(mahadasha.name);
    }
  });

  it("covers 72 years across two cycles", () => {
    const dasha = computeYogini(200, BIRTH);
    expect(dasha.mahadashas).toHaveLength(16);
  });
});
