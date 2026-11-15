import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { computeVedicChartArtifact } from "@astro/astrology-core";

import { KundaliChart } from "./kundali-chart";

const artifact = computeVedicChartArtifact({
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

afterEach(cleanup);

describe("KundaliChart", () => {
  it("renders an accessible North Indian chart with the lagna marked", () => {
    render(<KundaliChart artifact={artifact} />);

    expect(
      screen.getByRole("img", {
        name: `North Indian rashi chart with ${artifact.ascendant.signName} lagna`,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("La")).toBeInTheDocument();
  });

  it("places every occupied house's planets on the diagram", () => {
    const { container } = render(<KundaliChart artifact={artifact} />);
    const text = container.textContent ?? "";

    // All nine grahas appear as abbreviations somewhere on the diagram.
    for (const abbrev of ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]) {
      expect(text).toContain(abbrev);
    }
  });
});
