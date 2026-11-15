import { aspectedHouses } from "./aspects";
import { planetsIn } from "./chart";
import { dormantData, pakkaGhar } from "./data";
import type { Cite, LkChart, Planet } from "./types";
import { PLANET_ORDER } from "./types";

export interface SleepingPlanet {
  planet: Planet;
  house: number;
  status: "awake" | "dormant";
  /** Rule id from data/dormant.json that decided the status. */
  rule: string;
  /** The planet whose presence/remedy awakens the house this planet sits in. */
  awakener: Planet;
  awakenerPresent: boolean;
  selfAwakeningAge: number;
  needs_review: boolean;
  cite: Cite;
}

export interface SleepingHouse {
  house: number;
  occupied: boolean;
  status: "active" | "dormant";
  /** Planet that wakes a dormant house (awakening map). */
  awakener: Planet;
  awakenerPresent: boolean;
  needs_review: boolean;
  cite: Cite;
}

function ruleOf(id: string) {
  const r = dormantData.rules.find((x) => x.id === id);
  if (!r) throw new Error(`unknown dormant rule ${id}`);
  return r;
}

function awakenerOf(house: number): Planet {
  const a = dormantData.awakeners.find((x) => x.house === house);
  if (!a) throw new Error(`no awakener for house ${house}`);
  return a.planet;
}

function ageOf(planet: Planet): number {
  return dormantData.self_awakening.find((x) => x.planet === planet)?.age ?? 0;
}

function sideEmpty(chart: LkChart, from: number, to: number): boolean {
  for (let h = from; h <= to; h += 1) {
    if (planetsIn(chart, h).length > 0) return false;
  }
  return true;
}

/** Dormant/awake status for every planet in the chart (rules in data/dormant.json). */
export function sleepingPlanets(chart: LkChart): SleepingPlanet[] {
  const aspected = aspectedHouses(chart);
  const priorEmpty = sideEmpty(chart, 1, 6);
  const latterEmpty = sideEmpty(chart, 7, 12);
  const h2Empty = planetsIn(chart, 2).length === 0;
  const h10Empty = planetsIn(chart, 10).length === 0;
  const out: SleepingPlanet[] = [];

  for (const planet of PLANET_ORDER) {
    const house = chart.planetHouse[planet];
    if (!house) continue;
    const own = pakkaGhar.find((r) => r.planet === planet)?.houses.includes(house) ?? false;

    let dormant = false;
    let ruleId = "active_default";
    if (own) {
      ruleId = "own_pakka_ghar";
    } else if (house >= 7 && priorEmpty) {
      dormant = true;
      ruleId = "prior_side_empty";
    } else if (house <= 6 && latterEmpty) {
      dormant = true;
      ruleId = "latter_side_empty";
    } else if (house === 2 && h10Empty) {
      dormant = true;
      ruleId = "h10_empty_h2";
    } else if (house === 10 && h2Empty) {
      dormant = true;
      ruleId = "h2_empty_h10";
    } else if (house === 9 && h2Empty) {
      dormant = true;
      ruleId = "h2_empty_h9";
    } else if (house <= 6 && planetsIn(chart, house + 6).length === 0) {
      dormant = true;
      ruleId = "no_opposite_planet";
    } else if (house >= 7 && !aspected.has(house)) {
      dormant = true;
      ruleId = "unaspected";
    }

    const rule = ruleId === "active_default" ? ruleOf("own_pakka_ghar") : ruleOf(ruleId);
    const awakener = awakenerOf(house);
    out.push({
      planet,
      house,
      status: dormant ? "dormant" : "awake",
      rule: ruleId,
      awakener,
      awakenerPresent: chart.planetHouse[awakener] !== undefined,
      selfAwakeningAge: ageOf(planet),
      needs_review: ruleId === "active_default" ? false : rule.needs_review,
      cite: rule.cite,
    });
  }
  return out;
}

/** Empty houses with no incoming aspect are dormant houses; each lists its awakening planet. */
export function sleepingHouses(chart: LkChart): SleepingHouse[] {
  const aspected = aspectedHouses(chart);
  const rule = ruleOf("empty_unaspected_house");
  const out: SleepingHouse[] = [];
  for (let house = 1; house <= 12; house += 1) {
    const occupied = planetsIn(chart, house).length > 0;
    const dormant = !occupied && !aspected.has(house);
    const awakener = awakenerOf(house);
    out.push({
      house,
      occupied,
      status: dormant ? "dormant" : "active",
      awakener,
      awakenerPresent: chart.planetHouse[awakener] !== undefined,
      needs_review: rule.needs_review,
      cite: rule.cite,
    });
  }
  return out;
}
