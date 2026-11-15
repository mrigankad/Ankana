import { isOddSign, signOf } from "./zodiac";

export const VARGA_KEYS = [
  "d1",
  "d2",
  "d3",
  "d7",
  "d9",
  "d10",
  "d12",
  "d30",
  "d60",
] as const;

export type VargaKey = (typeof VARGA_KEYS)[number];

const DIVISIONS: Record<VargaKey, number> = {
  d1: 1,
  d2: 2,
  d3: 3,
  d7: 7,
  d9: 9,
  d10: 10,
  d12: 12,
  d30: 30,
  d60: 60,
};

/** Trimsamsa spans: [toDegree, resultSign] applied in order. */
const TRIMSAMSA_ODD: Array<[number, number]> = [
  [5, 0], // Mars -> Aries
  [10, 10], // Saturn -> Aquarius
  [18, 8], // Jupiter -> Sagittarius
  [25, 2], // Mercury -> Gemini
  [30, 6], // Venus -> Libra
];

const TRIMSAMSA_EVEN: Array<[number, number]> = [
  [5, 1], // Venus -> Taurus
  [12, 5], // Mercury -> Virgo
  [20, 11], // Jupiter -> Pisces
  [25, 9], // Saturn -> Capricorn
  [30, 7], // Mars -> Scorpio
];

/** Sidereal longitude -> sign index (0-11) in the requested divisional chart. */
export function vargaSign(chart: VargaKey, siderealLongitude: number): number {
  const { index: sign, degreesInSign } = signOf(siderealLongitude);
  const part = Math.min(
    Math.floor(degreesInSign / (30 / DIVISIONS[chart])),
    DIVISIONS[chart] - 1,
  );

  switch (chart) {
    case "d1":
      return sign;
    case "d2": {
      // Odd signs: Leo then Cancer. Even signs: Cancer then Leo.
      const leoFirst = isOddSign(sign);
      const isFirstHalf = part === 0;
      return isFirstHalf === leoFirst ? 4 : 3;
    }
    case "d3":
      return (sign + part * 4) % 12; // same, 5th, 9th
    case "d7":
      return (sign * 7 + part) % 12;
    case "d9":
      return (sign * 9 + part) % 12;
    case "d10":
      return ((isOddSign(sign) ? sign : sign + 8) + part) % 12;
    case "d12":
      return (sign + part) % 12;
    case "d30": {
      const spans = isOddSign(sign) ? TRIMSAMSA_ODD : TRIMSAMSA_EVEN;
      for (const [toDegree, resultSign] of spans) {
        if (degreesInSign < toDegree) {
          return resultSign;
        }
      }
      return spans[spans.length - 1][1];
    }
    case "d60":
      return (sign + part) % 12;
  }
}

export interface VargaChartSet {
  [chart: string]: {
    ascendantSign: number;
    planets: Record<string, number>;
  };
}

export function computeVargaCharts(
  planetLongitudes: Record<string, number>,
  ascendantLongitude: number,
): VargaChartSet {
  const result: VargaChartSet = {};

  for (const chart of VARGA_KEYS) {
    const planets: Record<string, number> = {};
    for (const [planet, longitude] of Object.entries(planetLongitudes)) {
      planets[planet] = vargaSign(chart, longitude);
    }
    result[chart] = {
      ascendantSign: vargaSign(chart, ascendantLongitude),
      planets,
    };
  }

  return result;
}
