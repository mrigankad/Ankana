import { computeVedicChartArtifact } from "@astro/astrology-core";
import { describe, expect, it } from "vitest";

import { toolStatusLabel } from "./assistant-service";
import { TOOL_ANCHORS, TOOL_DEFINITIONS, executeTool } from "./tools";

const artifact = computeVedicChartArtifact({
  birthDate: "1995-03-15",
  birthTime: "06:42",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});
const NOW = new Date("2026-11-14T00:00:00Z");

const LK_TOOLS = ["lk_chart", "lk_sleeping", "lk_rin", "lk_masnui", "lk_varshphal", "lk_upay"];

describe("Lal Kitab assistant tools", () => {
  it("are declared with anchors and status labels", () => {
    const names = TOOL_DEFINITIONS.map((t) => t.function.name);
    for (const name of LK_TOOLS) {
      expect(names).toContain(name);
      expect(TOOL_ANCHORS[name]).toMatch(/^lal-kitab/);
      expect(toolStatusLabel(name)).not.toMatch(/^Consulting/);
    }
  });

  it("lk_chart honours the origin option", () => {
    const lagna = executeTool("lk_chart", artifact, NOW);
    expect(lagna.summary).toContain("lagna_h1");
    expect(lagna.summary).toContain("H1:sun");
    const aries = executeTool("lk_chart", artifact, NOW, { args: { origin: "aries_h1" } });
    expect(aries.summary).toContain("aries_h1");
    expect(aries.summary).toContain("H12:sun");
  });

  it("lk_varshphal defaults to the current year of life and validates range", () => {
    const current = executeTool("lk_varshphal", artifact, NOW);
    expect((current.data as { age: number }).age).toBe(32);
    const age33 = executeTool("lk_varshphal", artifact, NOW, { args: { age: 33 } });
    expect((age33.data as { row: number[] }).row[0]).toBe(12);
    const bad = executeTool("lk_varshphal", artifact, NOW, { args: { age: 150 } });
    expect((bad.data as { available: boolean }).available).toBe(false);
  });

  it("lk_upay returns the one-at-a-time rule", () => {
    const upay = executeTool("lk_upay", artifact, NOW);
    expect(upay.summary).toContain("one at a time");
    expect(upay.anchor).toBe("lal-kitab-upay");
  });

  it("lk_sleeping, lk_rin and lk_masnui return data", () => {
    expect(executeTool("lk_sleeping", artifact, NOW).summary).toContain("Dormant planets");
    expect(executeTool("lk_rin", artifact, NOW).summary).toContain("debts");
    expect(executeTool("lk_masnui", artifact, NOW).summary).toContain("No artificial");
  });
});
