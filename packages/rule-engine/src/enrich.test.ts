import { computeVedicChartArtifact } from "@astro/astrology-core";
import { describe, expect, it } from "vitest";

import { evaluatePredictionsEnriched } from "./enrich";

const artifact = computeVedicChartArtifact({
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

const FROM = new Date("2026-07-09T00:00:00Z");

describe("evaluatePredictionsEnriched", () => {
  const predictions = evaluatePredictionsEnriched(artifact, {
    from: FROM,
    horizonYears: 5,
  });

  it("adds a confidence band to every prediction", () => {
    expect(predictions.length).toBeGreaterThan(0);
    for (const prediction of predictions) {
      expect(["low", "medium", "high"]).toContain(prediction.confidenceBand);
      if (prediction.confidence >= 0.7) {
        expect(prediction.confidenceBand).toBe("high");
      } else if (prediction.confidence >= 0.4) {
        expect(prediction.confidenceBand).toBe("medium");
      } else {
        expect(prediction.confidenceBand).toBe("low");
      }
    }
  });

  it("flags tension and prefixes narrative on mixed windows", () => {
    const mixed = predictions.filter((p) => p.effect === "mixed");
    for (const prediction of mixed) {
      expect(prediction.tension).toBe(true);
      expect(prediction.narrative).toMatch(/^This window carries both/);
    }
  });

  it("attaches shadbala drivers when window lords have strength rows", () => {
    const withDrivers = predictions.filter((p) => p.confidenceDrivers?.length);
    expect(withDrivers.length).toBeGreaterThan(0);
    for (const prediction of withDrivers) {
      for (const driver of prediction.confidenceDrivers!) {
        expect(driver).toMatch(/Shadbala ratio \d+\.\d{2}/);
      }
    }
  });

  it("is deterministic", () => {
    expect(
      evaluatePredictionsEnriched(artifact, { from: FROM, horizonYears: 5 }),
    ).toEqual(predictions);
  });
});
