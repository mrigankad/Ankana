import { NAKSHATRA_LORD_CYCLE, nakshatraOf } from "./zodiac";

export const VIMSHOTTARI_YEARS: Record<string, number> = {
  ketu: 7,
  venus: 20,
  sun: 6,
  moon: 10,
  mars: 7,
  rahu: 18,
  jupiter: 16,
  saturn: 19,
  mercury: 17,
};

export const VIMSHOTTARI_TOTAL_YEARS = 120;

const DAYS_PER_YEAR = 365.2425;
const MS_PER_YEAR = DAYS_PER_YEAR * 86_400_000;

export interface DashaPeriod {
  level: "mahadasha" | "antardasha" | "pratyantardasha";
  planet: string;
  /** Period name where the system uses one (e.g. yogini names). */
  name?: string;
  start: string;
  end: string;
  children?: DashaPeriod[];
}

export interface VimshottariDasha {
  birthNakshatra: string;
  birthLord: string;
  balanceYears: number;
  mahadashas: DashaPeriod[];
}

function lordSequence(startLord: string): string[] {
  const startIndex = NAKSHATRA_LORD_CYCLE.indexOf(
    startLord as (typeof NAKSHATRA_LORD_CYCLE)[number],
  );
  return Array.from(
    { length: 9 },
    (_, i) => NAKSHATRA_LORD_CYCLE[(startIndex + i) % 9],
  );
}

function buildSubPeriods(
  parentPlanet: string,
  parentStartMs: number,
  parentYears: number,
  level: "antardasha" | "pratyantardasha",
): DashaPeriod[] {
  const sequence = lordSequence(parentPlanet);
  const periods: DashaPeriod[] = [];
  let cursor = parentStartMs;

  for (const planet of sequence) {
    const years = (parentYears * VIMSHOTTARI_YEARS[planet]) / VIMSHOTTARI_TOTAL_YEARS;
    const endMs = cursor + years * MS_PER_YEAR;

    const period: DashaPeriod = {
      level,
      planet,
      start: new Date(cursor).toISOString(),
      end: new Date(endMs).toISOString(),
    };

    if (level === "antardasha") {
      period.children = buildSubPeriods(planet, cursor, years, "pratyantardasha");
    }

    periods.push(period);
    cursor = endMs;
  }

  return periods;
}

export function computeVimshottari(
  moonSiderealLongitude: number,
  birthUtc: Date,
): VimshottariDasha {
  const nakshatra = nakshatraOf(moonSiderealLongitude);
  const birthLord = nakshatra.lord;
  const birthLordYears = VIMSHOTTARI_YEARS[birthLord];
  const balanceYears = birthLordYears * (1 - nakshatra.fractionTraversed);

  const mahadashas: DashaPeriod[] = [];
  const sequence = lordSequence(birthLord);

  // The first mahadasha started before birth; its balance runs from birth.
  let cursor =
    birthUtc.getTime() - (birthLordYears - balanceYears) * MS_PER_YEAR;

  for (const planet of sequence) {
    const years = VIMSHOTTARI_YEARS[planet];
    const endMs = cursor + years * MS_PER_YEAR;

    mahadashas.push({
      level: "mahadasha",
      planet,
      start: new Date(cursor).toISOString(),
      end: new Date(endMs).toISOString(),
      children: buildSubPeriods(planet, cursor, years, "antardasha"),
    });

    cursor = endMs;
  }

  return {
    birthNakshatra: nakshatra.name,
    birthLord,
    balanceYears,
    mahadashas,
  };
}
