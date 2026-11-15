import { computeVedicChartArtifact } from "@astro/astrology-core";
import { describe, expect, it } from "vitest";

import { evaluateRemedies, isFunctionalBenefic } from "./remedies";

const artifact = computeVedicChartArtifact({
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

describe("isFunctionalBenefic", () => {
  it("requires trikona lordship for this lagna", () => {
    // For every planet the verdict must match the house data directly.
    for (const planet of ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn"]) {
      const owned = artifact.houses
        .filter((h) => h.lord === planet)
        .map((h) => h.number);
      const expected =
        owned.some((h) => [1, 5, 9].includes(h)) &&
        !owned.every((h) => [6, 8, 12].includes(h));
      expect(isFunctionalBenefic(planet, artifact)).toBe(expected);
    }
  });

  it("never marks the nodes functional benefics", () => {
    expect(isFunctionalBenefic("rahu", artifact)).toBe(false);
    expect(isFunctionalBenefic("ketu", artifact)).toBe(false);
  });
});

describe("evaluateRemedies", () => {
  const remedies = evaluateRemedies(artifact);

  it("produces remedies only for weak or afflicted planets", () => {
    expect(remedies.length).toBeGreaterThan(0);
    const ratioOf = new Map(
      artifact.strengthMetrics.shadbala.map((r) => [r.planet as string, r.ratio]),
    );
    for (const remedy of remedies) {
      const state = artifact.planets.find((p) => p.planet === remedy.planet)!;
      const ratio = ratioOf.get(remedy.planet);
      const weak = ratio !== undefined && ratio < 1;
      const afflicted =
        state.combust ||
        state.dignity === "debilitated" ||
        state.dignity === "enemy";
      const nodeInDusthana =
        (remedy.planet === "rahu" || remedy.planet === "ketu") &&
        [6, 8, 12].includes(state.house);
      expect(weak || afflicted || nodeInDusthana).toBe(true);
    }
  });

  it("enforces the gemstone gate", () => {
    for (const remedy of remedies.filter((r) => r.kind === "gemstone")) {
      const state = artifact.planets.find((p) => p.planet === remedy.planet)!;
      expect(isFunctionalBenefic(remedy.planet, artifact)).toBe(true);
      expect(state.combust).toBe(false);
      expect(state.dignity).not.toBe("debilitated");
    }
  });

  it("never emits a gemstone or rudraksha without cautions", () => {
    for (const remedy of remedies) {
      if (remedy.kind === "gemstone" || remedy.kind === "rudraksha") {
        expect(remedy.cautions.length).toBeGreaterThan(0);
      }
    }
  });

  it("attaches evidence and rationale to every remedy", () => {
    for (const remedy of remedies) {
      expect(remedy.evidence.length).toBeGreaterThan(0);
      expect(remedy.rationale.length).toBeGreaterThan(0);
      expect(remedy.practice.length).toBeGreaterThan(0);
    }
  });

  it("always offers a safe mantra path for every remedied planet", () => {
    const planetsWithRemedies = new Set(remedies.map((r) => r.planet));
    for (const planet of planetsWithRemedies) {
      expect(
        remedies.some((r) => r.planet === planet && r.kind === "mantra"),
      ).toBe(true);
    }
  });

  it("is deterministic", () => {
    expect(evaluateRemedies(artifact)).toEqual(remedies);
  });
});
