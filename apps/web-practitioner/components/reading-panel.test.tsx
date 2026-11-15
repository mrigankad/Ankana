import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { ReadingPanel, type ChartReading } from "./reading-panel";

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  window.localStorage.clear();
});


const SAMPLE: ChartReading = {
  generatedAt: "2026-07-19T00:00:00.000Z",
  engineVersion: "py-1.0.0",
  sections: [
    {
      key: "lagna",
      title: "Lagna & temperament",
      items: [
        {
          title: "Scorpio Lagna - temperament and life direction",
          text: "The lagna rises in Scorpio within Anuradha nakshatra pada 4, colouring the personality.",
          evidence: [
            "Ascendant Scorpio 12.00 deg, Anuradha pada 4.",
            "Lagna lord mars in house 4 (Aquarius, friend).",
          ],
        },
      ],
    },
  ],
  lifeStory: {
    generatedAt: "2026-07-19T00:00:00.000Z",
    birthDate: "2003-08-29",
    currentAgeYears: 22,
    lenses: {
      hybrid: [
        {
          key: "hybrid-childhood",
          title: "Childhood (0–12) · Sun / Moon",
          ageRange: { from: 0, to: 12 },
          years: { start: "2003-08-29", end: "2016-08-29" },
          dashas: [
            {
              planet: "sun",
              level: "mahadasha",
              start: "2001-03-26T00:00:00.000Z",
              end: "2007-03-27T00:00:00.000Z",
              ageFrom: 0,
              ageTo: 3.6,
            },
          ],
          summary:
            "Across Sun and Moon years, Childhood (ages 0-12) highlights home, care, and temperament.",
          items: [
            {
              title: "Temperament through-line",
              text: "Across every chapter, the Scorpio lagna sets the temperament through-line.",
              evidence: ["Ascendant Scorpio, Anuradha pada 4."],
            },
          ],
          isCurrent: false,
        },
      ],
      ageBands: [
        {
          key: "age-childhood",
          title: "Childhood (0–12)",
          ageRange: { from: 0, to: 12 },
          summary: "Childhood (ages 0-12) highlights home and care.",
          dashas: [],
          items: [
            {
              title: "4th house themes",
              text: "This stage weighs mother, home, and inner peace.",
              evidence: ["House 4 lord moon in house 11."],
            },
          ],
        },
      ],
      dashaChapters: [
        {
          key: "dasha-rahu-2024",
          title: "Rahu years, age 20–38",
          ageRange: { from: 20, to: 38 },
          summary: "The Rahu mahadasha foregrounds ambition and foreign paths.",
          dashas: [
            {
              planet: "rahu",
              level: "mahadasha",
              start: "2024-03-26T00:00:00.000Z",
              end: "2042-03-26T00:00:00.000Z",
              ageFrom: 20.6,
              ageTo: 38.6,
            },
          ],
          items: [
            {
              title: "Rahu mahadasha promise",
              text: "Rahu sits natally channeling ambition through its house.",
              evidence: ["rahu mahadasha 2024-03-26 to 2042-03-26."],
            },
          ],
          isCurrent: true,
        },
      ],
    },
  },
};

describe("ReadingPanel", () => {
  it("renders section prose with collapsed evidence", () => {
    render(<ReadingPanel reading={SAMPLE} />);

    expect(screen.getByRole("heading", { name: /deep reading/i })).toBeTruthy();
    expect(screen.getByText(/Scorpio Lagna/)).toBeTruthy();
    expect(
      screen.getByText(/lagna rises in Scorpio within Anuradha/),
    ).toBeTruthy();
    expect(screen.getAllByText(/Evidence \(2\)/).length).toBeGreaterThan(0);
  });

  it("renders Your Life with hybrid lens by default", () => {
    render(<ReadingPanel reading={SAMPLE} />);

    expect(screen.getByRole("heading", { name: /your life/i })).toBeTruthy();
    expect(screen.getByText(/Childhood \(0–12\) · Sun \/ Moon/)).toBeTruthy();
    expect(
      screen.getByText(/Across Sun and Moon years, Childhood/),
    ).toBeTruthy();
  });

  it("switches to dasha chapters without losing deep reading", () => {
    render(<ReadingPanel reading={SAMPLE} />);

    fireEvent.click(screen.getByRole("tab", { name: /dasha chapters/i }));
    expect(screen.getByText(/Rahu years, age 20–38/)).toBeTruthy();
    expect(screen.getByText(/Now/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: /deep reading/i })).toBeTruthy();
  });

  it("hides Your Life when lifeStory is absent", () => {
    const { lifeStory: _omit, ...withoutLife } = SAMPLE;
    render(<ReadingPanel reading={withoutLife} />);

    expect(screen.queryByRole("heading", { name: /your life/i })).toBeNull();
    expect(screen.getByRole("heading", { name: /deep reading/i })).toBeTruthy();
  });
});
