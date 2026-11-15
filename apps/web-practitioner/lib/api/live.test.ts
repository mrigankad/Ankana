import { afterEach, describe, expect, it, vi } from "vitest";

import { viewFromPreview } from "./intake";
import { camelizeKeys, renderReport } from "./live";
import { ProblemError, problemMessage } from "./v1";

afterEach(() => vi.restoreAllMocks());

describe("problemMessage", () => {
  it("explains a missing consent in plain words", () => {
    const err = new ProblemError(403, { code: "consent_required", purpose: "chart_compute", detail: "x" });
    expect(problemMessage(err)).toMatch(/not agreed to chart compute/i);
  });
  it("never leaks server detail for 5xx", () => {
    expect(problemMessage(new ProblemError(500, { detail: "Traceback ..." }))).toMatch(/try again/i);
  });
  it("maps a network failure", () => {
    expect(problemMessage(new TypeError("fetch failed"))).toMatch(/cannot reach/i);
  });
});

describe("camelizeKeys", () => {
  it("camelizes engine keys but keeps the book citation keys", () => {
    const out = camelizeKeys<Record<string, unknown>>({ sleeping_planets: [{ self_awakening_age: 22, needs_review: false, cite: { printed_page: 116 } }] });
    expect(out).toEqual({ sleepingPlanets: [{ selfAwakeningAge: 22, needs_review: false, cite: { printed_page: 116 } }] });
  });
});

describe("viewFromPreview", () => {
  it("builds the preview with a time-sensitivity note", () => {
    const v = viewFromPreview(
      {
        lagna: { sign: "Pisces", sign_index: 11, degrees_in_sign: 10.53, nakshatra: "Uttara Bhadrapada", pada: 3 },
        moon: { sign: "Leo", nakshatra: "Magha", pada: 2 },
        houses: { "1": ["Su"], "6": ["Mo"] },
        sensitivity: { d1_minutes_before: 38, d1_minutes_after: 70, d1_holds_from: "06:04", d1_holds_until: "07:52", d9_minutes_before: 6, d9_minutes_after: 7, d9_holds_from: "06:36", d9_holds_until: "06:49", window_minutes: 6, scan_minutes: 240 },
      },
      { h: 6, m: 42 },
    );
    expect(v.lagna).toBe("Pisces lagna 10\u00b032\u2032");
    expect(v.lagnaSign).toBe(12);
    expect(v.houses[6]).toEqual(["Mo"]);
    expect(v.safeNote).toMatch(/rectify/);
  });
});

describe("renderReport", () => {
  it("polls until the report is done and returns the signed link", async () => {
    const seq = [
      { id: "r1", status: "queued" },
      { id: "r1", status: "running" },
      { id: "r1", status: "done", download_url: "/v1/storage/x?sig=1" },
    ];
    let i = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(seq[Math.min(i++, seq.length - 1)]), { status: i === 1 ? 202 : 200 })),
    );
    const seen: string[] = [];
    const done = await renderReport({ chart_id: "c1" }, (r) => seen.push(r.status), { intervalMs: 1 });
    expect(done.status).toBe("done");
    expect(seen).toEqual(["queued", "running", "done"]);
  });
});
