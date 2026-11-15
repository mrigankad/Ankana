import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { VedicChartArtifact } from "@astro/astrology-core";

import golden from "../../../../services/api-py/tests/golden/charts.json";
import { fixtureDepthSource, fixtureDoubleTransit, fixtureGochara, fixtureSadeSati } from "@/lib/api/fixture-transit-depth";
import { HI } from "@/lib/i18n/hi";

import { TransitDepth } from "./transit-depth";

// The Python golden chart (Virgo Moon, born 2003) is the parity reference: the Python engine
// produced the pinned values below with swisseph, the TS engine must land on the same ones.
const natal = (golden as unknown as Array<{ artifact: VedicChartArtifact }>)[0].artifact;
const NOW = Date.parse("2026-11-15T00:00:00Z");
const day = (iso: string) => Date.parse(iso) / 86_400_000;

describe("fixture transit depth engine (parity with services/api-py transit_depth.py)", () => {
  it("lists the lifetime sade sati and dhaiya periods with phase dates", () => {
    const r = fixtureSadeSati(natal, NOW);
    expect(r.moon_sign).toBe("Virgo");
    const first = r.periods.find((p) => p.kind === "sade_sati")!;
    expect(Math.abs(day(first.starts_at) - day("2006-10-31T00:00:00Z"))).toBeLessThan(2);
    expect(Math.abs(day(first.ends_at) - day("2014-11-02T00:00:00Z"))).toBeLessThan(2);
    expect(first.phases.map((p) => p.phase)).toEqual(["rising", "peak", "setting"]);
    expect(Math.abs(day(first.phases[1].starts_at) - day("2009-09-09T00:00:00Z"))).toBeLessThan(2);
    const next = r.periods[r.next_index!];
    expect(next.kind).toBe("dhaiya_ashtama");
    expect(Math.abs(day(next.starts_at) - day("2027-06-02T00:00:00Z"))).toBeLessThan(2);
    expect(r.current.kind).toBeNull();
    expect(r.proof).toMatch(/Phaladeepika/);
  });

  it("rates each graha with bindus, vedha and a reason", () => {
    const g = fixtureGochara(natal, NOW);
    const by = Object.fromEntries(g.planets.map((p) => [p.planet, p]));
    expect(by.venus).toMatchObject({ verdict: "favourable", bindus: 4, vedha_house: 8 });
    expect(by.mercury).toMatchObject({ verdict: "mixed", reason_code: "favourable_weak_bindus", bindus: 3 });
    expect(by.jupiter).toMatchObject({ verdict: "mixed", reason_code: "unfavourable_softened", bindus: 5 });
    expect(by.saturn).toMatchObject({ verdict: "unfavourable", bindus: 1 });
    expect(by.rahu).toMatchObject({ verdict: "not_rated", bindus: null });
    expect(g.planets).toHaveLength(9);
  });

  it("what-if date moves Saturn and the sade sati status", () => {
    const g = fixtureGochara(natal, Date.parse("2008-03-01T00:00:00Z"));
    expect(g.saturn_status).toEqual({ kind: "sade_sati", phase: "rising", house_from_moon: 12 });
  });

  it("marks double transit houses where Jupiter and Saturn both reach", () => {
    const d = fixtureDoubleTransit(natal, NOW, 24);
    expect(d.spans[0]).toMatchObject({ jupiter_sign: "Leo", saturn_sign: "Pisces", houses: [2] });
    expect(d.houses.filter((h) => h.active_now).map((h) => h.house)).toEqual([2]);
    expect(d.houses).toHaveLength(12);
  });
});

describe("TransitDepth", () => {
  const source = {
    getSadeSati: async () => fixtureSadeSati(natal, NOW),
    getGochara: vi.fn(async (d: string | null) => fixtureGochara(natal, d ? Date.parse(`${d}T06:30:00Z`) : NOW)),
    getDoubleTransit: async () => fixtureDoubleTransit(natal, NOW),
  };

  it("renders gochara, the sade sati band and double transit, and reloads for a what-if date", async () => {
    render(<TransitDepth source={source} />);
    expect(await screen.findByText("Gochara today")).toBeTruthy();
    expect(await screen.findByText("Sade sati and dhaiya for life")).toBeTruthy();
    expect(await screen.findByText("Double transit, next 24 months")).toBeTruthy();
    expect(await screen.findByText("Venus")).toBeTruthy();
    expect(screen.getAllByText(/Phaladeepika/).length).toBeGreaterThan(1);

    const [dd, mm, yyyy] = screen.getAllByRole("textbox");
    fireEvent.change(dd, { target: { value: "01" } });
    fireEvent.change(mm, { target: { value: "03" } });
    fireEvent.change(yyyy, { target: { value: "2008" } });
    await waitFor(() => expect(source.getGochara).toHaveBeenCalledWith("2008-03-01"));
    expect(await screen.findByText(/Saturn today: sade sati, rising phase/)).toBeTruthy();
  });

  it("has Hindi for every depth heading and source line", () => {
    for (const key of ["Gochara today", "Sade sati and dhaiya for life", "Double transit, next 24 months", "What-if date", "Show working"]) {
      expect(HI[key]).toBeTruthy();
    }
    const proof = fixtureSadeSati(natal, NOW).proof;
    expect(HI[proof]).toBeTruthy();
    expect(HI[fixtureGochara(natal, NOW).proof]).toBeTruthy();
    expect(HI[fixtureDoubleTransit(natal, NOW).proof]).toBeTruthy();
  });
});
