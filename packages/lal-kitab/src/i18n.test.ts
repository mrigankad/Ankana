import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { hindiCoverage, localizeReport } from "./i18n";

const dataDir = join(__dirname, "..", "data");

describe("lal-kitab Hindi overlay", () => {
  it("leaves English untouched", () => {
    const report = { theme: "Royal, dutiful character; self-made authority." };
    expect(localizeReport(report, "en")).toBe(report);
  });

  it("translates a known paraphrase and flags the overlay for review", () => {
    const out = localizeReport({ theme: "Royal, dutiful character; self-made authority." }, "hi");
    expect(out.theme).toMatch(/[\u0900-\u097F]/);
    expect(hindiCoverage().needs_review_hi).toBe(true);
  });

  it("covers every English effect, theme and remedy in the planet-house data", () => {
    const rows: Array<{ theme?: string; conditions?: Array<{ effect: string }>; remedies?: Array<{ text: string }> }> =
      JSON.parse(readFileSync(join(dataDir, "planet_house.json"), "utf8")).rows;
    const dir = join(dataDir, "planet_house");
    const byId = new Map<string, (typeof rows)[number]>(
      rows.map((r) => [(r as unknown as { id: string }).id, r]),
    );
    for (const f of readdirSync(dir)) {
      const extra = JSON.parse(readFileSync(join(dir, f), "utf8"));
      for (const r of Array.isArray(extra) ? extra : extra.rows) byId.set(r.id, r);
    }
    let missing = 0;
    for (const r of byId.values()) {
      const strings = [r.theme, ...(r.conditions ?? []).map((c) => c.effect), ...(r.remedies ?? []).map((x) => x.text)];
      for (const s of strings) {
        if (s && localizeReport({ s }, "hi").s === s) missing += 1;
      }
    }
    expect(byId.size).toBe(108);
    expect(missing).toBe(0);
  });
});
