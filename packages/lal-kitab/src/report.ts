import { lkAspects } from "./aspects";
import { lkChart } from "./chart";
import { planetHouseEntries } from "./data";
import { detectMasnui } from "./masnui";
import { matchPlanetHouseEntries, remedies } from "./remedies";
import { detectRin } from "./rin";
import { sleepingHouses, sleepingPlanets } from "./sleeping";
import type { LkArtifactInput, LkOptions } from "./types";
import { varshphal, yearOfLife, VARSHPHAL_MAX_AGE } from "./varshphal";

export interface LalKitabReportOptions extends LkOptions {
  /** Year of life for the annual chart; defaults from birth date and `now`. */
  age?: number;
  now?: Date;
}

/** Everything the lal-kitab tab needs, in one deterministic object. */
export function lalKitabReport(artifact: LkArtifactInput, options: LalKitabReportOptions = {}) {
  const chart = lkChart(artifact, options);
  const birth = artifact.calculationMetadata?.input?.birthDate;
  const now = options.now ?? new Date();
  const derivedAge = birth ? yearOfLife(birth, now) : undefined;
  const requested = options.age ?? derivedAge;
  const age = requested !== undefined && requested >= 1 && requested <= VARSHPHAL_MAX_AGE ? requested : undefined;

  return {
    origin: chart.origin,
    chart,
    sleepingPlanets: sleepingPlanets(chart),
    sleepingHouses: sleepingHouses(chart),
    aspects: lkAspects(chart),
    rin: detectRin(chart),
    masnui: detectMasnui(chart),
    planetHouse: matchPlanetHouseEntries(chart).map((m) => ({
      id: m.entry.id,
      planet: m.entry.planet,
      house: m.entry.house,
      theme: m.entry.theme,
      matched: m.matched,
      cite: m.entry.cite,
    })),
    varshphal: age !== undefined ? varshphal(chart, age) : null,
    varshphalAgeRequested: requested ?? null,
    remedies: remedies(chart),
    coverage: {
      planetHouseDone: planetHouseEntries.filter((e) => e.status === "done").length,
      planetHouseTotal: planetHouseEntries.length,
    },
  };
}
