/// <reference types="node" />
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import { computeVedicChartArtifact } from "@astro/astrology-core";
import { describe, expect, it } from "vitest";

import { lalKitabReport, VARSHPHAL_MAX_AGE, varshphal, lkChart, yearOfLife } from "./index";
import type { LkArtifactInput, LkOrigin, Planet } from "./index";
import { PLANET_ORDER } from "./types";

/**
 * Exports TS outputs for the Python parity test (services/api-py/tests/test_lal_kitab_parity.py).
 * Only runs when LK_PARITY_OUT is set:
 *   LK_PARITY_OUT=../../services/api-py/tests/fixtures/lal_kitab_parity.json pnpm --filter @astro/lal-kitab test parity-export
 */
const out = process.env.LK_PARITY_OUT;

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fabricate(seed: number): LkArtifactInput {
  const r = rng(seed);
  const lagna = Math.floor(r() * 12);
  // Cluster placements on a few signs so debts / artificial planets / dormant cases occur.
  const pool = Array.from({ length: 2 + Math.floor(r() * 6) }, () => Math.floor(r() * 12));
  const planets = PLANET_ORDER.filter(() => r() > 0.05).map((planet) => ({
    planet: planet as Planet,
    signIndex: pool[Math.floor(r() * pool.length)],
  }));
  const y = 1950 + Math.floor(r() * 70);
  const m = 1 + Math.floor(r() * 12);
  const d = 1 + Math.floor(r() * 28);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    ascendant: { signIndex: lagna },
    planets,
    calculationMetadata: { input: { birthDate: `${y}-${pad(m)}-${pad(d)}` } },
  };
}

describe.skipIf(!out)("parity export", () => {
  it("writes fixture", () => {
    const now = new Date("2026-11-14T10:00:00Z");
    const ananya = computeVedicChartArtifact({
      birthDate: "1995-03-15",
      birthTime: "06:42",
      timezoneName: "Asia/Kolkata",
      latitude: 25.3176,
      longitude: 82.9739,
      placeLabel: "Varanasi, Uttar Pradesh, India",
    });
    const slim = (a: LkArtifactInput): LkArtifactInput => ({
      ascendant: { signIndex: a.ascendant.signIndex },
      planets: a.planets.map((p) => ({ planet: p.planet, signIndex: p.signIndex })),
      calculationMetadata: { input: { birthDate: a.calculationMetadata?.input?.birthDate } },
    });

    const inputs: Array<{ id: string; artifact: LkArtifactInput; origin?: LkOrigin; age?: number }> = [
      { id: "ananya_default", artifact: slim(ananya) },
      { id: "ananya_aries", artifact: slim(ananya), origin: "aries_h1" },
      { id: "ananya_age36", artifact: slim(ananya), age: 36 },
      { id: "ananya_age_max", artifact: slim(ananya), age: VARSHPHAL_MAX_AGE },
    ];
    for (let i = 0; i < 24; i += 1) {
      inputs.push({
        id: `random_${i}`,
        artifact: fabricate(1000 + i),
        origin: i % 4 === 3 ? "aries_h1" : undefined,
        age: i % 3 === 0 ? 1 + ((i * 7) % VARSHPHAL_MAX_AGE) : undefined,
      });
    }

    const cases = inputs.map((c) => {
      const report = lalKitabReport(c.artifact, { origin: c.origin, age: c.age, now });
      const chart = lkChart(c.artifact, { origin: c.origin });
      const annual = [1, 35, 36, VARSHPHAL_MAX_AGE].map((age) => varshphal(chart, age));
      return { ...c, now: now.toISOString(), report, varshphal_ages: annual };
    });
    const yol = [
      ["1995-03-15", "2026-11-14T10:00:00Z"],
      ["1995-11-14", "2026-11-14T10:00:00Z"],
      ["1995-11-15", "2026-11-14T10:00:00Z"],
      ["2026-11-14", "2026-11-14T00:00:00Z"],
    ].map(([birth, at]) => ({ birth, now: at, year: yearOfLife(birth, new Date(at)) }));

    mkdirSync(dirname(out!), { recursive: true });
    writeFileSync(out!, `${JSON.stringify({ generated_by: "packages/lal-kitab/src/parity-export.test.ts", cases, year_of_life: yol }, null, 1)}\n`);
    expect(cases.length).toBeGreaterThan(20);
  });
});
