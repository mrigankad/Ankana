import { describe, expect, it } from "vitest";

import {
  VIMSHOTTARI_TOTAL_YEARS,
  VIMSHOTTARI_YEARS,
  computeVimshottari,
} from "./dasha-vimshottari";

const BIRTH = new Date("1990-01-01T05:00:00Z");
const DAY_MS = 86_400_000;

describe("computeVimshottari", () => {
  it("gives a full Ketu balance for the Moon at 0 Ashwini", () => {
    const dasha = computeVimshottari(0, BIRTH);
    expect(dasha.birthLord).toBe("ketu");
    expect(dasha.balanceYears).toBeCloseTo(7, 5);
    expect(dasha.mahadashas[0].planet).toBe("ketu");
    expect(new Date(dasha.mahadashas[0].start).getTime()).toBeCloseTo(
      BIRTH.getTime(),
      -4,
    );
  });

  it("halves the balance mid-nakshatra", () => {
    const dasha = computeVimshottari(360 / 27 / 2, BIRTH);
    expect(dasha.balanceYears).toBeCloseTo(3.5, 5);
  });

  it("orders mahadashas in the Vimshottari sequence covering 120 years", () => {
    const dasha = computeVimshottari(45, BIRTH); // Rohini -> Moon lord
    expect(dasha.birthLord).toBe("moon");
    expect(dasha.mahadashas.map((p) => p.planet)).toEqual([
      "moon",
      "mars",
      "rahu",
      "jupiter",
      "saturn",
      "mercury",
      "ketu",
      "venus",
      "sun",
    ]);

    const first = new Date(dasha.mahadashas[0].start).getTime();
    const last = new Date(dasha.mahadashas[8].end).getTime();
    const totalYears = (last - first) / (365.2425 * DAY_MS);
    expect(totalYears).toBeCloseTo(VIMSHOTTARI_TOTAL_YEARS, 3);
  });

  it("sizes antardashas proportionally and nests pratyantardashas", () => {
    const dasha = computeVimshottari(0, BIRTH);
    const ketuMd = dasha.mahadashas[0];
    const antardashas = ketuMd.children!;

    expect(antardashas[0].planet).toBe("ketu");
    const ketuAdDays =
      (new Date(antardashas[0].end).getTime() -
        new Date(antardashas[0].start).getTime()) /
      DAY_MS;
    const expectedDays =
      ((VIMSHOTTARI_YEARS.ketu * VIMSHOTTARI_YEARS.ketu) /
        VIMSHOTTARI_TOTAL_YEARS) *
      365.2425;
    expect(ketuAdDays).toBeCloseTo(expectedDays, 1);

    // Antardashas tile the mahadasha exactly.
    expect(antardashas[8].end).toBe(ketuMd.end);
    // Pratyantardashas exist and tile their antardasha.
    const pratyantars = antardashas[0].children!;
    expect(pratyantars).toHaveLength(9);
    expect(pratyantars[8].end).toBe(antardashas[0].end);
  });
});
