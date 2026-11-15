import type { VedicChartArtifact } from "@astro/astrology-core";
import type { LocationSearchResult } from "@astro/shared-types";

import type { IntakeSubmit, LagnaPreviewView } from "./intake";
import type { ChartReading } from "@/components/reading-panel";

/**
 * View-model contracts for the practitioner app. These are deliberately small and
 * hand-written. When the generated client from services/api-py/openapi.json lands,
 * swap the implementation behind `AnkanaApi` (lib/api/client.ts) and map the
 * generated types onto these shapes; screens only depend on this file.
 */

/** Free-text practitioner tag. "Lal Kitab", "Matching" and "Rectify" have their own chip colours. */
export type ClientTag = string;

export interface ClientRow {
  id: string;
  /** Latest chart job id, when a chart exists. */
  chartId: string | null;
  initials: string;
  name: string;
  /** "15 Mar 1995, Varanasi" */
  birthLine: string;
  lagna: string;
  dasha: string;
  lastConsult: string;
  nextFollowUp: string;
  tags: ClientTag[];
}

export interface ConsultCard {
  id: string;
  /** The client the visit is for; the Brief opens on it. */
  clientId?: string;
  time: string;
  clientName: string;
  chartId: string | null;
  kind: "chart" | "match";
  /** Short chip, e.g. "Prepared", "Needs birth time", "Lal Kitab", "Matching". */
  status: { label: string; tone: "ok" | "alert" | "accent" | "ink" };
  topic: string;
  /** Headline inside the tile, e.g. "Pisces lagna", "Match 28/36". */
  headline: string;
  /** Live rows: a translatable template and its values, used instead of `headline` when set. */
  headlineKey?: string;
  headlineParams?: Record<string, string>;
  sub: string;
  /** Live rows: running dasha lords, shown as "Moon / Mars dasha" in the language in use. */
  dasha?: { maha: string; antar: string | null };
  /** House number (1..12) to planet abbreviations, for the tile mini chart (north style). */
  miniHouses?: Record<number, string[]>;
}

export interface NeedsYouItem {
  id: string;
  tone: "alert" | "amber";
  who: string;
  text: string;
  action: string;
  /** Live rows: a translatable template and values for `text`, and where the action goes. */
  textKey?: string;
  textParams?: Record<string, string | number>;
  href?: string;
}

export interface SkyItem {
  date: string;
  title: string;
  touched: number;
  /** Live rows: the event as data, so the title can be written in the language in use. */
  kind?: "ingress" | "retrograde-station" | "direct-station" | "amavasya" | "purnima";
  planet?: string;
  sign?: string;
}

export interface TodayView {
  practitioner: { name: string; firstName: string; practice: string; initials: string };
  dateLine: string;
  consultCount: number;
  /** Null when the practice has no place and its time zone has no default city. */
  panchang: {
    vara: string;
    varaDeva: string;
    sunrise: string;
    /** Live: the place the panchang is read for. */
    place?: string;
    tithi: { name: string; until: string; paksha?: string; untilTime?: string };
    nakshatra: { name: string; until: string; untilTime?: string };
    rahuKaal: { range: string; note: string; from?: string; to?: string };
    ingress: { title: string; note: string; planet?: string; sign?: string; date?: string; touched?: number } | null;
  } | null;
  consults: ConsultCard[];
  needsYou: NeedsYouItem[];
  sky: SkyItem[];
  /** Live: local date (YYYY-MM-DD) and zone, so the date line can be written in the language in use. */
  dateIso?: string;
  timezone?: string;
  /** Live: the first booking of the day, for the sentence under the greeting. */
  first?: { name: string; time: string; status: "prepared" | "needs_birth_time" | "no_chart" };
}

export interface WorkspaceMeta {
  clientCount: number;
  needsYouCount: number;
  reportsUsed: number;
  /** Null means unlimited (billing is off). */
  reportsQuota: number | null;
  engine: string;
  practitioner: { name: string; practice: string; initials: string };
  consults: Array<{ clientName: string; time: string; active: boolean }>;
}

export interface ChartBundle {
  chartId: string;
  client: { id: string; name: string; initials: string };
  artifact: VedicChartArtifact;
  /** Output of lalKitabReport() from packages/lal-kitab (JSON shape). */
  lalKitab: LalKitabReportJson;
  birthLine: string;
  asked: AskThread;
  /** Present in live mode (served with the chart). */
  reading?: ChartReading;
}

export interface AskThread {
  question: string;
  answer: Array<{ text: string; cite?: number }>;
  citations: Array<{ n: number; source: string; detail: string }>;
  checks: { engine: string; verifier: string };
  suggestions: string[];
}

export interface LalKitabReportJson {
  origin: string;
  chart: { houses: string[][]; planetHouse: Record<string, number>; lagnaSignIndex: number | null };
  sleepingPlanets: Array<{ planet: string; house: number; wakesAt?: number; reason?: string }>;
  sleepingHouses: unknown[];
  aspects: unknown[];
  rin: Array<{ id?: string; kind?: string; title?: string; planet?: string; house?: number; why?: string; cite?: { page?: number } }>;
  masnui: unknown[];
  planetHouse: unknown[];
  varshphal: unknown;
  remedies: unknown;
  [key: string]: unknown;
}

export interface IntakeInput {
  clientName: string;
  birthDate: string;
  birthTime: string;
  timeSource: "certificate" | "memory" | "approximate" | "unknown";
  place: string;
  ayanamsha: "lahiri";
  style: "north" | "south";
  lalKitab: boolean;
}

export interface LagnaPreview {
  lagna: string;
  moon: string;
  navamsaNote: string;
  safeNote: string;
}

/** The single seam between screens and the backend. */
export interface AnkanaApi {
  getWorkspace(): Promise<WorkspaceMeta>;
  getToday(): Promise<TodayView>;
  listClients(): Promise<ClientRow[]>;
  getClient(id: string): Promise<{ row: ClientRow; chartId: string | null }>;
  getChart(chartId: string): Promise<ChartBundle>;
  previewLagna(input: { birthDate: string; birthTime: string; location: LocationSearchResult }): Promise<LagnaPreviewView>;
  getClientDetail(id: string): Promise<ClientDetail>;
  searchLocations(q: string): Promise<LocationSearchResult[]>;
  /** Creates (or reuses) the client, saves the birth record and queues the chart job. */
  submitIntake(input: IntakeSubmit): Promise<{ clientId: string; chartId: string; reused?: boolean }>;
}

export interface ClientDetailChart {
  id: string;
  kind: "d1" | "match" | "varsha";
  title: string;
  sub: string;
  miniHouses?: Record<number, string[]>;
}

export interface ClientDetailRemedy {
  title: string;
  day: number;
  total: number;
  note: string;
}

export interface ClientDetailFact {
  label: string;
  value: string;
  note: string;
}

export interface ClientDetailReport {
  title: string;
  sent: string;
  status: string;
  tone?: "ok" | "alert" | "accent" | "muted";
  /** Live rows: translatable sentence parts and the signed download link, when the PDF is ready. */
  sentKey?: string;
  sentParams?: Record<string, string>;
  href?: string;
}

/** Everything the Client screen (U03) shows. Sections are empty for clients without history. */
export interface ClientDetail {
  row: ClientRow;
  chartId: string | null;
  /** Reads "Born ..., Pisces lagna ..., Moon in ...". Empty when unknown. */
  bornLine: string;
  consultToday: string | null;
  timeConfirmed: string | null;
  charts: ClientDetailChart[];
  consultations: Array<{ when: string; title: string; note: string }>;
  remedies: ClientDetailRemedy[];
  reports: ClientDetailReport[];
  /** Lagna, running period, moon, worth raising. */
  facts: ClientDetailFact[];
}
