import { computeVedicChartArtifact } from "@astro/astrology-core";
import { describe, expect, it } from "vitest";

import { evaluatePredictions } from "./evaluator";
import { VEDIC_PREDICTION_RULES } from "./packs/vedic-predictions";

const artifact = computeVedicChartArtifact({
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

const FROM = new Date("2026-07-09T00:00:00Z");

describe("rule pack", () => {
  it("ships at least 30 rules, all with sources and weights", () => {
    expect(VEDIC_PREDICTION_RULES.length).toBeGreaterThanOrEqual(30);
    for (const rule of VEDIC_PREDICTION_RULES) {
      expect(rule.source.length).toBeGreaterThan(0);
      expect(rule.weight).toBeGreaterThan(0);
      expect(rule.when.length).toBeGreaterThan(0);
    }
  });

  it("has unique rule ids", () => {
    const ids = VEDIC_PREDICTION_RULES.map((r) => r.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("evaluatePredictions", () => {
  const predictions = evaluatePredictions(artifact, {
    from: FROM,
    horizonYears: 5,
  });

  it("produces dated predictions inside the horizon", () => {
    expect(predictions.length).toBeGreaterThan(0);
    const until = FROM.getTime() + 5.1 * 365.2425 * 86_400_000;
    for (const prediction of predictions) {
      expect(new Date(prediction.window.end).getTime()).toBeGreaterThan(
        FROM.getTime(),
      );
      expect(new Date(prediction.window.start).getTime()).toBeLessThan(until);
    }
  });

  it("attaches evidence and rule ids to every prediction", () => {
    for (const prediction of predictions) {
      expect(prediction.evidence.length).toBeGreaterThan(0);
      expect(prediction.ruleIds.length).toBeGreaterThan(0);
      expect(prediction.narrative.length).toBeGreaterThan(0);
    }
  });

  it("bounds confidence to [0.05, 0.95]", () => {
    for (const prediction of predictions) {
      expect(prediction.confidence).toBeGreaterThanOrEqual(0.05);
      expect(prediction.confidence).toBeLessThanOrEqual(0.95);
    }
  });

  it("respects the domain filter", () => {
    // Pick a domain that actually fires for this chart.
    const firingDomain = predictions[0]!.domain;
    const filtered = evaluatePredictions(artifact, {
      from: FROM,
      horizonYears: 5,
      domains: [firingDomain],
    });
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((p) => p.domain === firingDomain)).toBe(true);
    expect(filtered).toEqual(
      predictions.filter((p) => p.domain === firingDomain),
    );
  });

  it("orders predictions chronologically", () => {
    const starts = predictions.map((p) => p.window.start);
    expect([...starts].sort()).toEqual(starts);
  });

  it("is deterministic", () => {
    const again = evaluatePredictions(artifact, { from: FROM, horizonYears: 5 });
    expect(again).toEqual(predictions);
  });

  it("substitutes template placeholders in narratives", () => {
    for (const prediction of predictions) {
      expect(prediction.narrative).not.toContain("{level}");
      expect(prediction.narrative).not.toContain("{lord}");
    }
  });
});
