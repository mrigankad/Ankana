import { dignityOf, type Dignity, type Planet } from "./dignities";
import { vargaSign, type VargaKey } from "./vargas";

/** Shadvarga weights totalling 20 (BPHS vimshopaka, shadvarga scheme). */
const SHADVARGA_WEIGHTS: Partial<Record<VargaKey, number>> = {
  d1: 6,
  d2: 2,
  d3: 4,
  d9: 5,
  d12: 2,
  d30: 1,
};

/** Fraction of a varga's weight earned per dignity in that varga. */
const DIGNITY_FRACTION: Record<Dignity, number> = {
  exalted: 1,
  moolatrikona: 1,
  own: 1,
  friend: 0.75,
  neutral: 0.5,
  enemy: 0.25,
  debilitated: 0.125,
};

export interface VimshopakaResult {
  planet: Planet;
  /** 0-20; >=15 classically counts as strong, <10 weak. */
  score: number;
}

const SCORED_PLANETS: Planet[] = [
  "sun",
  "moon",
  "mars",
  "mercury",
  "jupiter",
  "venus",
  "saturn",
];

export function computeVimshopaka(
  longitudes: Record<Planet, number>,
): VimshopakaResult[] {
  return SCORED_PLANETS.map((planet) => {
    let score = 0;

    for (const [chart, weight] of Object.entries(SHADVARGA_WEIGHTS) as Array<
      [VargaKey, number]
    >) {
      const sign = vargaSign(chart, longitudes[planet]);
      // Dignity evaluated at the varga sign's midpoint.
      const dignity = dignityOf(planet, sign * 30 + 15);
      score += weight * DIGNITY_FRACTION[dignity];
    }

    return { planet, score: Math.round(score * 100) / 100 };
  });
}
