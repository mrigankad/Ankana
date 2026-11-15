import { describe, expect, it } from "vitest";
import { computeVedicChartArtifact } from "@astro/astrology-core";

import { CLASSICAL_CORPUS } from "./corpus";
import { searchClassical } from "./retrieve";
import { executeTool } from "../tools";

const artifact = computeVedicChartArtifact({
  birthDate: "2003-08-29",
  birthTime: "12:22",
  timezoneName: "Asia/Kolkata",
  latitude: 25.6167,
  longitude: 88.1233,
  placeLabel: "Raiganj, West Bengal",
});

describe("classical corpus", () => {
  it("has unique source ids and non-empty passages", () => {
    const ids = CLASSICAL_CORPUS.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(CLASSICAL_CORPUS.length).toBeGreaterThanOrEqual(30);
    for (const passage of CLASSICAL_CORPUS) {
      expect(passage.source.length).toBeGreaterThan(0);
      expect(passage.text.length).toBeGreaterThan(40);
    }
  });
});

describe("searchClassical", () => {
  it("retrieves 10th house career notes for a vocation query", () => {
    const hits = searchClassical("10th house career vocation karma", 3);
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].id).toMatch(/house-10|planet|dasha/);
    expect(hits.some((h) => h.id === "nk-house-10")).toBe(true);
    expect(hits[0].source).toContain("Nakshatra");
  });

  it("retrieves Saturn / sade sati framing", () => {
    const hits = searchClassical("sade sati saturn transit moon", 3);
    expect(hits.some((h) => h.id === "nk-transit-sade-sati")).toBe(true);
  });

  it("returns empty for blank queries", () => {
    expect(searchClassical(" ", 3)).toEqual([]);
  });
});

describe("search_classical tool", () => {
  it("returns source ids in tool data", () => {
    const result = executeTool("search_classical", artifact, new Date(), {
      args: { query: "Jupiter mahadasha growth", topK: 2 },
    });
    expect(result.summary).toContain("Classical notes");
    expect(result.anchor).toBeUndefined();
    const data = result.data as {
      hits: Array<{ id: string; source: string; text: string }>;
    };
    expect(data.hits.length).toBeGreaterThan(0);
    expect(data.hits[0].id).toMatch(/^nk-/);
    expect(data.hits[0].source.length).toBeGreaterThan(0);
  });
});
