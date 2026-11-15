import { describe, expect, it } from "vitest";

import { lahiriAyanamsa, toSidereal } from "./ayanamsa";
import { nakshatraOf, signModality, signOf } from "./zodiac";

describe("lahiriAyanamsa", () => {
  it("is close to 23.85 degrees at J2000", () => {
    const value = lahiriAyanamsa(new Date("2000-01-01T12:00:00Z"));
    expect(value).toBeGreaterThan(23.8);
    expect(value).toBeLessThan(23.9);
  });

  it("is close to 24.13 degrees in 2020", () => {
    const value = lahiriAyanamsa(new Date("2020-01-01T00:00:00Z"));
    expect(value).toBeGreaterThan(24.08);
    expect(value).toBeLessThan(24.19);
  });

  it("subtracts from tropical longitude with wraparound", () => {
    const sidereal = toSidereal(10, new Date("2000-01-01T12:00:00Z"));
    expect(sidereal).toBeCloseTo(10 - 23.85306 + 360, 1);
  });
});

describe("signOf", () => {
  it("maps 0 degrees to Aries ruled by Mars", () => {
    const sign = signOf(0);
    expect(sign.name).toBe("Aries");
    expect(sign.lord).toBe("mars");
    expect(sign.degreesInSign).toBe(0);
  });

  it("maps 133.5 degrees to Leo", () => {
    const sign = signOf(133.5);
    expect(sign.name).toBe("Leo");
    expect(sign.degreesInSign).toBeCloseTo(13.5, 6);
  });
});

describe("nakshatraOf", () => {
  it("maps 0 degrees to Ashwini pada 1 ruled by Ketu", () => {
    const nakshatra = nakshatraOf(0);
    expect(nakshatra.name).toBe("Ashwini");
    expect(nakshatra.lord).toBe("ketu");
    expect(nakshatra.pada).toBe(1);
  });

  it("maps the Magha start boundary correctly", () => {
    const nakshatra = nakshatraOf(120);
    expect(nakshatra.name).toBe("Magha");
    expect(nakshatra.lord).toBe("ketu");
  });

  it("cycles lords in Vimshottari order", () => {
    expect(nakshatraOf(13.34).lord).toBe("venus"); // Bharani
    expect(nakshatraOf(27).lord).toBe("sun"); // Krittika
    expect(nakshatraOf(40.5).lord).toBe("moon"); // Rohini
  });

  it("computes pada within a nakshatra", () => {
    // 3deg20' per pada; 10 degrees into Ashwini is pada 4.
    expect(nakshatraOf(10.5).pada).toBe(4);
  });
});

describe("signModality", () => {
  it("classifies movable, fixed, and dual signs", () => {
    expect(signModality(0)).toBe("movable"); // Aries
    expect(signModality(1)).toBe("fixed"); // Taurus
    expect(signModality(2)).toBe("dual"); // Gemini
    expect(signModality(9)).toBe("movable"); // Capricorn
  });
});
