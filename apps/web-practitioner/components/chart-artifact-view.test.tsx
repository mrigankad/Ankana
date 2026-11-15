import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { computeVedicChartArtifact } from "@astro/astrology-core";

import { ChartArtifactView } from "./chart-artifact-view";

const artifact = computeVedicChartArtifact({
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

afterEach(cleanup);

describe("ChartArtifactView", () => {
  it("renders the planetary position table for all nine grahas", () => {
    render(<ChartArtifactView artifact={artifact} />);

    expect(screen.getByText("Planetary Positions")).toBeInTheDocument();
    for (const planet of ["sun", "moon", "rahu", "ketu", "saturn"]) {
      expect(screen.getAllByText(planet).length).toBeGreaterThan(0);
    }
  });

  it("renders panchang, dasha timeline, and lagna", () => {
    render(<ChartArtifactView artifact={artifact} />);

    expect(screen.getByRole("heading", { name: "Panchang" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Dasha Timeline" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Lagna/ })).toBeInTheDocument();
    expect(screen.getAllByText(/mahadasha:/).length).toBe(9);
  });

  it("renders detected yogas with their evidence", () => {
    render(<ChartArtifactView artifact={artifact} />);

    expect(screen.getByText("Detected Yogas")).toBeInTheDocument();
    const present = artifact.yogas.filter((yoga) => yoga.present);
    for (const yoga of present) {
      expect(screen.getByText(yoga.name)).toBeInTheDocument();
    }
  });
});
