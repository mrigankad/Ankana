import type { VedicChartArtifact } from "@astro/astrology-core";

import generated from "../fixtures/ananya.generated.json";
import type {
  AskThread,
  ChartBundle,
  ClientRow,
  LagnaPreview,
  LalKitabReportJson,
  TodayView,
  WorkspaceMeta,
} from "./types";

export const ANANYA_CHART_ID = "chart-ananya-sharma";
export const ANANYA_CLIENT_ID = "client-ananya-sharma";

export const clientRows: ClientRow[] = [
  { id: ANANYA_CLIENT_ID, chartId: ANANYA_CHART_ID, initials: "AS", name: "Ananya Sharma", birthLine: "15 Mar 1995, Varanasi", lagna: "Pisces 10°32′", dasha: "Moon / Mars to Feb 2027", lastConsult: "24 Oct", nextFollowUp: "Today, 11:30", tags: ["Lal Kitab"] },
  { id: "client-vikram-rao", chartId: null, initials: "VR", name: "Vikram Rao", birthLine: "02 Aug 1988, Hyderabad", lagna: "Leo 4°18′", dasha: "Rahu · Rahu to 2031", lastConsult: "First visit", nextFollowUp: "Today, 14:00", tags: ["Lal Kitab"] },
  { id: "client-meera-iyer", chartId: null, initials: "MI", name: "Meera Iyer", birthLine: "11 Nov 1991, Chennai", lagna: "Libra 0°41′", dasha: "Saturn · Saturn to 2030", lastConsult: "9 Sep", nextFollowUp: "Today, 16:15", tags: ["Rectify"] },
  { id: "client-arjun-kavya", chartId: null, initials: "AK", name: "Arjun Nair & Kavya Menon", birthLine: "Kochi · Bengaluru", lagna: "Virgo · Taurus", dasha: "Venus · Mercury", lastConsult: "First visit", nextFollowUp: "Today, 18:00", tags: ["Matching"] },
  { id: "client-sana-qureshi", chartId: null, initials: "SQ", name: "Sana Qureshi", birthLine: "27 Jun 1993, Lucknow", lagna: "Cancer 19°05′", dasha: "Mars · Mars to 2028", lastConsult: "4 Oct", nextFollowUp: "Tue 18 Nov", tags: ["Lal Kitab"] },
  { id: "client-rajesh-kulkarni", chartId: null, initials: "RK", name: "Rajesh Kulkarni", birthLine: "19 Jan 1979, Nashik", lagna: "Scorpio 22°09′", dasha: "Jupiter · Jupiter to 2029", lastConsult: "30 Oct", nextFollowUp: "Wed 19 Nov", tags: ["Lal Kitab", "Matching"] },
  { id: "client-pooja-deshmukh", chartId: null, initials: "PD", name: "Pooja Deshmukh", birthLine: "08 May 1998, Pune", lagna: "Gemini 11°27′", dasha: "Venus · Venus to 2033", lastConsult: "12 Oct", nextFollowUp: "Mon 24 Nov", tags: ["Rectify", "Matching"] },
  { id: "client-harpreet-singh", chartId: null, initials: "HS", name: "Harpreet Singh", birthLine: "23 Dec 1985, Ludhiana", lagna: "Sagittarius 7°50′", dasha: "Mercury · Mercury to 2026", lastConsult: "18 Sep", nextFollowUp: "Fri 28 Nov", tags: ["Lal Kitab"] },
  { id: "client-lakshmi-v", chartId: null, initials: "LV", name: "Lakshmi Venkataraman", birthLine: "02 Sep 1970, Madurai", lagna: "Aquarius 15°36′", dasha: "Ketu · Ketu to 2027", lastConsult: "6 Aug", nextFollowUp: "Not scheduled", tags: [] },
  { id: "client-imran-sheikh", chartId: null, initials: "IS", name: "Imran Sheikh", birthLine: "14 Feb 1990, Aurangabad", lagna: "Capricorn 3°12′", dasha: "Sun · Sun to 2026", lastConsult: "21 Oct", nextFollowUp: "Tue 2 Dec", tags: ["Rectify"] },
];

export const workspaceFixture: WorkspaceMeta = {
  clientCount: 27,
  needsYouCount: 3,
  reportsUsed: 18,
  reportsQuota: 40,
  engine: "Engine v2 · Lahiri",
  practitioner: { name: "Rohan Shastri", practice: "Shastri Jyotish, Pune", initials: "RS" },
  consults: [
    { clientName: "Ananya Sharma", time: "11:30", active: true },
    { clientName: "Vikram Rao", time: "14:00", active: true },
    { clientName: "Meera Iyer", time: "16:15", active: false },
    { clientName: "Arjun & Kavya", time: "18:00", active: false },
  ],
};

export const todayFixture: TodayView = {
  practitioner: { name: "Rohan Shastri", firstName: "Rohan", practice: "Shastri Jyotish, Pune", initials: "RS" },
  dateLine: "Saturday 14 November · Ananya Sharma is first, at 11:30. Her chart is ready.",
  consultCount: 4,
  panchang: {
    vara: "Shanivara",
    varaDeva: "शनिवार · Pune sunrise 06:41",
    sunrise: "06:41",
    tithi: { name: "Navami, shukla", until: "until 21:04" },
    nakshatra: { name: "Shatabhisha", until: "until 15:22" },
    rahuKaal: { range: "09:28 to 10:52", note: "avoid new starts" },
    ingress: { title: "Sun into Scorpio", note: "16 Nov, touches 9 clients" },
  },
  consults: [
    { id: "c1", clientId: ANANYA_CLIENT_ID, time: "11:30 · in 2h", clientName: "Ananya Sharma", chartId: ANANYA_CHART_ID, kind: "chart", status: { label: "Prepared", tone: "ok" }, topic: "Career question · 2nd visit", headline: "Pisces lagna", sub: "Moon / Mars dasha", miniHouses: { 1: ["Su"], 2: ["Ke"], 5: ["Ma"], 6: ["Mo"], 8: ["Ra"], 9: ["Ju"], 11: ["Ve"], 12: ["Me", "Sa"] } },
    { id: "c2", clientId: "client-vikram-rao", time: "14:00", clientName: "Vikram Rao", chartId: null, kind: "chart", status: { label: "Lal Kitab", tone: "accent" }, topic: "Business · first visit", headline: "Leo lagna", sub: "Rahu dasha", miniHouses: { 1: ["Ju"], 3: ["Sa"], 4: ["Ke"], 7: ["Mo"], 9: ["Ra"], 11: ["Ma"], 12: ["Su", "Me"] } },
    { id: "c3", clientId: "client-meera-iyer", time: "16:15", clientName: "Meera Iyer", chartId: null, kind: "chart", status: { label: "Needs birth time", tone: "alert" }, topic: "Rectify ±12 min", headline: "Libra lagna", sub: "Saturn dasha", miniHouses: { 1: ["Sa"], 4: ["Ju"], 6: ["Ra"], 7: ["Mo"], 10: ["Ke"], 11: ["Su", "Ve"], 12: ["Me", "Ma"] } },
    { id: "c4", clientId: "client-arjun-kavya", time: "18:00", clientName: "Arjun & Kavya", chartId: null, kind: "match", status: { label: "Matching", tone: "ink" }, topic: "Marriage · family call", headline: "Match 28/36", sub: "Ashtakoot" },
  ],
  needsYou: [
    { id: "n1", tone: "alert", who: "Meera Iyer", text: "lagna changes inside ±12 min of the recorded time", action: "Rectify" },
    { id: "n2", tone: "amber", who: "Vikram Rao", text: "draft Lal Kitab upay, 2 remedies, review before sending", action: "Review" },
    { id: "n3", tone: "amber", who: "Sana Qureshi", text: "40-day remedy ends Tuesday, send a check-in", action: "Message" },
  ],
  sky: [
    { date: "16 Nov", title: "Sun enters Scorpio", touched: 9 },
    { date: "18 Nov", title: "Mercury stations retrograde", touched: 14 },
    { date: "20 Nov", title: "Amavasya", touched: 27 },
  ],
};

export const askFixture: AskThread = {
  question: "What supports her career now?",
  answer: [
    { text: "Her Moon dasha, running 2025 to 2035, is in its Mars period until Feb 2027. The Moon sits in the 6th house of work and service ", cite: 1 },
    { text: ". Saturn, lord of the 11th and 12th, is strong in its own sign in the 12th, which favours steady effort behind the scenes ", cite: 2 },
    { text: ". Mars debilitated in the 5th is the one caution ", cite: 3 },
    { text: "." },
  ],
  citations: [
    { n: 1, source: "Dashas", detail: "Moon / Mars, to Feb 2027" },
    { n: 2, source: "Planets", detail: "Saturn 22°20′ Aquarius, own sign" },
    { n: 3, source: "Planets", detail: "Mars 19°58′ Cancer, debilitated" },
  ],
  checks: { engine: "Engine · checked 4 facts", verifier: "Verifier · all claims match" },
  suggestions: ["Which remedy fits Mars?", "Compare with her D10"],
};

export const ananyaBundle: ChartBundle = {
  chartId: ANANYA_CHART_ID,
  client: { id: ANANYA_CLIENT_ID, name: "Ananya Sharma", initials: "AS" },
  artifact: (generated as unknown as { artifact: VedicChartArtifact }).artifact,
  lalKitab: (generated as unknown as { lalKitab: LalKitabReportJson }).lalKitab,
  birthLine: "15 Mar 1995, 06:42 IST, Varanasi",
  asked: askFixture,
};

export const lagnaPreviewFixture: LagnaPreview = {
  lagna: "Pisces lagna 10°32′",
  moon: "Moon in Magha pada 2, Leo",
  navamsaNote: "Navamsa lagna changes within ±14 min",
  safeNote:
    "Pisces holds until about 08:00, so the main chart is safe. The D9 lagna turns at 06:56, so rectify before reading marriage or the finer dasha timing.",
};
