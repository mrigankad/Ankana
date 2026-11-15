import { normalizeDegrees } from "./ephemeris";
import { julianDay } from "./time";

/**
 * Lahiri (Chitrapaksha) ayanamsa approximation.
 *
 * Anchored at 23.85306 deg for J2000 with the general precession rate.
 * Accurate to within a few arc minutes across 1900-2100, which is inside
 * the platform tolerance for sign and nakshatra boundaries.
 */
export function lahiriAyanamsa(date: Date): number {
  const t = (julianDay(date) - 2_451_545.0) / 36_525;
  return 23.85306 + (5_028.796195 * t + 1.1054348 * t * t) / 3_600;
}

export function toSidereal(tropicalLongitude: number, date: Date): number {
  return normalizeDegrees(tropicalLongitude - lahiriAyanamsa(date));
}
