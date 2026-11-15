import { tropicalAscendant } from "./ascendant";
import {
  computeAshtakavarga,
  computeSarvashtakavarga,
  type AshtakavargaResult,
} from "./ashtakavarga";
import { computeShadbala, type ShadbalaResult } from "./shadbala";
import { computeVimshopaka, type VimshopakaResult } from "./vimshopaka";
import { computeAspects, computeConjunctions, type Aspect, type Conjunction } from "./aspects";
import { lahiriAyanamsa, toSidereal } from "./ayanamsa";
import {
  computeVimshottari,
  type VimshottariDasha,
} from "./dasha-vimshottari";
import { computeYogini, type YoginiDasha } from "./dasha-yogini";
import {
  dignityOf,
  isCombust,
  type Dignity,
  type Planet,
} from "./dignities";
import {
  isRetrograde,
  meanLunarNode,
  normalizeDegrees,
  tropicalLongitude,
  type EphemerisBody,
} from "./ephemeris";
import { houseOf, wholeSignHouses, type House } from "./houses";
import { computePanchang, type Panchang } from "./panchang";
import { julianDay, toUtcDate } from "./time";
import { computeVargaCharts, type VargaChartSet } from "./vargas";
import { detectYogas, type YogaCategory, type YogaResult } from "./yogas";
import {
  boundaryWarnings,
  type BoundaryWarning,
} from "./boundaries";
import { nakshatraOf, signOf, type SignName } from "./zodiac";

export const ENGINE_VERSION = "0.1.0";
export type { BoundaryWarning };

export interface BirthDataInput {
  birthDate: string;
  birthTime: string;
  timezoneName: string;
  latitude: number;
  longitude: number;
  placeLabel?: string;
}

export interface PlanetState {
  planet: Planet;
  siderealLongitude: number;
  signIndex: number;
  signName: SignName;
  degreesInSign: number;
  nakshatra: string;
  pada: number;
  house: number;
  dignity: Dignity;
  retrograde: boolean;
  combust: boolean;
}

export interface VedicChartArtifact {
  calculationMetadata: {
    engineVersion: string;
    system: "vedic";
    ayanamsa: { name: "lahiri"; value: number };
    utcDateTime: string;
    julianDay: number;
    input: BirthDataInput;
  };
  ascendant: {
    siderealLongitude: number;
    signIndex: number;
    signName: SignName;
    degreesInSign: number;
    nakshatra: string;
    pada: number;
  };
  planets: PlanetState[];
  houses: Array<House & { occupants: Planet[] }>;
  panchang: Panchang;
  vargas: VargaChartSet;
  vimshottari: VimshottariDasha;
  yoginiDasha: YoginiDasha;
  yogas: YogaResult[];
  aspects: Aspect[];
  conjunctions: Conjunction[];
  strengthMetrics: {
    shadbala: ShadbalaResult[];
    ashtakavarga: AshtakavargaResult[];
    sarvashtakavarga: number[];
    vimshopaka: VimshopakaResult[];
  };
  /** Bodies within 0.1° of a sign/nakshatra/pada cusp. */
  boundaryWarnings: BoundaryWarning[];
}

const SEVEN_BODIES: EphemerisBody[] = [
  "sun",
  "moon",
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
];

export function computeVedicChartArtifact(
  input: BirthDataInput,
): VedicChartArtifact {
  const utc = toUtcDate(input.birthDate, input.birthTime, input.timezoneName);
  const ayanamsaValue = lahiriAyanamsa(utc);

  const tropical: Record<Planet, number> = {} as Record<Planet, number>;
  for (const body of SEVEN_BODIES) {
    tropical[body] = tropicalLongitude(body, utc);
  }
  tropical.rahu = meanLunarNode(utc);
  tropical.ketu = normalizeDegrees(tropical.rahu + 180);

  const sidereal = Object.fromEntries(
    Object.entries(tropical).map(([planet, lon]) => [
      planet,
      toSidereal(lon, utc),
    ]),
  ) as Record<Planet, number>;

  const ascTropical = tropicalAscendant(utc, input.latitude, input.longitude);
  const ascSidereal = toSidereal(ascTropical, utc);
  const ascSign = signOf(ascSidereal);
  const ascNakshatra = nakshatraOf(ascSidereal);

  const planets: PlanetState[] = (Object.keys(sidereal) as Planet[]).map(
    (planet) => {
      const lon = sidereal[planet];
      const sign = signOf(lon);
      const nakshatra = nakshatraOf(lon);
      const retrograde =
        planet === "rahu" || planet === "ketu"
          ? true
          : isRetrograde(planet as EphemerisBody, utc);

      return {
        planet,
        siderealLongitude: lon,
        signIndex: sign.index,
        signName: sign.name,
        degreesInSign: sign.degreesInSign,
        nakshatra: nakshatra.name,
        pada: nakshatra.pada,
        house: houseOf(lon, ascSidereal),
        dignity: dignityOf(planet, lon),
        retrograde,
        combust:
          planet === "sun"
            ? false
            : isCombust(planet, tropical[planet], tropical.sun, retrograde),
      };
    },
  );

  const houses = wholeSignHouses(ascSidereal).map((house) => ({
    ...house,
    occupants: planets
      .filter((p) => p.house === house.number)
      .map((p) => p.planet),
  }));

  const planetSigns = Object.fromEntries(
    planets.map((p) => [p.planet, p.signIndex]),
  ) as Record<Planet, number>;

  // Vara runs sunrise to sunrise; local calendar weekday is the v1
  // approximation (documented limitation for births before sunrise).
  const localWeekday = new Date(
    utc.toLocaleString("en-US", { timeZone: input.timezoneName }),
  ).getDay();

  return {
    calculationMetadata: {
      engineVersion: ENGINE_VERSION,
      system: "vedic",
      ayanamsa: { name: "lahiri", value: ayanamsaValue },
      utcDateTime: utc.toISOString(),
      julianDay: julianDay(utc),
      input,
    },
    ascendant: {
      siderealLongitude: ascSidereal,
      signIndex: ascSign.index,
      signName: ascSign.name,
      degreesInSign: ascSign.degreesInSign,
      nakshatra: ascNakshatra.name,
      pada: ascNakshatra.pada,
    },
    planets,
    houses,
    panchang: computePanchang(sidereal.sun, sidereal.moon, localWeekday),
    vargas: computeVargaCharts(sidereal, ascSidereal),
    vimshottari: computeVimshottari(sidereal.moon, utc),
    yoginiDasha: computeYogini(sidereal.moon, utc),
    yogas: detectYogas({
      longitudes: sidereal,
      signs: planetSigns,
      ascendantSign: ascSign.index,
      dignities: Object.fromEntries(
        planets.map((p) => [p.planet, p.dignity]),
      ) as Record<Planet, import("./dignities").Dignity>,
      houseLords: houses.map((h) => h.lord as Planet),
    }),
    aspects: computeAspects(planetSigns),
    conjunctions: computeConjunctions(planetSigns),
    strengthMetrics: (() => {
      const sunState = planets.find((p) => p.planet === "sun")!;
      const ashtakavarga = computeAshtakavarga({
        signs: planetSigns,
        ascendantSign: ascSign.index,
      });

      return {
        shadbala: computeShadbala({
          longitudes: sidereal,
          ascendantLongitude: ascSidereal,
          moonSunElongation: normalizeDegrees(sidereal.moon - sidereal.sun),
          retrograde: Object.fromEntries(
            planets.map((p) => [p.planet, p.retrograde]),
          ) as Record<Planet, boolean>,
          // Sun in houses 7-12 (whole sign) approximates a day birth.
          isDayBirth: sunState.house >= 7,
        }),
        ashtakavarga,
        sarvashtakavarga: computeSarvashtakavarga(ashtakavarga),
        vimshopaka: computeVimshopaka(sidereal),
      };
    })(),
    boundaryWarnings: boundaryWarnings(sidereal, ascSidereal),
  };
}
