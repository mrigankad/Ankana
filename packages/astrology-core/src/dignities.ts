import { normalizeDegrees } from "./ephemeris";
import { signOf } from "./zodiac";

export type Planet =
  | "sun"
  | "moon"
  | "mercury"
  | "venus"
  | "mars"
  | "jupiter"
  | "saturn"
  | "rahu"
  | "ketu";

export type Dignity =
  | "exalted"
  | "moolatrikona"
  | "own"
  | "friend"
  | "neutral"
  | "enemy"
  | "debilitated";

interface DignityRow {
  exaltationSign: number;
  ownSigns: number[];
  /** [signIndex, fromDegree, toDegree] */
  moolatrikona: [number, number, number] | null;
}

const DIGNITY_TABLE: Record<Exclude<Planet, "rahu" | "ketu">, DignityRow> = {
  sun: { exaltationSign: 0, ownSigns: [4], moolatrikona: [4, 0, 20] },
  moon: { exaltationSign: 1, ownSigns: [3], moolatrikona: [1, 3, 30] },
  mars: { exaltationSign: 9, ownSigns: [0, 7], moolatrikona: [0, 0, 12] },
  mercury: { exaltationSign: 5, ownSigns: [2, 5], moolatrikona: [5, 15, 20] },
  jupiter: { exaltationSign: 3, ownSigns: [8, 11], moolatrikona: [8, 0, 10] },
  venus: { exaltationSign: 11, ownSigns: [1, 6], moolatrikona: [6, 0, 15] },
  saturn: { exaltationSign: 6, ownSigns: [9, 10], moolatrikona: [10, 0, 20] },
};

/** Naisargika (natural) friendships. */
const FRIENDS: Record<Exclude<Planet, "rahu" | "ketu">, Planet[]> = {
  sun: ["moon", "mars", "jupiter"],
  moon: ["sun", "mercury"],
  mars: ["sun", "moon", "jupiter"],
  mercury: ["sun", "venus"],
  jupiter: ["sun", "moon", "mars"],
  venus: ["mercury", "saturn"],
  saturn: ["mercury", "venus"],
};

const ENEMIES: Record<Exclude<Planet, "rahu" | "ketu">, Planet[]> = {
  sun: ["venus", "saturn"],
  moon: [],
  mars: ["mercury"],
  mercury: ["moon"],
  jupiter: ["mercury", "venus"],
  venus: ["sun", "moon"],
  saturn: ["sun", "moon", "mars"],
};

const SIGN_LORD_PLANETS: Planet[] = [
  "mars",
  "venus",
  "mercury",
  "moon",
  "sun",
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
  "saturn",
  "jupiter",
];

export function dignityOf(planet: Planet, siderealLongitude: number): Dignity {
  if (planet === "rahu" || planet === "ketu") {
    // Nodes have no classical dignity scheme in v1; treated as neutral.
    return "neutral";
  }

  const row = DIGNITY_TABLE[planet];
  const sign = signOf(siderealLongitude);
  const debilitationSign = (row.exaltationSign + 6) % 12;

  if (sign.index === row.exaltationSign) {
    return "exalted";
  }
  if (sign.index === debilitationSign) {
    return "debilitated";
  }
  if (
    row.moolatrikona &&
    sign.index === row.moolatrikona[0] &&
    sign.degreesInSign >= row.moolatrikona[1] &&
    sign.degreesInSign < row.moolatrikona[2]
  ) {
    return "moolatrikona";
  }
  if (row.ownSigns.includes(sign.index)) {
    return "own";
  }

  const dispositor = SIGN_LORD_PLANETS[sign.index];
  if (dispositor === planet) {
    return "own";
  }
  if (FRIENDS[planet].includes(dispositor)) {
    return "friend";
  }
  if (ENEMIES[planet].includes(dispositor)) {
    return "enemy";
  }
  return "neutral";
}

/** Classical combustion orbs in degrees from the Sun. */
const COMBUSTION_ORBS: Partial<Record<Planet, { direct: number; retrograde: number }>> = {
  moon: { direct: 12, retrograde: 12 },
  mars: { direct: 17, retrograde: 17 },
  mercury: { direct: 14, retrograde: 12 },
  jupiter: { direct: 11, retrograde: 11 },
  venus: { direct: 10, retrograde: 8 },
  saturn: { direct: 15, retrograde: 15 },
};

export function isCombust(
  planet: Planet,
  planetTropicalLongitude: number,
  sunTropicalLongitude: number,
  retrograde: boolean,
): boolean {
  const orbs = COMBUSTION_ORBS[planet];
  if (!orbs) {
    return false;
  }

  const separation = Math.min(
    normalizeDegrees(planetTropicalLongitude - sunTropicalLongitude),
    normalizeDegrees(sunTropicalLongitude - planetTropicalLongitude),
  );

  return separation <= (retrograde ? orbs.retrograde : orbs.direct);
}
