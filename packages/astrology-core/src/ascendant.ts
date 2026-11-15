import { greenwichSiderealDegrees, normalizeDegrees } from "./ephemeris";
import { julianDay } from "./time";

const DEG = Math.PI / 180;

/** Mean obliquity of the ecliptic (Meeus 22.2), in degrees. */
export function meanObliquity(date: Date): number {
  const t = (julianDay(date) - 2_451_545.0) / 36_525;
  return (
    23.43929111 -
    (46.815 * t + 0.00059 * t * t - 0.001813 * t * t * t) / 3_600
  );
}

/**
 * Tropical ascendant longitude for an instant and geographic position.
 *
 * RAMC is the local sidereal time in degrees. The atan2 form keeps the
 * ascendant in the correct semicircle without quadrant fix-ups.
 */
export function tropicalAscendant(
  date: Date,
  latitude: number,
  longitude: number,
): number {
  const ramc = normalizeDegrees(greenwichSiderealDegrees(date) + longitude);
  const epsilon = meanObliquity(date);

  const ascendant = Math.atan2(
    Math.cos(ramc * DEG),
    -(
      Math.sin(ramc * DEG) * Math.cos(epsilon * DEG) +
      Math.tan(latitude * DEG) * Math.sin(epsilon * DEG)
    ),
  );

  return normalizeDegrees(ascendant / DEG);
}
