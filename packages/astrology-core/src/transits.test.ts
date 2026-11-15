import { describe, expect, it } from "vitest";

import { computeVedicChartArtifact } from "./chart";
import { computeTransitSnapshot, computeTransitTimeline } from "./transits";

const natal = computeVedicChartArtifact({
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

describe("computeTransitSnapshot", () => {
  const snapshot = computeTransitSnapshot(natal, new Date("2026-07-09T00:00:00Z"));

  it("returns all nine grahas with natal-relative houses", () => {
    expect(snapshot.planets).toHaveLength(9);
    for (const state of snapshot.planets) {
      expect(state.houseFromLagna).toBeGreaterThanOrEqual(1);
      expect(state.houseFromLagna).toBeLessThanOrEqual(12);
      expect(state.houseFromMoon).toBeGreaterThanOrEqual(1);
      expect(state.houseFromMoon).toBeLessThanOrEqual(12);
      expect(state.nakshatra).toBeTruthy();
    }
  });

  it("keeps transit Rahu and Ketu opposite and always retrograde", () => {
    const rahu = snapshot.planets.find((p) => p.planet === "rahu")!;
    const ketu = snapshot.planets.find((p) => p.planet === "ketu")!;
    const gap = Math.abs(rahu.siderealLongitude - ketu.siderealLongitude);
    expect(Math.min(gap, 360 - gap)).toBeCloseTo(180, 6);
    expect(rahu.retrograde).toBe(true);
  });

  it("derives sade sati strictly from Saturn's house from the natal Moon", () => {
    const saturn = snapshot.planets.find((p) => p.planet === "saturn")!;
    const inBand = [12, 1, 2].includes(saturn.houseFromMoon);
    expect(snapshot.sadeSati.active).toBe(inBand);
    if (inBand) {
      expect(["rising", "peak", "setting"]).toContain(snapshot.sadeSati.phase);
    } else {
      expect(snapshot.sadeSati.phase).toBeNull();
    }
    expect(snapshot.sadeSati.evidence.length).toBeGreaterThan(0);
  });

  it("matches the natal chart when computed for the birth instant", () => {
    const atBirth = computeTransitSnapshot(natal, new Date("1990-01-01T05:00:00Z"));
    for (const natalPlanet of natal.planets) {
      const transit = atBirth.planets.find((p) => p.planet === natalPlanet.planet)!;
      expect(transit.signIndex).toBe(natalPlanet.signIndex);
    }
  });
});

describe("computeTransitTimeline", () => {
  it("finds the Sun's twelve ingresses in a year, in order", () => {
    const events = computeTransitTimeline(new Date("2026-01-01T00:00:00Z"), 1);
    const sunIngresses = events.filter(
      (e) => e.planet === "sun" && e.kind === "ingress",
    );
    expect(sunIngresses.length).toBe(12);

    const dates = events.map((e) => e.date);
    expect([...dates].sort()).toEqual(dates);
  });

  it("detects mercury retrograde and direct stations in a year", () => {
    const events = computeTransitTimeline(new Date("2026-01-01T00:00:00Z"), 1);
    const retro = events.filter(
      (e) => e.planet === "mercury" && e.kind === "retrograde-station",
    );
    const direct = events.filter(
      (e) => e.planet === "mercury" && e.kind === "direct-station",
    );
    // Mercury stations retrograde 3-4 times per year.
    expect(retro.length).toBeGreaterThanOrEqual(3);
    expect(retro.length).toBeLessThanOrEqual(4);
    expect(Math.abs(retro.length - direct.length)).toBeLessThanOrEqual(1);
  });

  it("clamps the horizon and never reports the Moon", () => {
    const events = computeTransitTimeline(new Date("2026-01-01T00:00:00Z"), 0.25);
    expect(events.every((e) => e.planet !== "moon")).toBe(true);
    const last = new Date(events[events.length - 1]!.date).getTime();
    expect(last).toBeLessThanOrEqual(
      new Date("2026-01-01T00:00:00Z").getTime() + 0.26 * 365.25 * 86_400_000,
    );
  });
});
