import type { DashaPeriod } from "./dasha-vimshottari";
import { nakshatraOf } from "./zodiac";

/** The eight yoginis in sequence with their lords and years (36y cycle). */
export const YOGINIS = [
  { name: "Mangala", planet: "moon", years: 1 },
  { name: "Pingala", planet: "sun", years: 2 },
  { name: "Dhanya", planet: "jupiter", years: 3 },
  { name: "Bhramari", planet: "mars", years: 4 },
  { name: "Bhadrika", planet: "mercury", years: 5 },
  { name: "Ulka", planet: "saturn", years: 6 },
  { name: "Siddha", planet: "venus", years: 7 },
  { name: "Sankata", planet: "rahu", years: 8 },
] as const;

export const YOGINI_CYCLE_YEARS = 36;

const MS_PER_YEAR = 365.2425 * 86_400_000;

export interface YoginiDasha {
  birthNakshatra: string;
  birthYogini: string;
  balanceYears: number;
  /** Two full 36-year cycles of mahadashas with antardashas. */
  mahadashas: DashaPeriod[];
}

/**
 * Yogini dasha. Starting yogini index follows the classical rule
 * (nakshatra number + 3) mod 8, mapping remainder 1..8 onto
 * Mangala..Sankata; balance is the untraversed fraction of that
 * yogini's span.
 */
export function computeYogini(
  moonSiderealLongitude: number,
  birthUtc: Date,
): YoginiDasha {
  const nakshatra = nakshatraOf(moonSiderealLongitude);
  const nakshatraNumber = nakshatra.index + 1; // 1-based
  const remainder = (nakshatraNumber + 3) % 8;
  const startIndex = (remainder === 0 ? 8 : remainder) - 1; // 0-based

  const startYogini = YOGINIS[startIndex];
  const balanceYears = startYogini.years * (1 - nakshatra.fractionTraversed);

  const mahadashas: DashaPeriod[] = [];
  let cursor =
    birthUtc.getTime() - (startYogini.years - balanceYears) * MS_PER_YEAR;

  // Two full cycles = 72 years of coverage from the birth yogini.
  for (let i = 0; i < 16; i += 1) {
    const yogini = YOGINIS[(startIndex + i) % 8];
    const endMs = cursor + yogini.years * MS_PER_YEAR;

    const children: DashaPeriod[] = [];
    let subCursor = cursor;
    for (let j = 0; j < 8; j += 1) {
      // Antardashas run in sequence from the mahadasha's own yogini,
      // each proportional to its years within the 36-year total.
      const sub = YOGINIS[((startIndex + i) % 8 + j) % 8];
      const subYears = (yogini.years * sub.years) / YOGINI_CYCLE_YEARS;
      const subEnd = subCursor + subYears * MS_PER_YEAR;
      children.push({
        level: "antardasha",
        planet: sub.planet,
        name: sub.name,
        start: new Date(subCursor).toISOString(),
        end: new Date(subEnd).toISOString(),
      });
      subCursor = subEnd;
    }

    mahadashas.push({
      level: "mahadasha",
      planet: yogini.planet,
      name: yogini.name,
      start: new Date(cursor).toISOString(),
      end: new Date(endMs).toISOString(),
      children,
    });
    cursor = endMs;
  }

  return {
    birthNakshatra: nakshatra.name,
    birthYogini: startYogini.name,
    balanceYears,
    mahadashas,
  };
}
