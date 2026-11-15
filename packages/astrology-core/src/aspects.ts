import type { Planet } from "./dignities";

/** Extra full sign aspects beyond the universal 7th, per graha drishti. */
const SPECIAL_ASPECTS: Partial<Record<Planet, number[]>> = {
  mars: [4, 8],
  jupiter: [5, 9],
  saturn: [3, 10],
};

const ASPECTING_PLANETS: Planet[] = [
  "sun",
  "moon",
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
];

export interface Aspect {
  from: Planet;
  to: Planet;
  /** House offset counted inclusively (7 = opposition). */
  count: number;
}

export interface Conjunction {
  signIndex: number;
  planets: Planet[];
}

/** Inclusive sign count from one sign to another (1-12). */
export function signCount(fromSign: number, toSign: number): number {
  return ((toSign - fromSign + 12) % 12) + 1;
}

export function computeAspects(planetSigns: Record<Planet, number>): Aspect[] {
  const aspects: Aspect[] = [];

  for (const from of ASPECTING_PLANETS) {
    const casts = [7, ...(SPECIAL_ASPECTS[from] ?? [])];
    for (const [to, toSign] of Object.entries(planetSigns) as Array<
      [Planet, number]
    >) {
      if (to === from) {
        continue;
      }
      const count = signCount(planetSigns[from], toSign);
      if (casts.includes(count)) {
        aspects.push({ from, to, count });
      }
    }
  }

  return aspects;
}

export function computeConjunctions(
  planetSigns: Record<Planet, number>,
): Conjunction[] {
  const bySign = new Map<number, Planet[]>();

  for (const [planet, sign] of Object.entries(planetSigns) as Array<
    [Planet, number]
  >) {
    bySign.set(sign, [...(bySign.get(sign) ?? []), planet]);
  }

  return [...bySign.entries()]
    .filter(([, planets]) => planets.length > 1)
    .map(([signIndex, planets]) => ({ signIndex, planets }))
    .sort((a, b) => a.signIndex - b.signIndex);
}
