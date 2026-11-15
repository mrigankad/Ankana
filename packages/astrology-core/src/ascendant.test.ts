import { Body, Observer, SearchRiseSet } from "astronomy-engine";
import { describe, expect, it } from "vitest";

import { meanObliquity, tropicalAscendant } from "./ascendant";
import { normalizeDegrees, tropicalLongitude } from "./ephemeris";
import { houseOf, wholeSignHouses } from "./houses";

function angularDistance(a: number, b: number): number {
  const diff = Math.abs(normalizeDegrees(a) - normalizeDegrees(b));
  return Math.min(diff, 360 - diff);
}

describe("meanObliquity", () => {
  it("is about 23.44 degrees at J2000", () => {
    expect(meanObliquity(new Date("2000-01-01T12:00:00Z"))).toBeCloseTo(23.439, 2);
  });
});

describe("tropicalAscendant", () => {
  it("equals the solar longitude at sunrise within tolerance", () => {
    const cases = [
      { lat: 25.3176, lon: 82.9739, date: new Date("1990-01-01T00:00:00Z") },
      { lat: 40.7128, lon: -74.006, date: new Date("2020-06-15T00:00:00Z") },
      { lat: -33.8688, lon: 151.2093, date: new Date("2015-03-20T00:00:00Z") },
    ];

    for (const { lat, lon, date } of cases) {
      const observer = new Observer(lat, lon, 0);
      const sunrise = SearchRiseSet(Body.Sun, observer, +1, date, 2);
      expect(sunrise).not.toBeNull();

      const sunriseDate = sunrise!.date;
      const ascendant = tropicalAscendant(sunriseDate, lat, lon);
      const sunLongitude = tropicalLongitude("sun", sunriseDate);

      expect(angularDistance(ascendant, sunLongitude)).toBeLessThan(2.5);
    }
  });

  it("advances roughly 30 degrees over two hours", () => {
    const start = new Date("2020-06-15T06:00:00Z");
    const later = new Date(start.getTime() + 2 * 3_600_000);

    const first = tropicalAscendant(start, 25.3176, 82.9739);
    const second = tropicalAscendant(later, 25.3176, 82.9739);

    const advance = normalizeDegrees(second - first);
    expect(advance).toBeGreaterThan(20);
    expect(advance).toBeLessThan(45);
  });
});

describe("wholeSignHouses", () => {
  it("starts house 1 at the ascendant sign and cycles", () => {
    const houses = wholeSignHouses(133.5); // Leo ascendant
    expect(houses[0].signName).toBe("Leo");
    expect(houses[0].lord).toBe("sun");
    expect(houses[11].signName).toBe("Cancer");
    expect(houses).toHaveLength(12);
  });
});

describe("houseOf", () => {
  it("places a body relative to the ascendant sign", () => {
    expect(houseOf(133.5, 133.5)).toBe(1); // Leo body, Leo asc
    expect(houseOf(0, 133.5)).toBe(9); // Aries body, Leo asc
  });
});
