import { describe, expect, it } from "vitest";

import { HI_LIVE } from "../i18n/hi-live";
import type { ClientRowV1, TodayV1, UsageV1 } from "./live";
import { clientRowFromV1, followUpLabel, needsYouItems, reportViews, skyItems, todayViewFromV1, workspaceFromLive } from "./live-views";

const base: ClientRowV1 = {
  id: "c1", display_name: "Ananya Sharma", contact_email: "a@example.com", contact_phone: null, timezone: null, preferred_language: null,
  created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", tags: ["Lal Kitab"], latest_chart_id: "ch1", lagna_sign: "Pisces", lagna_degree: 10.53,
  current_dasha: { maha: "moon", antar: "mars", antar_ends: null }, last_consultation_at: "2026-10-24T08:00:00Z", next_consultation_at: null,
  next_follow_up: "2026-11-18", needs_rectify: false,
};

describe("clientRowFromV1", () => {
  const now = new Date("2026-11-14T06:00:00Z");
  it("formats lagna, dasha, last visit and follow-up", () => {
    const r = clientRowFromV1(base, { now, timeZone: "Asia/Kolkata" });
    expect(r).toMatchObject({ chartId: "ch1", initials: "AS", lagna: "Pisces 10°32′", dasha: "Moon / Mars", lastConsult: "24 Oct", nextFollowUp: "Wed 18 Nov", tags: ["Lal Kitab"] });
  });
  it("leaves chart fields empty without a chart and falls back to a booked visit", () => {
    const r = clientRowFromV1({ ...base, lagna_sign: null, lagna_degree: null, current_dasha: null, latest_chart_id: null, last_consultation_at: null, next_follow_up: null, next_consultation_at: "2026-11-14T10:00:00Z" }, { now, timeZone: "Asia/Kolkata" });
    expect(r).toMatchObject({ chartId: null, lagna: "", dasha: "", lastConsult: "", nextFollowUp: "Today" });
  });
});

describe("followUpLabel", () => {
  it("says Today for the current day", () => expect(followUpLabel("2026-11-14", "2026-11-14")).toBe("Today"));
});

const today: TodayV1 = {
  date: "2026-11-14", timezone: "Asia/Kolkata", practitioner_name: "Rohan Shastri",
  consultations: [{ id: "k1", client_id: "c1", client_name: "Ananya Sharma", at: "2026-11-14T06:00:00Z", topic: "Career", mode: null, chart_id: "ch1", lagna_sign: "Pisces", lagna_degree: 10, maha: "moon", antar: "mars", houses: { "1": ["Su"], "12": ["Me", "Sa"] }, status: "prepared" }],
  needs_you: { total: 2, followups: 1, missed_remedies: 0, ended_plans: 0, failed_sends: 1, items: [{ kind: "followup", client_id: "c1", client_name: "Ananya Sharma", detail: null, days: 2 }, { kind: "failed_send", client_id: null, client_name: null, detail: "remedy_due", days: null }] },
  place: { label: "New Delhi", latitude: 28.6, longitude: 77.2, source: "timezone_default" },
  panchang: { sunrise: "2026-11-14T01:12:00Z", sunset: "2026-11-14T11:58:00Z", vara: "Shanivara", paksha: "shukla", tithi: { name: "Panchami", ends_at: "2026-11-14T17:54:00Z" }, nakshatra: { name: "Purva Ashadha", ends_at: "2026-11-14T14:54:00Z" }, yoga: "Shula", karana: "Bava", moon_sign: "Sagittarius", sun_sign: "Libra", rahu_kaal_start: "2026-11-14T03:54:00Z", rahu_kaal_end: "2026-11-14T05:14:00Z" },
  sky: [{ at: "2026-11-16T14:09:00Z", planet: "sun", kind: "ingress", sign: "Scorpio", sign_index: 7, clients_touched: 3, client_ids: [] }],
  next_ingress: { at: "2026-11-16T14:09:00Z", planet: "sun", kind: "ingress", sign: "Scorpio", sign_index: 7, clients_touched: 3, client_ids: [] },
};

describe("todayViewFromV1", () => {
  it("maps consultations, panchang in the practice zone, sky and needs-you", () => {
    const v = todayViewFromV1(today, "Shastri Jyotish");
    expect(v.practitioner.firstName).toBe("Rohan");
    expect(v.first).toEqual({ name: "Ananya Sharma", time: "11:30", status: "prepared" });
    expect(v.consults[0]).toMatchObject({ time: "11:30", headlineKey: "{sign} lagna", status: { label: "Prepared", tone: "ok" }, miniHouses: { 1: ["Su"], 12: ["Me", "Sa"] } });
    expect(v.panchang).toMatchObject({ vara: "Shanivara", varaDeva: "शनिवार", sunrise: "06:42", tithi: { paksha: "shukla", untilTime: "23:24" }, rahuKaal: { from: "09:24", to: "10:44" } });
    expect(v.panchang?.ingress).toMatchObject({ planet: "sun", sign: "Scorpio", date: "16 Nov", touched: 3 });
    expect(v.sky[0]).toMatchObject({ date: "16 Nov", title: "Sun enters Scorpio", touched: 3 });
    expect(v.needsYou).toHaveLength(2);
  });
  it("has no panchang when the server sent none", () => {
    expect(todayViewFromV1({ ...today, panchang: null, next_ingress: null }).panchang).toBeNull();
  });
});

describe("needsYouItems", () => {
  it("links clients and marks overdue follow-ups as alerts", () => {
    const [a, b] = needsYouItems(today.needs_you.items);
    expect(a).toMatchObject({ tone: "alert", href: "/clients/c1", textKey: "follow-up is {n} days overdue", textParams: { n: 2 } });
    expect(b).toMatchObject({ href: "/needs-you", tone: "alert" });
  });
});

describe("skyItems and workspaceFromLive", () => {
  it("titles stations", () => {
    expect(skyItems([{ ...today.sky[0]!, kind: "retrograde-station", planet: "mercury", sign: "Virgo" }], "Asia/Kolkata")[0]!.title).toBe("Mercury stations retrograde in Virgo");
  });
  it("shows unlimited usage when billing is off and the limit when on", () => {
    const meters = (limit: number | null): UsageV1 => ({ billing: limit !== null, plan: null, plan_name: null, period: "2026-11", unlimited: limit === null, meters: [{ metric: "reports", used: 3, limit, period: "2026-11-01" }, { metric: "clients", used: 7, limit: null, period: "current" }] });
    expect(workspaceFromLive({ usage: meters(null), today, practiceName: "P" })).toMatchObject({ reportsUsed: 3, reportsQuota: null, clientCount: 7, needsYouCount: 2 });
    expect(workspaceFromLive({ usage: meters(25), today: null, practiceName: "P" }).reportsQuota).toBe(25);
  });
});

describe("reportViews", () => {
  it("maps status, tone and link", () => {
    const [r] = reportViews([{ id: "r", chart_id: "c", status: "done", template: "standard", template_version: "1", language: "hi", sections: ["a", "b"], error: null, created_at: "2026-10-24T10:00:00Z", size_bytes: 1, download_url: "/v1/storage/x", download_expires_in: 900 }], (u) => `http://api${u}`);
    expect(r).toMatchObject({ title: "Standard report, 2 sections", status: "Ready", tone: "ok", href: "http://api/v1/storage/x", sentParams: { date: "24 Oct", lang: "Hindi" } });
  });
});

describe("Hindi coverage", () => {
  it("has no empty entries and keeps placeholders", () => {
    for (const [k, v] of Object.entries(HI_LIVE)) {
      expect(v.length).toBeGreaterThan(0);
      for (const ph of k.match(/\{\w+\}/g) ?? []) expect(v, k).toContain(ph);
    }
  });
});
