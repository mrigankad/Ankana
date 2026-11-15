// astronomy-engine ships CJS whose named exports are not statically
// analyzable under the Node ESM loader; import the module object instead.
import type { Body as AstronomyBody } from "astronomy-engine";
import * as astronomyModule from "astronomy-engine";

// Interop-safe unwrap: Node ESM exposes the CJS module as `default`,
// while bundler/vitest loaders expose named members directly.
const astronomy =
  ((astronomyModule as { default?: typeof astronomyModule }).default ??
    astronomyModule);

const { Body, Ecliptic, GeoVector, SiderealTime } = astronomy;

import { julianDay } from "./time";

export type EphemerisBody =
  | "sun"
  | "moon"
  | "mercury"
  | "venus"
  | "mars"
  | "jupiter"
  | "saturn";

const BODY_MAP: Record<EphemerisBody, AstronomyBody> = {
  sun: Body.Sun,
  moon: Body.Moon,
  mercury: Body.Mercury,
  venus: Body.Venus,
  mars: Body.Mars,
  jupiter: Body.Jupiter,
  saturn: Body.Saturn,
};

export function normalizeDegrees(value: number): number {
  return ((value % 360) + 360) % 360;
}

export function tropicalLongitude(body: EphemerisBody, date: Date): number {
  const vector = GeoVector(BODY_MAP[body], date, true);
  return normalizeDegrees(Ecliptic(vector).elon);
}

export function meanLunarNode(date: Date): number {
  const t = (julianDay(date) - 2_451_545.0) / 36_525;

  const omega =
    125.0445479 -
    1_934.1362891 * t +
    0.0020754 * t * t +
    (t * t * t) / 467_441 -
    (t * t * t * t) / 60_616_000;

  return normalizeDegrees(omega);
}

export function isRetrograde(body: EphemerisBody, date: Date): boolean {
  if (body === "sun" || body === "moon") {
    return false;
  }

  const hours = 6;
  const before = tropicalLongitude(
    body,
    new Date(date.getTime() - hours * 3_600_000),
  );
  const after = tropicalLongitude(
    body,
    new Date(date.getTime() + hours * 3_600_000),
  );

  const delta = normalizeDegrees(after - before);
  return delta > 180;
}

export function greenwichSiderealDegrees(date: Date): number {
  return normalizeDegrees(SiderealTime(date) * 15);
}
