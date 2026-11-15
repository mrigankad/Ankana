import { describe, expect, it } from "vitest";

import {
  greenwichSiderealDegrees,
  isRetrograde,
  meanLunarNode,
  tropicalLongitude,
} from "./ephemeris";

const J2000 = new Date("2000-01-01T12:00:00Z");

describe("tropicalLongitude", () => {
  it("matches the apparent solar longitude at J2000", () => {
    expect(tropicalLongitude("sun", J2000)).toBeCloseTo(280.37, 1);
  });

  it("returns values in [0, 360)", () => {
    for (const body of ["moon", "mercury", "venus", "mars", "jupiter", "saturn"] as const) {
      const lon = tropicalLongitude(body, J2000);
      expect(lon).toBeGreaterThanOrEqual(0);
      expect(lon).toBeLessThan(360);
    }
  });
});

describe("meanLunarNode", () => {
  it("matches the Meeus mean node at J2000", () => {
    expect(meanLunarNode(J2000)).toBeCloseTo(125.04, 1);
  });
});

describe("isRetrograde", () => {
  it("never reports the sun or moon retrograde", () => {
    expect(isRetrograde("sun", J2000)).toBe(false);
    expect(isRetrograde("moon", J2000)).toBe(false);
  });

  it("detects a known mercury retrograde window", () => {
    // Mercury was retrograde late Feb-March 2020.
    expect(isRetrograde("mercury", new Date("2020-02-25T00:00:00Z"))).toBe(true);
    expect(isRetrograde("mercury", new Date("2020-04-15T00:00:00Z"))).toBe(false);
  });
});

describe("greenwichSiderealDegrees", () => {
  it("matches the known GAST at J2000", () => {
    expect(greenwichSiderealDegrees(J2000)).toBeCloseTo(18.697136 * 15, 1);
  });
});
