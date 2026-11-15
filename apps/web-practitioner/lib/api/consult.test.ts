import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", async (orig) => ({ ...(await orig<typeof import("./client")>()), isFixtures: () => true }));

import { ANANYA_CLIENT_ID } from "./fixtures";
import { consultApi, factHref, resetConsultFixtures, splitNoteBody, type NoteFact } from "./consult";

const fact: NoteFact = { id: "a1", type: "planet", ref: "planet:saturn", label: "Saturn in Aquarius, house 12" };

describe("note chips", () => {
  it("splits a body into text and fact pieces in order", () => {
    const parts = splitNoteBody("See {{fact:a1}} first, then {{fact:zz}}.", [fact]);
    expect(parts).toEqual([{ text: "See " }, { fact }, { text: " first, then " }, { text: "{{fact:zz}}" }, { text: "." }]);
  });

  it("links a chip to the chart tab that shows the fact", () => {
    expect(factHref("c1", { type: "planet" })).toBe("/charts/c1?tab=planets");
    expect(factHref("c1", { type: "dasha" })).toBe("/charts/c1?tab=dashas");
    expect(factHref("c1", { type: "yoga" })).toBe("/charts/c1?tab=yogas");
    expect(factHref("c1", { type: "transit" })).toBe("/charts/c1?tab=transits");
    expect(factHref("c1", { type: "lal_kitab" })).toBe("/charts/c1?tab=lal-kitab");
    expect(factHref(null, { type: "planet" })).toBeNull();
  });
});

describe("fixture mode renders the whole workflow", () => {
  beforeEach(() => resetConsultFixtures());

  it("offers every kind of chart fact", async () => {
    const { chart_id, facts } = await consultApi.getChartFacts(ANANYA_CLIENT_ID);
    expect(chart_id).toBeTruthy();
    expect(new Set(facts.map((f) => f.type))).toEqual(new Set(["planet", "dasha", "yoga", "transit", "lal_kitab"]));
  });

  it("builds a brief with the running period, three transits and the stated question", async () => {
    const b = await consultApi.getBrief(ANANYA_CLIENT_ID);
    expect(b.dasha?.maha).toBe("moon");
    expect(b.transits).toHaveLength(3);
    expect(b.stated_question).toContain("Pune");
    expect(b.remedies.length).toBeGreaterThan(0);
    expect(b.follow_ups[0]?.overdue).toBe(true);
    expect(b.last_consultation?.excerpt).toBeTruthy();
  });

  it("saves a summary with a prediction, then records the outcome later", async () => {
    const id = "cons-ananya-3";
    const saved = await consultApi.saveSummary(id, { topics: ["Career"], remedies_given: ["Lamp"], follow_up_date: "2026-12-01", predictions: [{ statement: "Job change", window_start: "2026-12-01", window_end: "2027-03-01" }] });
    expect(saved.predictions[0]?.status).toBe("pending");
    const p = saved.predictions[0]!;
    expect((await consultApi.updatePrediction(p.id, { status: "came_true", outcome_note: "Joined" })).status).toBe("came_true");
    expect((await consultApi.updatePrediction(p.id, { status: "unclear" })).outcome_note).toBe("Joined");
    const timeline = await consultApi.getTimeline(ANANYA_CLIENT_ID);
    expect(timeline.some((e) => e.kind === "prediction" && e.title === "Job change")).toBe(true);
    expect(timeline.map((e) => e.at)).toEqual([...timeline.map((e) => e.at)].sort().reverse());
  });

  it("puts consultations, predictions, remedies, reports and life events on one timeline", async () => {
    await consultApi.createLifeEvent(ANANYA_CLIENT_ID, { event_date: "2026-11-01", kind: "move", title: "Moved to Pune" });
    const kinds = new Set((await consultApi.getTimeline(ANANYA_CLIENT_ID)).map((e) => e.kind));
    expect(kinds).toEqual(new Set(["consultation", "prediction", "remedy", "report", "life_event"]));
  });

  it("drafts a summary without a server", async () => {
    const d = await consultApi.draftSummary("cons-ananya-1");
    expect(d.summary.source).toBe("ai");
    expect(d.verification.status).toBe("ok");
  });
});
