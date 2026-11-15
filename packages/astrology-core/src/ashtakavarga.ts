import type { Planet } from "./dignities";

export type AshtakavargaPlanet =
  | "sun"
  | "moon"
  | "mars"
  | "mercury"
  | "jupiter"
  | "venus"
  | "saturn";

export const ASHTAKAVARGA_PLANETS: AshtakavargaPlanet[] = [
  "sun",
  "moon",
  "mars",
  "mercury",
  "jupiter",
  "venus",
  "saturn",
];

type Contributor = AshtakavargaPlanet | "lagna";

const CONTRIBUTORS: Contributor[] = [...ASHTAKAVARGA_PLANETS, "lagna"];

/**
 * Classical Bhinnashtakavarga benefic-place tables (BPHS). For each target
 * planet, the houses (counted inclusively from each contributor's sign)
 * where a bindu is earned. Row totals give the classical bindu counts:
 * Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56, Venus 52, Saturn 39;
 * Sarvashtakavarga total 337.
 */
const BENEFIC_PLACES: Record<
  AshtakavargaPlanet,
  Record<Contributor, number[]>
> = {
  sun: {
    sun: [1, 2, 4, 7, 8, 9, 10, 11],
    moon: [3, 6, 10, 11],
    mars: [1, 2, 4, 7, 8, 9, 10, 11],
    mercury: [3, 5, 6, 9, 10, 11, 12],
    jupiter: [5, 6, 9, 11],
    venus: [6, 7, 12],
    saturn: [1, 2, 4, 7, 8, 9, 10, 11],
    lagna: [3, 4, 6, 10, 11, 12],
  },
  moon: {
    sun: [3, 6, 7, 8, 10, 11],
    moon: [1, 3, 6, 7, 10, 11],
    mars: [2, 3, 5, 6, 9, 10, 11],
    mercury: [1, 3, 4, 5, 7, 8, 10, 11],
    jupiter: [1, 4, 7, 8, 10, 11, 12],
    venus: [3, 4, 5, 7, 9, 10, 11],
    saturn: [3, 5, 6, 11],
    lagna: [3, 6, 10, 11],
  },
  mars: {
    sun: [3, 5, 6, 10, 11],
    moon: [3, 6, 11],
    mars: [1, 2, 4, 7, 8, 10, 11],
    mercury: [3, 5, 6, 11],
    jupiter: [6, 10, 11, 12],
    venus: [6, 8, 11, 12],
    saturn: [1, 4, 7, 8, 9, 10, 11],
    lagna: [1, 3, 6, 10, 11],
  },
  mercury: {
    sun: [5, 6, 9, 11, 12],
    moon: [2, 4, 6, 8, 10, 11],
    mars: [1, 2, 4, 7, 8, 9, 10, 11],
    mercury: [1, 3, 5, 6, 9, 10, 11, 12],
    jupiter: [6, 8, 11, 12],
    venus: [1, 2, 3, 4, 5, 8, 9, 11],
    saturn: [1, 2, 4, 7, 8, 9, 10, 11],
    lagna: [1, 2, 4, 6, 8, 10, 11],
  },
  jupiter: {
    sun: [1, 2, 3, 4, 7, 8, 9, 10, 11],
    moon: [2, 5, 7, 9, 11],
    mars: [1, 2, 4, 7, 8, 10, 11],
    mercury: [1, 2, 4, 5, 6, 9, 10, 11],
    jupiter: [1, 2, 3, 4, 7, 8, 10, 11],
    venus: [2, 5, 6, 9, 10, 11],
    saturn: [3, 5, 6, 12],
    lagna: [1, 2, 4, 5, 6, 7, 9, 10, 11],
  },
  venus: {
    sun: [8, 11, 12],
    moon: [1, 2, 3, 4, 5, 8, 9, 11, 12],
    mars: [3, 5, 6, 9, 11, 12],
    mercury: [3, 5, 6, 9, 11],
    jupiter: [5, 8, 9, 10, 11],
    venus: [1, 2, 3, 4, 5, 8, 9, 10, 11],
    saturn: [3, 4, 5, 8, 9, 10, 11],
    lagna: [1, 2, 3, 4, 5, 8, 9, 11],
  },
  saturn: {
    sun: [1, 2, 4, 7, 8, 10, 11],
    moon: [3, 6, 11],
    mars: [3, 5, 6, 10, 11, 12],
    mercury: [6, 8, 9, 10, 11, 12],
    jupiter: [5, 6, 11, 12],
    venus: [6, 11, 12],
    saturn: [3, 5, 6, 11],
    lagna: [1, 3, 4, 6, 10, 11],
  },
};

export interface AshtakavargaResult {
  planet: AshtakavargaPlanet;
  /** Bindus earned in each sign, index 0 = Aries. */
  bindusBySign: number[];
  totalBindus: number;
}

export interface AshtakavargaInput {
  /** Sign index (0-11) per graha; nodes are ignored by ashtakavarga. */
  signs: Record<Planet, number>;
  ascendantSign: number;
}

export function computeAshtakavarga(
  input: AshtakavargaInput,
): AshtakavargaResult[] {
  return ASHTAKAVARGA_PLANETS.map((target) => {
    const bindusBySign = Array.from({ length: 12 }, () => 0);

    for (const contributor of CONTRIBUTORS) {
      const fromSign =
        contributor === "lagna"
          ? input.ascendantSign
          : input.signs[contributor];

      for (const house of BENEFIC_PLACES[target][contributor]) {
        bindusBySign[(fromSign + house - 1) % 12] += 1;
      }
    }

    return {
      planet: target,
      bindusBySign,
      totalBindus: bindusBySign.reduce((sum, b) => sum + b, 0),
    };
  });
}

/** Sarvashtakavarga: per-sign sums across the seven bhinnashtakavargas. */
export function computeSarvashtakavarga(
  results: AshtakavargaResult[],
): number[] {
  const sums = Array.from({ length: 12 }, () => 0);
  for (const result of results) {
    result.bindusBySign.forEach((bindus, sign) => {
      sums[sign] += bindus;
    });
  }
  return sums;
}
