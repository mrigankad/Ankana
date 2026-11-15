import { describe, expect, it } from "vitest";

import { VARGA_KEYS, computeVargaCharts, vargaSign } from "./vargas";

describe("vargaSign d9 (navamsa)", () => {
  it("follows the classical starting signs by modality", () => {
    expect(vargaSign("d9", 1)).toBe(0); // Aries 1deg -> Aries navamsa
    expect(vargaSign("d9", 10)).toBe(3); // Aries 10deg (4th part) -> Cancer
    expect(vargaSign("d9", 30)).toBe(9); // Taurus 0deg -> Capricorn
    expect(vargaSign("d9", 60)).toBe(6); // Gemini 0deg -> Libra
    expect(vargaSign("d9", 90)).toBe(3); // Cancer 0deg -> Cancer
  });
});

describe("vargaSign d2 (hora)", () => {
  it("assigns Leo and Cancer by half and parity", () => {
    expect(vargaSign("d2", 10)).toBe(4); // Aries first half -> Leo
    expect(vargaSign("d2", 20)).toBe(3); // Aries second half -> Cancer
    expect(vargaSign("d2", 40)).toBe(3); // Taurus first half -> Cancer
    expect(vargaSign("d2", 50)).toBe(4); // Taurus second half -> Leo
  });
});

describe("vargaSign d3 (drekkana)", () => {
  it("maps thirds to same, fifth, and ninth signs", () => {
    expect(vargaSign("d3", 5)).toBe(0); // Aries 1st -> Aries
    expect(vargaSign("d3", 15)).toBe(4); // Aries 2nd -> Leo
    expect(vargaSign("d3", 25)).toBe(8); // Aries 3rd -> Sagittarius
  });
});

describe("vargaSign d10 (dasamsa)", () => {
  it("starts odd signs from themselves and even signs from the ninth", () => {
    expect(vargaSign("d10", 1)).toBe(0); // Aries part 0 -> Aries
    expect(vargaSign("d10", 31)).toBe(9); // Taurus part 0 -> Capricorn
  });
});

describe("vargaSign d30 (trimsamsa)", () => {
  it("uses the fixed odd and even spans", () => {
    expect(vargaSign("d30", 3)).toBe(0); // Aries 3deg -> Aries (Mars span)
    expect(vargaSign("d30", 7)).toBe(10); // Aries 7deg -> Aquarius (Saturn)
    expect(vargaSign("d30", 33)).toBe(1); // Taurus 3deg -> Taurus (Venus)
    expect(vargaSign("d30", 59)).toBe(7); // Taurus 29deg -> Scorpio (Mars)
  });
});

describe("computeVargaCharts", () => {
  it("produces every varga with signs in range", () => {
    const charts = computeVargaCharts({ sun: 256.7, moon: 123.4 }, 300.2);

    expect(Object.keys(charts)).toEqual([...VARGA_KEYS]);
    for (const chart of Object.values(charts)) {
      expect(chart.ascendantSign).toBeGreaterThanOrEqual(0);
      expect(chart.ascendantSign).toBeLessThan(12);
      for (const sign of Object.values(chart.planets)) {
        expect(sign).toBeGreaterThanOrEqual(0);
        expect(sign).toBeLessThan(12);
      }
    }
  });
});
