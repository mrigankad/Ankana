import { masnuiData } from "./data";
import type { Cite, LkChart, Planet } from "./types";

export interface MasnuiFinding {
  id: string;
  formedPlanet: Planet;
  variant: string | null;
  components: [Planet, Planet];
  house: number;
  /** True when the formed planet itself also sits in the chart (the artificial one then acts on top of it). */
  formedPlanetPresent: boolean;
  cite: Cite;
  needs_review: boolean;
}

/** Artificial planets: both component planets share a house (p.68). */
export function detectMasnui(chart: LkChart): MasnuiFinding[] {
  const out: MasnuiFinding[] = [];
  for (const row of masnuiData.rows) {
    const [a, b] = row.components;
    const ha = chart.planetHouse[a];
    const hb = chart.planetHouse[b];
    if (!ha || ha !== hb) continue;
    out.push({
      id: row.id,
      formedPlanet: row.formed_planet,
      variant: row.variant,
      components: row.components,
      house: ha,
      formedPlanetPresent: chart.planetHouse[row.formed_planet] !== undefined,
      cite: row.cite,
      needs_review: row.needs_review,
    });
  }
  return out;
}
