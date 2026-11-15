import { lkChartFromHouses } from "./chart";
import { cycle35, varshphalData } from "./data";
import type { LkChart, Planet } from "./types";
import { PLANET_ORDER } from "./types";

export const VARSHPHAL_MAX_AGE = varshphalData.rows.length;

export interface VarshphalPlanet {
  planet: Planet;
  natalHouse: number;
  annualHouse: number;
  /** Vikram-year month the annual house corresponds to (p.215). */
  month: string;
}

export interface VarshphalResult {
  /** Year of life as indexed by the matrix: 1 = first year (the matrix has no natal row; see data/varshphal.json coverage_note for the age convention question). */
  age: number;
  /** annualHouse for natal house 1..12 (index 0 = natal house 1). */
  row: number[];
  planets: VarshphalPlanet[];
  annualChart: LkChart;
  cycle35: {
    rotation: number;
    yearInCycle: number;
    cyclePlanet: Planet;
    part: "beginning" | "middle" | "last";
    partRuler: Planet;
    needs_review: boolean;
  };
  semantics: string;
}

function monthOf(house: number): string {
  return varshphalData.months.rows.find((r) => r.house === house)?.month ?? "";
}

/** Position within the 35 year circulation (p.78). */
export function cycle35Position(age: number): VarshphalResult["cycle35"] {
  const rotation = Math.floor((age - 1) / 35) + 1;
  const yearInCycle = ((age - 1) % 35) + 1;
  let acc = 0;
  for (const row of cycle35) {
    if (yearInCycle <= acc + row.years) {
      const within = yearInCycle - acc; // 1..years
      const partLen = row.years / 3;
      const idx = Math.min(2, Math.floor((within - 1) / partLen));
      return {
        rotation,
        yearInCycle,
        cyclePlanet: row.planet,
        part: row.parts[idx].part,
        partRuler: row.parts[idx].ruler,
        needs_review: row.needs_review,
      };
    }
    acc += row.years;
  }
  throw new Error("unreachable");
}

/** Annual chart (varshphal) for a given year of life, from the book's age matrix. */
export function varshphal(chart: LkChart, age: number): VarshphalResult {
  if (!Number.isInteger(age) || age < 1 || age > VARSHPHAL_MAX_AGE) {
    throw new RangeError(`age must be an integer 1..${VARSHPHAL_MAX_AGE} (the book's matrix stops at ${VARSHPHAL_MAX_AGE})`);
  }
  const row = varshphalData.rows[age - 1].houses;
  const planets: VarshphalPlanet[] = [];
  const mapped: Partial<Record<Planet, number>> = {};
  for (const planet of PLANET_ORDER) {
    const natalHouse = chart.planetHouse[planet];
    if (!natalHouse) continue;
    const annualHouse = row[natalHouse - 1];
    mapped[planet] = annualHouse;
    planets.push({ planet, natalHouse, annualHouse, month: monthOf(annualHouse) });
  }
  return {
    age,
    row,
    planets,
    annualChart: lkChartFromHouses(mapped, chart.origin),
    cycle35: cycle35Position(age),
    semantics:
      "matrix[age][natal house] = annual house; age 1 is the first year of life (completed years + 1)",
  };
}

/** Year of life for the matrix from a birth date (YYYY-MM-DD) and a reference date. */
export function yearOfLife(birthDate: string, now: Date): number {
  const [y, m, d] = birthDate.split("-").map(Number);
  let completed = now.getUTCFullYear() - y;
  const beforeBirthday =
    now.getUTCMonth() + 1 < m || (now.getUTCMonth() + 1 === m && now.getUTCDate() < d);
  if (beforeBirthday) completed -= 1;
  return Math.max(1, completed + 1);
}
