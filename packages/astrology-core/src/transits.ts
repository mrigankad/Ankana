import { toSidereal } from "./ayanamsa";
import type { Planet } from "./dignities";
import {
  isRetrograde,
  meanLunarNode,
  normalizeDegrees,
  tropicalLongitude,
  type EphemerisBody,
} from "./ephemeris";
import type { VedicChartArtifact } from "./chart";
import { NAKSHATRA_NAMES, SIGN_NAMES, signOf } from "./zodiac";

const TRANSIT_BODIES: EphemerisBody[] = [
  "sun",
  "moon",
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
];

/** Slow bodies worth tracking in a multi-year event timeline. */
const TIMELINE_BODIES: EphemerisBody[] = [
  "sun",
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
];

export interface TransitPlanetState {
  planet: Planet;
  siderealLongitude: number;
  signIndex: number;
  signName: string;
  retrograde: boolean;
  houseFromLagna: number;
  houseFromMoon: number;
  nakshatra: string;
}

export interface TransitSnapshot {
  date: string;
  planets: TransitPlanetState[];
  sadeSati: {
    active: boolean;
    phase: "rising" | "peak" | "setting" | null;
    evidence: string[];
  };
  jupiterSummary: { signName: string; houseFromMoon: number; evidence: string[] };
  nodesSummary: {
    rahuSign: string;
    ketuSign: string;
    rahuHouseFromLagna: number;
    evidence: string[];
  };
}

export interface TransitEvent {
  date: string;
  planet: Planet;
  kind: "ingress" | "retrograde-station" | "direct-station";
  detail: string;
}

function inclusiveCount(fromSign: number, toSign: number): number {
  return ((toSign - fromSign + 12) % 12) + 1;
}

function siderealOf(body: EphemerisBody, date: Date): number {
  return toSidereal(tropicalLongitude(body, date), date);
}

export function computeTransitSnapshot(
  natal: VedicChartArtifact,
  date: Date,
): TransitSnapshot {
  const natalAscSign = Math.floor(natal.ascendant.siderealLongitude / 30) % 12;
  const natalMoon = natal.planets.find((p) => p.planet === "moon")!;
  const natalMoonSign = natalMoon.signIndex;

  const states: TransitPlanetState[] = TRANSIT_BODIES.map((body) => {
    const lon = siderealOf(body, date);
    const sign = signOf(lon);
    return {
      planet: body,
      siderealLongitude: lon,
      signIndex: sign.index,
      signName: sign.name,
      retrograde: isRetrograde(body, date),
      houseFromLagna: inclusiveCount(natalAscSign, sign.index),
      houseFromMoon: inclusiveCount(natalMoonSign, sign.index),
      nakshatra: NAKSHATRA_NAMES[Math.floor(lon / (360 / 27)) % 27],
    };
  });

  const rahuLon = toSidereal(meanLunarNode(date), date);
  const ketuLon = normalizeDegrees(rahuLon + 180);
  const rahuSign = signOf(rahuLon);
  const ketuSign = signOf(ketuLon);

  for (const [planet, lon] of [
    ["rahu", rahuLon],
    ["ketu", ketuLon],
  ] as Array<[Planet, number]>) {
    const sign = signOf(lon);
    states.push({
      planet,
      siderealLongitude: lon,
      signIndex: sign.index,
      signName: sign.name,
      retrograde: true,
      houseFromLagna: inclusiveCount(natalAscSign, sign.index),
      houseFromMoon: inclusiveCount(natalMoonSign, sign.index),
      nakshatra: NAKSHATRA_NAMES[Math.floor(lon / (360 / 27)) % 27],
    });
  }

  const saturn = states.find((s) => s.planet === "saturn")!;
  const sadeSatiPhase =
    saturn.houseFromMoon === 12
      ? "rising"
      : saturn.houseFromMoon === 1
        ? "peak"
        : saturn.houseFromMoon === 2
          ? "setting"
          : null;

  const jupiter = states.find((s) => s.planet === "jupiter")!;

  return {
    date: date.toISOString(),
    planets: states,
    sadeSati: {
      active: sadeSatiPhase !== null,
      phase: sadeSatiPhase,
      evidence: [
        `Natal Moon in ${SIGN_NAMES[natalMoonSign]}.`,
        `Transit Saturn in ${saturn.signName}, house ${saturn.houseFromMoon} from the natal Moon.`,
        sadeSatiPhase
          ? `Saturn within the 12th-1st-2nd band from the Moon: sade sati ${sadeSatiPhase} phase.`
          : "Saturn outside the 12th-1st-2nd band from the Moon: no sade sati.",
      ],
    },
    jupiterSummary: {
      signName: jupiter.signName,
      houseFromMoon: jupiter.houseFromMoon,
      evidence: [
        `Transit Jupiter in ${jupiter.signName}, house ${jupiter.houseFromMoon} from the natal Moon.`,
      ],
    },
    nodesSummary: {
      rahuSign: rahuSign.name,
      ketuSign: ketuSign.name,
      rahuHouseFromLagna: inclusiveCount(natalAscSign, rahuSign.index),
      evidence: [
        `Transit Rahu in ${rahuSign.name}, Ketu in ${ketuSign.name}.`,
        `Rahu occupies house ${inclusiveCount(natalAscSign, rahuSign.index)} from the natal lagna.`,
      ],
    },
  };
}

const DAY_MS = 86_400_000;

/** Bisect a boundary crossing between two dates down to under an hour. */
function bisect(
  from: Date,
  to: Date,
  crossed: (date: Date) => boolean,
): Date {
  let low = from.getTime();
  let high = to.getTime();
  while (high - low > 3_600_000) {
    const mid = (low + high) / 2;
    if (crossed(new Date(mid))) {
      high = mid;
    } else {
      low = mid;
    }
  }
  return new Date(high);
}

export function computeTransitTimeline(
  from: Date,
  years: number,
): TransitEvent[] {
  const clampedYears = Math.min(Math.max(years, 0.1), 5);
  const end = new Date(from.getTime() + clampedYears * 365.2425 * DAY_MS);
  const events: TransitEvent[] = [];

  for (const body of TIMELINE_BODIES) {
    let cursor = new Date(from);
    let previousSign = Math.floor(siderealOf(body, cursor) / 30) % 12;
    let previousRetro = isRetrograde(body, cursor);

    while (cursor < end) {
      const next = new Date(Math.min(cursor.getTime() + DAY_MS, end.getTime()));
      const sign = Math.floor(siderealOf(body, next) / 30) % 12;
      const retro = isRetrograde(body, next);

      if (sign !== previousSign) {
        const boundary = previousSign;
        const at = bisect(
          cursor,
          next,
          (d) => Math.floor(siderealOf(body, d) / 30) % 12 !== boundary,
        );
        events.push({
          date: at.toISOString(),
          planet: body,
          kind: "ingress",
          detail: `${body} enters ${SIGN_NAMES[sign]}`,
        });
      }

      if (retro !== previousRetro) {
        events.push({
          date: next.toISOString(),
          planet: body,
          kind: retro ? "retrograde-station" : "direct-station",
          detail: retro
            ? `${body} turns retrograde in ${SIGN_NAMES[sign]}`
            : `${body} turns direct in ${SIGN_NAMES[sign]}`,
        });
      }

      previousSign = sign;
      previousRetro = retro;
      cursor = next;
    }
  }

  return events.sort((a, b) => a.date.localeCompare(b.date));
}
