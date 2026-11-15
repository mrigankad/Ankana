import { planetsIn } from "./chart";
import { rinData } from "./data";
import type { Cite, LkChart, Planet } from "./types";

export interface RinFinding {
  id: string;
  planet: Planet;
  kind: string;
  /** table: planet in a placement house with a listed enemy planet (p.134-135);
   *  first_degree_father: planet in H9 with Mercury in its root house (p.136);
   *  indicator: malefic planet in 2/5/9/12 (p.132). */
  basis: "table" | "first_degree_father" | "indicator";
  house: number;
  with: Planet[];
  cause: string;
  symptoms: string;
  remedy: string;
  remedy_cite: Cite;
  cite: Cite;
  needs_review: boolean;
}

export function detectRin(chart: LkChart): RinFinding[] {
  const out: RinFinding[] = [];

  for (const row of rinData.rows) {
    const house = chart.planetHouse[row.planet];
    if (!house || !row.placement_houses.includes(house)) continue;
    const present = planetsIn(chart, house).filter((p) => row.enemy_planets_with.includes(p));
    if (present.length === 0) continue;
    out.push({
      id: row.id,
      planet: row.planet,
      kind: row.kind,
      basis: "table",
      house,
      with: present,
      cause: row.cause,
      symptoms: row.symptoms,
      remedy: row.remedy,
      remedy_cite: row.remedy_cite,
      cite: row.cite,
      needs_review: row.needs_review,
    });
  }

  const father = rinData.rows.find((r) => r.id === "pitri_rin")!;
  const fd = rinData.first_degree_father;
  const mercuryHouse = chart.planetHouse.mercury;
  for (const row of fd.rows) {
    if (chart.planetHouse[row.planet] !== 9) continue;
    if (!mercuryHouse || !row.mercury_house.includes(mercuryHouse)) continue;
    if (row.planet === "mercury") continue;
    out.push({
      id: "pitri_rin_first_degree",
      planet: row.planet,
      kind: "Debt to father (first degree)",
      basis: "first_degree_father",
      house: 9,
      with: ["mercury"],
      cause: father.cause,
      symptoms: father.symptoms,
      remedy: father.remedy,
      remedy_cite: father.remedy_cite,
      cite: fd.cite,
      needs_review: true,
    });
  }

  const gi = rinData.general_indicator;
  for (const planet of gi.planets) {
    const house = chart.planetHouse[planet];
    if (!house || !gi.houses.includes(house)) continue;
    out.push({
      id: "pitri_rin_indicator",
      planet,
      kind: "Possible debt to father (indicator)",
      basis: "indicator",
      house,
      with: [],
      cause: father.cause,
      symptoms: father.symptoms,
      remedy: father.remedy,
      remedy_cite: father.remedy_cite,
      cite: gi.cite,
      needs_review: true,
    });
  }
  return out;
}
