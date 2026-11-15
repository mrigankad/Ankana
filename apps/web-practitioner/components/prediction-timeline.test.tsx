import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { EnrichedPrediction } from "@astro/rule-engine";

import { PredictionTimeline } from "./prediction-timeline";

const SAMPLE: EnrichedPrediction[] = [
  {
    domain: "career",
    window: { start: "2026-01-01T00:00:00.000Z", end: "2027-01-01T00:00:00.000Z" },
    headline: "career - rahu mahadasha / jupiter antardasha (2026-01-01 to 2027-01-01)",
    narrative:
      "This window carries both supportive and challenging indications - read them together rather than choosing one: Career gains through network and teaching.",
    effect: "mixed",
    confidence: 0.62,
    confidenceBand: "medium",
    confidenceDrivers: ["rahu Shadbala ratio 0.00", "jupiter Shadbala ratio 1.12"],
    tension: true,
    linkedRemedyPlanets: ["rahu"],
    evidence: ["rahu owns 10th via lagna (vedic-predictions@1)"],
    ruleIds: ["career-dasha-10th"],
  },
];

describe("PredictionTimeline", () => {
  it("shows headline, confidence band, tension, and linked remedies", () => {
    render(<PredictionTimeline predictions={SAMPLE} />);

    expect(
      screen.getByText(/career - rahu mahadasha \/ jupiter antardasha/),
    ).toBeTruthy();
    expect(screen.getByText(/medium · 62%/)).toBeTruthy();
    expect(screen.getByText("tension")).toBeTruthy();
    expect(screen.getByText(/Linked remedies for rahu/)).toBeTruthy();
    expect(
      screen.getByText(/read them together rather than choosing one/),
    ).toBeTruthy();
  });
});
