import { describe, expect, it } from "vitest";

import { computeVedicChartArtifact } from "./chart";

const VARANASI_BIRTH = {
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
};

describe("computeVedicChartArtifact", () => {
  const artifact = computeVedicChartArtifact(VARANASI_BIRTH);

  it("records reproducible calculation metadata", () => {
    expect(artifact.calculationMetadata.utcDateTime).toBe("1990-01-01T05:00:00.000Z");
    expect(artifact.calculationMetadata.ayanamsa.name).toBe("lahiri");
    expect(artifact.calculationMetadata.ayanamsa.value).toBeGreaterThan(23.6);
    expect(artifact.calculationMetadata.ayanamsa.value).toBeLessThan(23.95);
    expect(artifact.calculationMetadata.engineVersion).toBeTruthy();
  });

  it("places the Sun in sidereal Sagittarius on 1990-01-01", () => {
    const sun = artifact.planets.find((p) => p.planet === "sun")!;
    expect(sun.signName).toBe("Sagittarius");
    expect(sun.retrograde).toBe(false);
  });

  it("computes all nine grahas with houses, nakshatras, and dignities", () => {
    expect(artifact.planets).toHaveLength(9);
    for (const planet of artifact.planets) {
      expect(planet.house).toBeGreaterThanOrEqual(1);
      expect(planet.house).toBeLessThanOrEqual(12);
      expect(planet.nakshatra).toBeTruthy();
      expect(planet.pada).toBeGreaterThanOrEqual(1);
      expect(planet.pada).toBeLessThanOrEqual(4);
      expect(planet.dignity).toBeTruthy();
    }
  });

  it("keeps Rahu and Ketu exactly opposite", () => {
    const rahu = artifact.planets.find((p) => p.planet === "rahu")!;
    const ketu = artifact.planets.find((p) => p.planet === "ketu")!;
    const gap = Math.abs(rahu.siderealLongitude - ketu.siderealLongitude);
    expect(Math.min(gap, 360 - gap)).toBeCloseTo(180, 6);
  });

  it("builds 12 whole-sign houses whose occupants match planet houses", () => {
    expect(artifact.houses).toHaveLength(12);
    for (const house of artifact.houses) {
      for (const occupant of house.occupants) {
        const planet = artifact.planets.find((p) => p.planet === occupant)!;
        expect(planet.house).toBe(house.number);
      }
    }
  });

  it("covers 120 years of Vimshottari dasha starting around birth", () => {
    const mahadashas = artifact.vimshottari.mahadashas;
    expect(mahadashas).toHaveLength(9);

    const start = new Date(mahadashas[0].start).getTime();
    const birth = new Date("1990-01-01T05:00:00Z").getTime();
    expect(start).toBeLessThanOrEqual(birth);

    const end = new Date(mahadashas[8].end).getTime();
    const years = (end - start) / (365.2425 * 86_400_000);
    expect(years).toBeCloseTo(120, 2);
  });

  it("returns yogas with evidence and all nine vargas", () => {
    expect(artifact.yogas.length).toBeGreaterThanOrEqual(9);
    for (const yoga of artifact.yogas) {
      expect(yoga.evidence.length).toBeGreaterThan(0);
    }
    expect(Object.keys(artifact.vargas)).toContain("d9");
    expect(Object.keys(artifact.vargas)).toContain("d60");
  });

  it("is deterministic for identical input", () => {
    const again = computeVedicChartArtifact(VARANASI_BIRTH);
    expect(again).toEqual(artifact);
  });
});

describe("strengthMetrics", () => {
  const artifact = computeVedicChartArtifact(VARANASI_BIRTH);

  it("includes shadbala for all seven planets with positive ratios", () => {
    expect(artifact.strengthMetrics.shadbala).toHaveLength(7);
    for (const result of artifact.strengthMetrics.shadbala) {
      expect(result.totalRupas).toBeGreaterThan(0);
      expect(result.ratio).toBeGreaterThan(0);
    }
  });

  it("carries a classical sarvashtakavarga totalling 337", () => {
    const total = artifact.strengthMetrics.sarvashtakavarga.reduce(
      (a, b) => a + b,
      0,
    );
    expect(total).toBe(337);
  });

  it("scores vimshopaka within 0..20", () => {
    for (const { score } of artifact.strengthMetrics.vimshopaka) {
      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThanOrEqual(20);
    }
  });
});
