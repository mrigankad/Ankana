import type { VedicChartArtifact } from "@astro/astrology-core";

import { getApiBaseUrl } from "./client";
import {
  newIdempotencyKey,
  v1Get,
  v1Patch,
  v1Post,
  v1Put,
  v1Request,
  v1Sse,
  type SseEvent,
} from "./v1";
import type { ChartReading } from "@/components/reading-panel";
import type { LalKitabReportJson } from "./types";

/* ------------------------------------------------------------------ models */

export interface ClientV1 {
  id: string;
  display_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  timezone: string | null;
  preferred_language: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashaNowV1 {
  maha: string;
  antar: string | null;
  antar_ends: string | null;
}

/** A client row from GET /v1/clients: the client plus what the list needs without opening charts. */
export interface ClientRowV1 extends ClientV1 {
  tags: string[];
  latest_chart_id: string | null;
  lagna_sign: string | null;
  lagna_degree: number | null;
  current_dasha: DashaNowV1 | null;
  last_consultation_at: string | null;
  next_consultation_at: string | null;
  next_follow_up: string | null;
  needs_rectify: boolean;
}

export interface ClientFacetsV1 {
  total: number;
  needs_rectify: number;
  follow_up_due: number;
  tags: Array<{ tag: string; count: number }>;
}

export type ClientSort = "recent" | "name" | "follow_up" | "last_consult";

export interface ClientListParams {
  q?: string;
  cursor?: string | null;
  limit?: number;
  tag?: string;
  needsRectify?: boolean;
  followUpDue?: boolean;
  sort?: ClientSort;
}

export interface ClientInput {
  display_name: string;
  contact_email?: string | null;
  contact_phone?: string | null;
  timezone?: string | null;
  preferred_language?: string | null;
}

export type ConsentPurpose = "chart_compute" | "ai_assistant" | "report_sharing" | "marketing";

export interface ConsentV1 {
  id: string;
  client_id: string;
  purpose: ConsentPurpose;
  notice_version: string;
  notice_text: string | null;
  notice_language: string | null;
  granted_at: string;
  withdrawn_at: string | null;
  channel: string | null;
}

export interface BirthRecordV1 {
  id: string;
  client_id: string;
  version: number;
  birth_date: string;
  birth_time: string | null;
  time_source: "certificate" | "memory" | "approximate" | "unknown";
  place_label: string;
  latitude: number;
  longitude: number;
  timezone_name: string;
  created_at: string;
}

export interface BirthRecordInput {
  birth_date: string;
  birth_time: string | null;
  time_source: BirthRecordV1["time_source"];
  place_label: string;
  latitude: number;
  longitude: number;
  timezone_name: string;
}

export interface ChartV1 {
  id: string;
  client_id: string;
  birth_record_id: string;
  settings: { ayanamsa?: string; node_type?: string; chart_style?: string; [k: string]: unknown };
  engine_version: string;
  created_at: string;
  created: boolean;
}

export interface ChartDetailV1 {
  chart: ChartV1;
  artifact: VedicChartArtifact;
  reading: ChartReading;
}

export interface ConsultationV1 {
  id: string;
  client_id: string;
  chart_artifact_id: string | null;
  consulted_at: string;
  scheduled_at?: string | null;
  mode: string | null;
  topic: string | null;
  created_at: string;
  notes?: NoteV1[];
}

export interface NoteV1 {
  id: string;
  consultation_id: string;
  body: string;
  created_at: string;
}

export interface RemedyItemV1 {
  id: string;
  plan_id: string;
  title: string;
  instructions: string | null;
  planet: string | null;
  sort_order: number;
  done_days: number;
}

export interface RemedyPlanV1 {
  id: string;
  client_id: string;
  title: string;
  status: "draft" | "active" | "completed" | "cancelled";
  cycle_days: number;
  start_date: string | null;
  end_date: string | null;
  day_number: number | null;
  missed_day_policy: string;
  items: RemedyItemV1[];
}

export interface RemedyPlanInput {
  title: string;
  consultation_id?: string | null;
  cycle_days?: number;
  missed_day_policy?: "restart" | "extend" | "ignore";
  items: Array<{ title: string; instructions?: string | null; planet?: string | null; sort_order?: number }>;
}

export interface ReportV1 {
  id: string;
  chart_id: string;
  status: "queued" | "running" | "done" | "failed" | string;
  template: string;
  language: "en" | "hi";
  sections: string[];
  error: string | null;
  size_bytes: number | null;
  download_url: string | null;
  download_expires_in: number | null;
}

export interface ReportInput {
  chart_id: string;
  template?: string;
  language?: "en" | "hi";
  sections?: string[];
  lal_kitab?: boolean;
  remedies?: boolean;
}

export interface ClientReportV1 {
  id: string;
  chart_id: string;
  status: "queued" | "running" | "done" | "failed" | string;
  template: string;
  template_version: string;
  language: "en" | "hi" | string;
  sections: string[] | null;
  error: string | null;
  created_at: string;
  size_bytes: number | null;
  download_url: string | null;
  download_expires_in: number | null;
}

export type TransitEventKind = "ingress" | "retrograde-station" | "direct-station" | "aspect" | "conjunction" | "sade_sati";
export type SadeSatiPhase = "rising" | "peak" | "setting";

export interface TransitEventV1 {
  date: string;
  planet: string;
  kind: TransitEventKind;
  sign: string;
  sign_index: number;
  house_from_lagna: number;
  house_from_moon: number;
  target: "moon" | "lagna" | null;
  aspect: number | null;
  phase: SadeSatiPhase | null;
}

export interface TransitTimelineV1 {
  chart_id: string;
  start: string;
  end: string;
  months: number;
  natal: { lagna_sign: string; moon_sign: string };
  sade_sati: {
    active_now: boolean;
    phase_now: SadeSatiPhase | null;
    phases: Array<{ phase: SadeSatiPhase; starts_at: string | null; ends_at: string | null }>;
  };
  events: TransitEventV1[];
}

export interface TodayConsultationV1 {
  id: string;
  client_id: string;
  client_name: string;
  at: string;
  topic: string | null;
  mode: string | null;
  chart_id: string | null;
  lagna_sign: string | null;
  lagna_degree: number | null;
  maha: string | null;
  antar: string | null;
  houses: Record<string, string[]>;
  status: "prepared" | "needs_birth_time" | "no_chart";
}

export interface TodaySkyEventV1 {
  at: string;
  planet: string;
  kind: "ingress" | "retrograde-station" | "direct-station" | "amavasya" | "purnima";
  sign: string;
  sign_index: number;
  clients_touched: number;
  client_ids: string[];
}

export interface TodayV1 {
  date: string;
  timezone: string;
  practitioner_name: string | null;
  consultations: TodayConsultationV1[];
  needs_you: {
    total: number;
    followups: number;
    missed_remedies: number;
    ended_plans: number;
    failed_sends: number;
    items: Array<{
      kind: "followup" | "missed_remedy" | "ended_plan" | "failed_send";
      client_id: string | null;
      client_name: string | null;
      detail: string | null;
      days: number | null;
    }>;
  };
  place: { label: string | null; latitude: number | null; longitude: number | null; source: "practice" | "timezone_default" | "unset" };
  panchang: {
    sunrise: string;
    sunset: string;
    vara: string;
    paksha: string;
    tithi: { name: string; ends_at: string };
    nakshatra: { name: string; ends_at: string };
    yoga: string;
    karana: string;
    moon_sign: string;
    sun_sign: string;
    rahu_kaal_start: string;
    rahu_kaal_end: string;
  } | null;
  sky: TodaySkyEventV1[];
  next_ingress: TodaySkyEventV1 | null;
}

export interface UsageV1 {
  billing: boolean;
  plan: string | null;
  plan_name: string | null;
  period: string;
  unlimited: boolean;
  meters: Array<{ metric: "reports" | "charts" | "ai_asks" | "clients"; used: number; limit: number | null; period: string }>;
}

export interface BrandingV1 {
  name: string;
  logo_url: string | null;
  brand_primary_color: string | null;
  brand_accent_color: string | null;
  brand_footer: string | null;
}

export interface AskCitation {
  index: number;
  tool: string;
  fact: string;
  anchor?: string;
}

export interface AskResult {
  answer: string;
  citations: AskCitation[];
  toolsUsed: string[];
  verification: { status: string; claimsChecked: number; claimsFailed: number; warnings?: string[] } | null;
  refused: boolean;
  refusalCategory: string | null;
  model?: string;
}

export interface LagnaPreviewV1 {
  lagna: { sign: string; sign_index: number; degrees_in_sign: number; nakshatra: string; pada: number };
  moon: { sign: string; nakshatra: string; pada: number };
  houses: Record<string, string[]>;
  sensitivity: {
    d1_minutes_before: number;
    d1_minutes_after: number;
    d1_holds_from: string;
    d1_holds_until: string;
    d9_minutes_before: number;
    d9_minutes_after: number;
    d9_holds_from: string;
    d9_holds_until: string;
    window_minutes: number;
    scan_minutes: number;
  };
}

/* ----------------------------------------------------------------- helpers */

/** Keys that the Lal Kitab view model keeps in snake_case (see fixtures/ananya.generated.json). */
const KEEP_SNAKE = new Set(["needs_review", "remedy_cite", "printed_page", "pdf_page", "ocr_confidence", "verified_from_image"]);

export function camelizeKeys<T = unknown>(value: unknown): T {
  if (Array.isArray(value)) return value.map((v) => camelizeKeys(v)) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const key = KEEP_SNAKE.has(k) ? k : k.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase());
      out[key] = camelizeKeys(v);
    }
    return out as T;
  }
  return value as T;
}

export function wasReused(res: { chart: ChartV1 }): boolean {
  return res.chart.created === false;
}

/* --------------------------------------------------------------------- api */

export const v1Api = {
  // clients
  listClients: (p: ClientListParams = {}) =>
    v1Get<{ clients: ClientRowV1[]; next_cursor: string | null; facets: ClientFacetsV1 }>("/clients", 8000, {
      q: p.q?.trim() || undefined,
      cursor: p.cursor ?? undefined,
      limit: p.limit ?? 50,
      tag: p.tag || undefined,
      needs_rectify: p.needsRectify ? true : undefined,
      follow_up_due: p.followUpDue ? true : undefined,
      sort: p.sort && p.sort !== "recent" ? p.sort : undefined,
    }),
  getClientTags: (id: string) => v1Get<{ tags: string[] }>(`/clients/${id}/tags`, 8000).then((r) => r.tags),
  setClientTags: (id: string, tags: string[]) => v1Put<{ tags: string[] }>(`/clients/${id}/tags`, { tags }).then((r) => r.tags),
  listClientTagCounts: () => v1Get<{ tags: Array<{ tag: string; count: number }> }>("/client-tags", 8000).then((r) => r.tags),
  listClientReports: (id: string) => v1Get<{ reports: ClientReportV1[] }>(`/clients/${id}/reports`, 8000).then((r) => r.reports),
  getToday: () => v1Get<TodayV1>("/today", 20000),
  getUsage: () => v1Get<UsageV1>("/usage", 8000),
  getTransitTimeline: (chartId: string, months = 12) =>
    v1Get<TransitTimelineV1>(`/charts/${chartId}/transits/timeline`, 30000, { months }),
  getClient: (id: string) => v1Get<{ client: ClientV1 }>(`/clients/${id}`, 8000).then((r) => r.client),
  createClient: (body: ClientInput) => v1Post<{ client: ClientV1 }>("/clients", body).then((r) => r.client),
  updateClient: (id: string, body: Partial<ClientInput>) => v1Patch<{ client: ClientV1 }>(`/clients/${id}`, body).then((r) => r.client),

  // consents
  getConsents: (clientId: string) =>
    v1Get<{ consents: ConsentV1[]; active: Record<string, boolean> }>(`/clients/${clientId}/consents`, 8000),
  recordConsent: (
    clientId: string,
    body: { purpose: ConsentPurpose; notice_version: string; notice_text?: string; notice_language?: string; channel?: string },
  ) => v1Post<{ consent: ConsentV1 }>(`/clients/${clientId}/consents`, body).then((r) => r.consent),
  withdrawConsent: (clientId: string, purpose: ConsentPurpose) =>
    v1Post<{ consent: ConsentV1 }>(`/clients/${clientId}/consents/${purpose}/withdraw`, {}),

  // birth records and charts
  listBirthRecords: (clientId: string) =>
    v1Get<{ birth_records: BirthRecordV1[] }>(`/clients/${clientId}/birth-records`, 8000).then((r) => r.birth_records),
  createBirthRecord: (clientId: string, body: BirthRecordInput) =>
    v1Post<{ birth_record: BirthRecordV1 }>(`/clients/${clientId}/birth-records`, body).then((r) => r.birth_record),
  generateChart: (
    clientId: string,
    body: { birth_record_id?: string; ayanamsa?: string; node_type?: "mean" | "true"; chart_style?: "north" | "south" | "east" },
    idempotencyKey?: string,
  ) =>
    v1Request<{ chart: ChartV1 }>("POST", `/clients/${clientId}/charts`, {
      body,
      idempotencyKey: idempotencyKey ?? newIdempotencyKey("chart"),
      timeoutMs: 30000,
    }),
  listCharts: (clientId: string) => v1Get<{ charts: ChartV1[] }>(`/clients/${clientId}/charts`, 8000).then((r) => r.charts),
  getChartDetail: (chartId: string) => v1Get<ChartDetailV1>(`/charts/${chartId}`, 20000),
  getPredictions: (chartId: string) => v1Get<{ predictions: unknown[] }>(`/charts/${chartId}/predictions`, 20000, { horizon_years: 5 }),
  getRemedies: (chartId: string) => v1Get<{ remedies: unknown[] }>(`/charts/${chartId}/remedies`, 20000),
  getTransits: (chartId: string) => v1Get<{ transits: unknown }>(`/charts/${chartId}/transits`, 20000),
  getLalKitab: (chartId: string, origin?: string) =>
    v1Get<{ lalKitab: Record<string, unknown> }>(`/charts/${chartId}/lal-kitab`, 20000, { origin }).then((r) =>
      camelizeKeys<LalKitabReportJson>(r.lalKitab),
    ),
  previewLagna: (body: { birth_date: string; birth_time: string; latitude: number; longitude: number; timezone_name: string }) =>
    v1Post<LagnaPreviewV1>("/charts/preview", body, { timeoutMs: 8000 }),

  // consultations
  listConsultations: (clientId: string) =>
    v1Get<{ consultations: ConsultationV1[] }>(`/clients/${clientId}/consultations`, 8000).then((r) => r.consultations),
  createConsultation: (
    clientId: string,
    body: { consulted_at?: string; scheduled_at?: string; follow_up_date?: string; mode?: string; topic?: string; chart_artifact_id?: string; note?: string },
  ) => v1Post<{ consultation: ConsultationV1 }>(`/clients/${clientId}/consultations`, body).then((r) => r.consultation),
  getConsultation: (id: string) => v1Get<{ consultation: ConsultationV1 }>(`/consultations/${id}`, 8000).then((r) => r.consultation),
  addNote: (consultationId: string, body: string) =>
    v1Post<{ note: NoteV1 }>(`/consultations/${consultationId}/notes`, { body }).then((r) => r.note),
  deleteNote: (consultationId: string, noteId: string) => v1Request<void>("DELETE", `/consultations/${consultationId}/notes/${noteId}`),

  // remedy plans
  listRemedyPlans: (clientId: string) =>
    v1Get<{ remedy_plans: RemedyPlanV1[] }>(`/clients/${clientId}/remedy-plans`, 8000).then((r) => r.remedy_plans),
  createRemedyPlan: (clientId: string, body: RemedyPlanInput) =>
    v1Post<{ remedy_plan: RemedyPlanV1 }>(`/clients/${clientId}/remedy-plans`, body).then((r) => r.remedy_plan),
  getRemedyPlan: (id: string) => v1Get<{ remedy_plan: RemedyPlanV1 }>(`/remedy-plans/${id}`, 8000).then((r) => r.remedy_plan),
  startRemedyPlan: (id: string, startDate?: string) =>
    v1Post<{ remedy_plan: RemedyPlanV1 }>(`/remedy-plans/${id}/start`, startDate ? { start_date: startDate } : {}).then((r) => r.remedy_plan),
  checkinRemedyItem: (planId: string, itemId: string, body: { done?: boolean; checkin_date?: string; note?: string } = {}) =>
    v1Post<{ checkin: unknown }>(`/remedy-plans/${planId}/items/${itemId}/checkins`, body),
  completeRemedyPlan: (id: string) => v1Post<{ remedy_plan: RemedyPlanV1 }>(`/remedy-plans/${id}/complete`, {}).then((r) => r.remedy_plan),
  cancelRemedyPlan: (id: string) => v1Post<{ remedy_plan: RemedyPlanV1 }>(`/remedy-plans/${id}/cancel`, {}).then((r) => r.remedy_plan),

  // reports
  createReport: (body: ReportInput) => v1Post<ReportV1>("/reports", body, { idempotencyKey: newIdempotencyKey("report") }),
  getReport: (id: string) => v1Get<ReportV1>(`/reports/${id}`, 8000),

  // branding
  getBranding: () => v1Get<BrandingV1>("/practice/branding", 8000),
  updateBranding: (body: Omit<BrandingV1, "name">) => v1Put<BrandingV1>("/practice/branding", body),
};

/** POST /v1/reports, then poll until the PDF is signed and ready. Resolves with the final report. */
export async function renderReport(
  body: ReportInput,
  onUpdate?: (r: ReportV1) => void,
  opts: { intervalMs?: number; timeoutMs?: number; signal?: AbortSignal } = {},
): Promise<ReportV1> {
  let report = await v1Api.createReport(body);
  onUpdate?.(report);
  const started = Date.now();
  const interval = opts.intervalMs ?? 1200;
  const limit = opts.timeoutMs ?? 120_000;
  while (report.status !== "done" && report.status !== "failed") {
    if (opts.signal?.aborted) throw new DOMException("aborted", "AbortError");
    if (Date.now() - started > limit) throw new Error("The report is taking longer than expected. It will keep rendering; check back shortly.");
    await new Promise((r) => setTimeout(r, interval));
    report = await v1Api.getReport(report.id);
    onUpdate?.(report);
  }
  return report;
}

export interface AskHandlers {
  onStatus?: (message: string) => void;
  onAnswer?: (a: AskResult) => void;
}

/** Stream an assistant answer over SSE. Resolves with the final answer. */
export async function askChart(
  chartId: string,
  body: { question: string; history?: Array<{ role: "user" | "assistant"; content: string }>; deep?: boolean },
  handlers: AskHandlers = {},
  signal?: AbortSignal,
): Promise<AskResult> {
  let final: AskResult | null = null;
  for await (const ev of v1Sse(`/charts/${chartId}/ask`, { ...body, stream: true }, signal) as AsyncGenerator<SseEvent>) {
    if (ev.event === "status") handlers.onStatus?.((ev.data as { message?: string }).message ?? "");
    else if (ev.event === "answer") {
      final = ev.data as AskResult;
      handlers.onAnswer?.(final);
    } else if (ev.event === "error") {
      throw new Error((ev.data as { message?: string }).message ?? "The assistant failed.");
    }
  }
  if (!final) throw new Error("The assistant returned no answer.");
  return final;
}

/** Signed download URLs from the local storage backend are API-relative. */
export function absoluteDownloadUrl(url: string) {
  return url.startsWith("/") ? `${getApiBaseUrl()}${url}` : url;
}
