import { signCount } from "./aspects";
import { dignityOf, type Dignity, type Planet } from "./dignities";
import { vargaSign } from "./vargas";
import { isOddSign, signOf } from "./zodiac";

export type ShadbalaPlanet =
  | "sun"
  | "moon"
  | "mars"
  | "mercury"
  | "jupiter"
  | "venus"
  | "saturn";

export const SHADBALA_PLANETS: ShadbalaPlanet[] = [
  "sun",
  "moon",
  "mars",
  "mercury",
  "jupiter",
  "venus",
  "saturn",
];

/** Deep-debilitation longitudes (uccha bala measures distance from these). */
const DEBILITATION_POINT: Record<ShadbalaPlanet, number> = {
  sun: 190, // 10 Libra
  moon: 213, // 3 Scorpio
  mars: 118, // 28 Cancer
  mercury: 345, // 15 Pisces
  jupiter: 275, // 5 Capricorn
  venus: 177, // 27 Virgo
  saturn: 20, // 20 Aries
};

/** Naisargika (natural) strength in virupas, fixed by BPHS. */
const NAISARGIKA: Record<ShadbalaPlanet, number> = {
  sun: 60,
  moon: 51.43,
  venus: 42.86,
  jupiter: 34.29,
  mercury: 25.71,
  mars: 17.14,
  saturn: 8.57,
};

/** House where each planet gains full directional strength. */
const DIG_BALA_HOUSE: Record<ShadbalaPlanet, number> = {
  jupiter: 1,
  mercury: 1,
  sun: 10,
  mars: 10,
  saturn: 7,
  moon: 4,
  venus: 4,
};

/** Classical minimum requirements in rupas (1 rupa = 60 virupas). */
const REQUIRED_RUPAS: Record<ShadbalaPlanet, number> = {
  sun: 5,
  moon: 6,
  mars: 5,
  mercury: 7,
  jupiter: 6.5,
  venus: 5.5,
  saturn: 5,
};

const DIGNITY_VIRUPAS: Record<Dignity, number> = {
  exalted: 30,
  moolatrikona: 25,
  own: 20,
  friend: 15,
  neutral: 10,
  enemy: 5,
  debilitated: 2,
};

export interface ShadbalaInput {
  /** Sidereal longitudes for the seven classical planets. */
  longitudes: Record<Planet, number>;
  ascendantLongitude: number;
  /** Moon-Sun elongation in degrees (for paksha bala). */
  moonSunElongation: number;
  /** Retrograde flags per planet. */
  retrograde: Record<Planet, boolean>;
  /** True if the Sun is above the horizon houses (7th-12th from lagna). */
  isDayBirth: boolean;
}

export interface ShadbalaResult {
  planet: ShadbalaPlanet;
  sthana: number;
  dig: number;
  kala: number;
  cheshta: number;
  naisargika: number;
  drik: number;
  totalVirupas: number;
  totalRupas: number;
  requiredRupas: number;
  ratio: number;
}

/**
 * Simplified Shadbala. Implements the dominant classical terms exactly
 * (uccha, kendradi, ojayugma, dig, naisargika, paksha, nathonnatha) and
 * substitutes documented neutral values where the full BPHS term needs
 * data outside the current artifact (drekkana, abda/masa/vara/hora
 * kala sub-balas, graha yuddha). Results are comparative, not tenths-of-
 * virupa accurate; the ratio ordering is the product-facing contract.
 */
export function computeShadbala(input: ShadbalaInput): ShadbalaResult[] {
  const ascSign = signOf(input.ascendantLongitude).index;

  return SHADBALA_PLANETS.map((planet) => {
    const lon = input.longitudes[planet];
    const sign = signOf(lon).index;

    // ── Sthana bala ──────────────────────────────────────────────
    // Uccha bala: 0 at deep debilitation, 60 at deep exaltation.
    const distance = Math.abs(
      (((lon - DEBILITATION_POINT[planet]) % 360) + 360) % 360,
    );
    const arc = distance > 180 ? 360 - distance : distance;
    const uccha = arc / 3;

    // Kendradi bala: kendra 60, panapara 30, apoklima 15.
    const house = signCount(ascSign, sign);
    const kendradi = [1, 4, 7, 10].includes(house)
      ? 60
      : [2, 5, 8, 11].includes(house)
        ? 30
        : 15;

    // Ojayugma: Moon and Venus favor even signs, the rest odd (D1 + D9).
    const prefersEven = planet === "moon" || planet === "venus";
    const d9 = vargaSign("d9", lon);
    let ojayugma = 0;
    if (isOddSign(sign) !== prefersEven) ojayugma += 15;
    if (isOddSign(d9) !== prefersEven) ojayugma += 15;

    // Saptavargaja simplified to D1 + D9 dignity contributions.
    const saptavargaja =
      DIGNITY_VIRUPAS[dignityOf(planet, lon)] +
      DIGNITY_VIRUPAS[dignityOf(planet, d9 * 30 + 15)];

    const sthana = uccha + kendradi + ojayugma + saptavargaja;

    // ── Dig bala: 60 at the power house cusp, 0 opposite. ───────
    const powerHouse = DIG_BALA_HOUSE[planet];
    const houseGap = Math.min(
      Math.abs(house - powerHouse),
      12 - Math.abs(house - powerHouse),
    );
    const dig = 60 * (1 - houseGap / 6);

    // ── Kala bala (simplified) ───────────────────────────────────
    // Nathonnatha: Moon/Mars/Saturn strong at night, Sun/Jupiter/Venus
    // by day, Mercury always strong.
    const dayStrong = planet === "sun" || planet === "jupiter" || planet === "venus";
    const nathonnatha =
      planet === "mercury" ? 60 : (input.isDayBirth === dayStrong ? 60 : 0);

    // Paksha bala: benefics wax with the Moon, malefics wane.
    const elongationArc =
      input.moonSunElongation > 180
        ? 360 - input.moonSunElongation
        : input.moonSunElongation;
    const pakshaBenefic = elongationArc / 3;
    const benefic = planet === "moon" || planet === "mercury" ||
      planet === "jupiter" || planet === "venus";
    const paksha = benefic ? pakshaBenefic : 60 - pakshaBenefic;

    // Remaining kala sub-balas held neutral (documented simplification).
    const kalaNeutral = 30;
    const kala = nathonnatha + paksha + kalaNeutral;

    // ── Cheshta bala (simplified motion strength) ────────────────
    const cheshta =
      planet === "sun" || planet === "moon"
        ? 30
        : input.retrograde[planet]
          ? 60
          : 30;

    // ── Drik bala held neutral (sign-aspect model too coarse). ──
    const drik = 0;

    const totalVirupas =
      sthana + dig + kala + cheshta + NAISARGIKA[planet] + drik;
    const totalRupas = totalVirupas / 60;

    return {
      planet,
      sthana,
      dig,
      kala,
      cheshta,
      naisargika: NAISARGIKA[planet],
      drik,
      totalVirupas,
      totalRupas,
      requiredRupas: REQUIRED_RUPAS[planet],
      ratio: totalRupas / REQUIRED_RUPAS[planet],
    };
  });
}
