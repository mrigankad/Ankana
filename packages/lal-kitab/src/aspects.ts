import { aspectRows } from "./data";
import { planetsIn } from "./chart";
import type { Cite, LkChart, Planet } from "./types";

export interface LkAspect {
  from: { planet: Planet; house: number };
  to: { planet: Planet; house: number };
  strength: number;
  derived: boolean;
  cite: Cite;
  needs_review: boolean;
}

/** All planet-to-planet aspects (directed) present in the chart. */
export function lkAspects(chart: LkChart): LkAspect[] {
  const out: LkAspect[] = [];
  for (const row of aspectRows) {
    for (const src of planetsIn(chart, row.from)) {
      for (const target of row.to) {
        for (const dst of planetsIn(chart, target)) {
          out.push({
            from: { planet: src, house: row.from },
            to: { planet: dst, house: target },
            strength: row.strength,
            derived: row.derived,
            cite: row.cite,
            needs_review: row.needs_review,
          });
        }
      }
    }
  }
  return out;
}

/** Houses that receive an aspect arrow from an occupied house. */
export function aspectedHouses(chart: LkChart): Map<number, number> {
  const best = new Map<number, number>();
  for (const row of aspectRows) {
    if (planetsIn(chart, row.from).length === 0) continue;
    for (const t of row.to) {
      best.set(t, Math.max(best.get(t) ?? 0, row.strength));
    }
  }
  return best;
}
