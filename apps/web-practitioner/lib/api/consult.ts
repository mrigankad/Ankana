import { isFixtures } from "./client";
import { ANANYA_CHART_ID, ANANYA_CLIENT_ID, ananyaBundle } from "./fixtures";
import type { ConsultationV1 } from "./live";
import { v1Get, v1Patch, v1Post, v1Put, v1Request } from "./v1";

/* ------------------------------------------------------------------ models */

export type FactType = "planet" | "dasha" | "yoga" | "transit" | "lal_kitab";

/** A chart fact pinned in a note. The note body holds {{fact:<id>}} where its chip sits. */
export interface NoteFact {
  id: string;
  type: FactType;
  ref: string;
  label: string;
}

export interface ChartFactOption {
  type: FactType;
  ref: string;
  label: string;
  group: string;
}

export interface NoteFull {
  id: string;
  consultation_id: string;
  body: string;
  facts: NoteFact[];
  created_at: string;
}

export interface ConsultationFull extends Omit<ConsultationV1, "notes"> {
  follow_up_date: string | null;
  client_question: string | null;
  notes: NoteFull[];
}

export type PredictionStatus = "pending" | "came_true" | "did_not" | "unclear";

export interface PredictionV1 {
  id: string;
  client_id: string;
  consultation_id: string;
  statement: string;
  window_start: string | null;
  window_end: string | null;
  status: PredictionStatus;
  outcome_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface PredictionDraft {
  id?: string | null;
  statement: string;
  window_start: string | null;
  window_end: string | null;
}

export interface SummaryBody {
  topics: string[];
  remedies_given: string[];
  follow_up_date: string | null;
  predictions: PredictionDraft[];
  source?: "manual" | "ai";
}

export interface SummaryV1 extends Required<Omit<SummaryBody, "predictions" | "source">> {
  consultation_id: string;
  source: "manual" | "ai";
  updated_at: string;
  predictions: PredictionV1[];
}

export interface DraftResult {
  summary: SummaryBody;
  verification: { status: "ok" | "mismatch" | "no_chart"; mismatches: Array<{ text: string; reason: string; correct: string }> };
  model: string | null;
}

export interface BriefTransit {
  date: string;
  planet: string;
  kind: string;
  sign: string;
  house_from_moon: number;
  house_from_lagna: number;
  target: string | null;
  aspect: number | null;
  phase: string | null;
}

export interface BriefV1 {
  client_id: string;
  chart_id: string | null;
  consultation_id: string | null;
  generated_at: string;
  dasha: { maha: string; maha_ends: string; antar: string | null; antar_ends: string | null } | null;
  transits: BriefTransit[];
  sade_sati: { active: boolean; phase: string | null; ends_at: string | null } | null;
  remedies: Array<{
    plan_id: string;
    title: string;
    status: string;
    day_number: number | null;
    cycle_days: number;
    end_date: string | null;
    adherence_pct: number | null;
  }>;
  last_consultation: { id: string; at: string; topic: string | null; excerpt: string | null } | null;
  follow_ups: Array<{ consultation_id: string; date: string; overdue: boolean }>;
  open_predictions: Array<{ id: string; statement: string; window_start: string | null; window_end: string | null; due: boolean }>;
  stated_question: string | null;
}

export type LifeKind = "marriage" | "child" | "job" | "business" | "move" | "education" | "health" | "loss" | "travel" | "other";
export const LIFE_KINDS: LifeKind[] = ["marriage", "child", "job", "business", "move", "education", "health", "loss", "travel", "other"];

export interface LifeEventV1 {
  id: string;
  client_id: string;
  event_date: string;
  kind: LifeKind;
  title: string;
  notes: string | null;
}

export interface TimelineEventV1 {
  id: string;
  kind: "consultation" | "prediction" | "remedy" | "report" | "life_event";
  at: string;
  title: string;
  detail: string | null;
  status: string | null;
  ref_id: string | null;
}

/* ------------------------------------------------------------------ helpers */

const FACT_MARKER = /\{\{fact:([A-Za-z0-9_-]{1,16})\}\}/g;

/** Split a note body into text and fact pieces, in order. A marker without a fact stays text. */
export function splitNoteBody(body: string, facts: NoteFact[]): Array<{ text: string } | { fact: NoteFact }> {
  const byId = new Map(facts.map((f) => [f.id, f]));
  const out: Array<{ text: string } | { fact: NoteFact }> = [];
  let last = 0;
  for (const m of body.matchAll(FACT_MARKER)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push({ text: body.slice(last, idx) });
    const fact = byId.get(m[1]!);
    out.push(fact ? { fact } : { text: m[0] });
    last = idx + m[0].length;
  }
  if (last < body.length) out.push({ text: body.slice(last) });
  return out;
}

export const FACT_TAB: Record<FactType, string> = {
  planet: "planets",
  dasha: "dashas",
  yoga: "yogas",
  transit: "transits",
  lal_kitab: "lal-kitab",
};

/** Where a chip leads: the chart tab that shows the fact. */
export function factHref(chartId: string | null, fact: Pick<NoteFact, "type">): string | null {
  return chartId ? `/charts/${chartId}?tab=${FACT_TAB[fact.type]}` : null;
}

export function newFactId(): string {
  return Math.random().toString(36).slice(2, 8);
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const d = (iso: string) => iso.slice(0, 10);

/* ------------------------------------------------------------------ fixtures */

const FX_NOW = "2026-11-14T09:00:00.000Z";
let seq = 100;
const fid = (p: string) => `${p}-${++seq}`;

interface FxStore {
  consultations: ConsultationFull[];
  summaries: Record<string, SummaryV1>;
  predictions: PredictionV1[];
  life: LifeEventV1[];
}

function seedFixtures(): FxStore {
  const c = (id: string, at: string, topic: string, extra: Partial<ConsultationFull> = {}): ConsultationFull => ({
    id,
    client_id: ANANYA_CLIENT_ID,
    chart_artifact_id: ANANYA_CHART_ID,
    consulted_at: at,
    scheduled_at: null,
    mode: "in_person",
    topic,
    created_at: at,
    follow_up_date: null,
    client_question: null,
    notes: [],
    ...extra,
  });
  const note = (cid: string, at: string, body: string, facts: NoteFact[]): NoteFull => ({ id: fid("note"), consultation_id: cid, body, facts, created_at: at });
  const consultations: ConsultationFull[] = [
    c("cons-ananya-3", "2026-11-14T06:00:00.000Z", "Career question, 2nd visit", {
      scheduled_at: "2026-11-14T06:00:00.000Z",
      client_question: "Should I take the Pune offer, and when is the right time to move?",
      notes: [
        note("cons-ananya-3", "2026-11-13T18:00:00.000Z", "Open with {{fact:a}} and the {{fact:b}} period that runs to Feb 2027. Ask about the Pune offer and the timing of the move.", [
          { id: "a", type: "planet", ref: "planet:jupiter", label: "Jupiter in Scorpio, house 9" },
          { id: "b", type: "dasha", ref: "dasha:moon/mars", label: "Moon / Mars, until 2027-02" },
        ]),
      ],
    }),
    c("cons-ananya-2", "2026-10-24T10:00:00.000Z", "Marriage matching, 45 min", {
      follow_up_date: "2026-11-10",
      notes: [
        note("cons-ananya-2", "2026-10-24T11:00:00.000Z", "Compared with Rohit Mehta. Ashtakoot 27 of 36, with {{fact:a}} noted for both families. Advised a muhurta after Makar Sankranti. Family to confirm.", [
          { id: "a", type: "planet", ref: "planet:mars", label: "Mars in Cancer, house 5, retrograde" },
        ]),
      ],
    }),
    c("cons-ananya-1", "2026-09-12T10:00:00.000Z", "First consultation, birth time check", {
      notes: [
        note("cons-ananya-1", "2026-09-12T11:00:00.000Z", "Hospital certificate seen and photographed. Lagna stable. Began a 43-day Saturn remedy ({{fact:a}}) and a Thursday fast.", [
          { id: "a", type: "lal_kitab", ref: "lal_kitab:saturn_h12", label: "Saturn in Lal Kitab house 12" },
        ]),
      ],
    }),
  ];
  const predictions: PredictionV1[] = [
    { id: "pred-1", client_id: ANANYA_CLIENT_ID, consultation_id: "cons-ananya-2", statement: "A muhurta for the engagement opens after Makar Sankranti", window_start: "2027-01-15", window_end: "2027-03-15", status: "pending", outcome_note: null, resolved_at: null, created_at: "2026-10-24T11:30:00.000Z" },
    { id: "pred-2", client_id: ANANYA_CLIENT_ID, consultation_id: "cons-ananya-1", statement: "A senior role is offered within the Moon / Mars period", window_start: "2026-09-12", window_end: "2026-11-01", status: "came_true", outcome_note: "The Pune offer arrived in October.", resolved_at: "2026-11-02T08:00:00.000Z", created_at: "2026-09-12T11:30:00.000Z" },
  ];
  const summaries: Record<string, SummaryV1> = {
    "cons-ananya-1": { consultation_id: "cons-ananya-1", topics: ["Birth time check", "Career direction"], remedies_given: ["Saturn: lamp at a peepal, Saturdays", "Jupiter: Thursday fast, yellow dal"], follow_up_date: null, source: "manual", updated_at: "2026-09-12T12:00:00.000Z", predictions: [predictions[1]!] },
    "cons-ananya-2": { consultation_id: "cons-ananya-2", topics: ["Marriage matching", "Mars in the 5th"], remedies_given: [], follow_up_date: "2026-11-10", source: "manual", updated_at: "2026-10-24T12:00:00.000Z", predictions: [predictions[0]!] },
  };
  const life: LifeEventV1[] = [
    { id: "life-1", client_id: ANANYA_CLIENT_ID, event_date: "2025-06-02", kind: "job", title: "Joined the Mumbai bank as an analyst", notes: null },
    { id: "life-2", client_id: ANANYA_CLIENT_ID, event_date: "2026-10-09", kind: "job", title: "Received the Pune offer letter", notes: "Decision pending until she meets the practitioner." },
  ];
  return { consultations, summaries, predictions, life };
}

let store: FxStore | null = null;
const fx = () => (store ??= seedFixtures());
const isAnanya = (clientId: string) => clientId === ANANYA_CLIENT_ID;

function fixtureFacts(): ChartFactOption[] {
  const a = ananyaBundle.artifact;
  const out: ChartFactOption[] = [];
  for (const p of a.planets) {
    out.push({ type: "planet", ref: `planet:${p.planet}`, group: "Planets", label: `${cap(p.planet)} in ${p.signName}, house ${p.house}${p.retrograde ? ", retrograde" : ""}` });
  }
  for (const m of a.vimshottari.mahadashas) {
    out.push({ type: "dasha", ref: `dasha:${m.planet}`, group: "Dashas", label: `${cap(m.planet)} dasha, ${m.start.slice(0, 4)} to ${m.end.slice(0, 4)}` });
  }
  const run = a.vimshottari.mahadashas.find((m) => m.planet === "moon");
  for (const s of run?.children ?? []) out.push({ type: "dasha", ref: `dasha:moon/${s.planet}`, group: "Dashas", label: `Moon / ${cap(s.planet)}, until ${s.end.slice(0, 7)}` });
  for (const y of a.yogas) if (y.present) out.push({ type: "yoga", ref: `yoga:${y.key}`, group: "Yogas", label: y.name });
  for (const t of fixtureTransits()) out.push({ type: "transit", ref: `transit:${t.planet}:${d(t.date)}`, group: "Transits", label: `${cap(t.planet)} ${t.kind.replace(/-/g, " ")}, ${cap(t.sign)} on ${d(t.date)}` });
  for (const [planet, house] of Object.entries(ananyaBundle.lalKitab.chart.planetHouse)) {
    out.push({ type: "lal_kitab", ref: `lal_kitab:${planet}_h${house}`, group: "Lal Kitab", label: `${cap(planet)} in Lal Kitab house ${house}` });
  }
  return out;
}

function fixtureTransits(): BriefTransit[] {
  return [
    { date: "2026-11-27T04:10:00Z", planet: "saturn", kind: "direct-station", sign: "pisces", house_from_moon: 8, house_from_lagna: 1, target: null, aspect: null, phase: null },
    { date: "2026-12-13T21:30:00Z", planet: "jupiter", kind: "retrograde-station", sign: "leo", house_from_moon: 1, house_from_lagna: 6, target: null, aspect: null, phase: null },
    { date: "2027-03-29T07:45:00Z", planet: "saturn", kind: "ingress", sign: "aries", house_from_moon: 9, house_from_lagna: 2, target: null, aspect: null, phase: null },
  ];
}

function fixtureBrief(clientId: string, consultationId?: string): BriefV1 {
  if (!isAnanya(clientId)) {
    return { client_id: clientId, chart_id: null, consultation_id: consultationId ?? null, generated_at: FX_NOW, dasha: null, transits: [], sade_sati: null, remedies: [], last_consultation: null, follow_ups: [], open_predictions: [], stated_question: null };
  }
  const s = fx();
  const visits = s.consultations.filter((c) => c.client_id === clientId);
  const target = visits.find((c) => c.id === (consultationId ?? "cons-ananya-3")) ?? visits[0]!;
  const last = visits.filter((c) => c.id !== target.id && (c.scheduled_at ?? c.consulted_at) <= FX_NOW).sort((a, b) => (b.scheduled_at ?? b.consulted_at).localeCompare(a.scheduled_at ?? a.consulted_at))[0];
  const sum = last ? s.summaries[last.id] : undefined;
  return {
    client_id: clientId,
    chart_id: ANANYA_CHART_ID,
    consultation_id: target.id,
    generated_at: FX_NOW,
    dasha: { maha: "moon", maha_ends: "2035-09-24T00:00:00Z", antar: "mars", antar_ends: "2027-02-23T00:00:00Z" },
    transits: fixtureTransits(),
    sade_sati: { active: false, phase: null, ends_at: null },
    remedies: [
      { plan_id: "plan-saturn", title: "Saturn: lamp at a peepal, Saturdays", status: "active", day_number: 31, cycle_days: 43, end_date: "2026-11-25", adherence_pct: 90 },
      { plan_id: "plan-jupiter", title: "Jupiter: Thursday fast, yellow dal", status: "active", day_number: 19, cycle_days: 43, end_date: "2026-12-03", adherence_pct: 74 },
      { plan_id: "plan-moon", title: "Moon: water to Shiva, Mondays", status: "active", day_number: 41, cycle_days: 43, end_date: "2026-11-16", adherence_pct: 100 },
    ],
    last_consultation: last ? { id: last.id, at: last.scheduled_at ?? last.consulted_at, topic: last.topic, excerpt: sum?.topics.join("; ") ?? null } : null,
    follow_ups: visits.filter((c) => c.follow_up_date).map((c) => ({ consultation_id: c.id, date: c.follow_up_date!, overdue: c.follow_up_date! < d(FX_NOW) })),
    open_predictions: s.predictions.filter((p) => p.client_id === clientId && p.status === "pending").map((p) => ({ id: p.id, statement: p.statement, window_start: p.window_start, window_end: p.window_end, due: Boolean(p.window_end && p.window_end < d(FX_NOW)) })),
    stated_question: target.client_question,
  };
}

function fixtureTimeline(clientId: string): TimelineEventV1[] {
  if (!isAnanya(clientId)) return [];
  const s = fx();
  const ev: TimelineEventV1[] = [];
  for (const c of s.consultations) ev.push({ id: `consultation:${c.id}`, kind: "consultation", at: c.scheduled_at ?? c.consulted_at, title: c.topic ?? "Consultation", detail: s.summaries[c.id]?.topics.join("; ") ?? null, status: null, ref_id: c.id });
  for (const p of s.predictions) ev.push({ id: `prediction:${p.id}`, kind: "prediction", at: p.created_at, title: p.statement, detail: `${p.window_start ?? "..."} to ${p.window_end ?? "..."}`, status: p.status, ref_id: p.id });
  for (const l of s.life) ev.push({ id: `life_event:${l.id}`, kind: "life_event", at: `${l.event_date}T00:00:00Z`, title: l.title, detail: l.notes, status: l.kind, ref_id: l.id });
  ev.push({ id: "remedy:plan-saturn", kind: "remedy", at: "2026-09-12T00:00:00Z", title: "Saturn: lamp at a peepal, Saturdays", detail: "43 days", status: "active", ref_id: "plan-saturn" });
  ev.push({ id: "remedy:plan-jupiter", kind: "remedy", at: "2026-10-26T00:00:00Z", title: "Jupiter: Thursday fast, yellow dal", detail: "43 days", status: "active", ref_id: "plan-jupiter" });
  ev.push({ id: "report:r1", kind: "report", at: "2026-10-24T12:30:00Z", title: "Career and dasha report", detail: "EN", status: "done", ref_id: null });
  ev.push({ id: "report:r2", kind: "report", at: "2026-09-12T12:30:00Z", title: "Lal Kitab remedies report", detail: "EN", status: "done", ref_id: null });
  return ev.sort((a, b) => b.at.localeCompare(a.at));
}

function fixtureDraft(c: ConsultationFull): DraftResult {
  const text = c.notes.map((n) => n.body.replace(FACT_MARKER, (_m, id: string) => n.facts.find((f) => f.id === id)?.label ?? "")).join(" ");
  const sentences = text.split(/(?<=\.)\s+/).map((x) => x.trim()).filter(Boolean);
  return {
    summary: {
      topics: [c.topic ?? "Consultation"],
      remedies_given: sentences.filter((x) => /remedy|fast|lamp|mantra/i.test(x)).slice(0, 2),
      follow_up_date: null,
      predictions: sentences.filter((x) => /timing|muhurta|move/i.test(x)).slice(0, 1).map((x) => ({ statement: x.replace(/\.$/, ""), window_start: null, window_end: null })),
      source: "ai",
    },
    verification: { status: "ok", mismatches: [] },
    model: null,
  };
}

/* --------------------------------------------------------------------- api */

type NoteWire = Omit<NoteFull, "facts"> & { facts?: NoteFact[] };
type ConsultWire = Omit<ConsultationFull, "notes" | "follow_up_date" | "client_question"> & {
  notes?: NoteWire[];
  follow_up_date?: string | null;
  client_question?: string | null;
};

const fullConsult = (c: ConsultWire): ConsultationFull => ({
  ...c,
  follow_up_date: c.follow_up_date ?? null,
  client_question: c.client_question ?? null,
  notes: (c.notes ?? []).map((n) => ({ ...n, facts: n.facts ?? [] })),
});

export interface NewConsultation {
  topic?: string;
  note?: string;
  note_facts?: NoteFact[];
  client_question?: string;
  chart_artifact_id?: string;
  scheduled_at?: string;
  follow_up_date?: string;
}

const CHANGED = "ankana:consult-changed";
/** Panels that show consultation data re-read after any write made through consultApi. */
export function onConsultChanged(cb: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener(CHANGED, cb);
  return () => window.removeEventListener(CHANGED, cb);
}
const announce = () => {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(CHANGED));
};

const api = {
  async listConsultations(clientId: string): Promise<ConsultationFull[]> {
    if (isFixtures()) return fx().consultations.filter((c) => c.client_id === clientId);
    const list = await v1Get<{ consultations: ConsultWire[] }>(`/clients/${clientId}/consultations`, 8000).then((r) => r.consultations);
    return (await Promise.all(list.map((c) => v1Get<{ consultation: ConsultWire }>(`/consultations/${c.id}`, 8000).then((r) => r.consultation).catch(() => c)))).map(fullConsult);
  },
  async createConsultation(clientId: string, body: NewConsultation): Promise<void> {
    if (isFixtures()) {
      const id = fid("cons");
      const at = new Date(FX_NOW).toISOString();
      fx().consultations.unshift({
        id, client_id: clientId, chart_artifact_id: body.chart_artifact_id ?? null, consulted_at: body.scheduled_at ?? at, scheduled_at: body.scheduled_at ?? null, mode: "in_person",
        topic: body.topic ?? null, created_at: at, follow_up_date: body.follow_up_date ?? null, client_question: body.client_question ?? null,
        notes: body.note ? [{ id: fid("note"), consultation_id: id, body: body.note, facts: body.note_facts ?? [], created_at: at }] : [],
      });
      return;
    }
    await v1Post(`/clients/${clientId}/consultations`, { ...body, mode: "in_person" });
  },
  async addNote(consultationId: string, body: string, facts: NoteFact[]): Promise<void> {
    if (isFixtures()) {
      const c = fx().consultations.find((x) => x.id === consultationId);
      c?.notes.push({ id: fid("note"), consultation_id: consultationId, body, facts, created_at: FX_NOW });
      return;
    }
    await v1Post(`/consultations/${consultationId}/notes`, { body, facts });
  },
  async getChartFacts(clientId: string): Promise<{ chart_id: string | null; facts: ChartFactOption[] }> {
    if (isFixtures()) return isAnanya(clientId) ? { chart_id: ANANYA_CHART_ID, facts: fixtureFacts() } : { chart_id: null, facts: [] };
    return v1Get(`/clients/${clientId}/chart-facts`, 30000);
  },
  async getBrief(clientId: string, consultationId?: string): Promise<BriefV1> {
    if (isFixtures()) return fixtureBrief(clientId, consultationId);
    return v1Get<BriefV1>(`/clients/${clientId}/brief`, 30000, { consultation_id: consultationId });
  },
  async getSummary(consultationId: string): Promise<SummaryV1 | null> {
    if (isFixtures()) return fx().summaries[consultationId] ?? null;
    return v1Get<{ summary: SummaryV1 | null }>(`/consultations/${consultationId}/summary`, 8000).then((r) => r.summary);
  },
  async saveSummary(consultationId: string, body: SummaryBody): Promise<SummaryV1> {
    if (isFixtures()) {
      const s = fx();
      const c = s.consultations.find((x) => x.id === consultationId);
      if (!c) throw new Error("Consultation not found");
      c.follow_up_date = body.follow_up_date;
      const keep = new Set(body.predictions.map((p) => p.id).filter(Boolean));
      s.predictions = s.predictions.filter((p) => p.consultation_id !== consultationId || p.status !== "pending" || keep.has(p.id));
      for (const p of body.predictions) {
        const row = p.id ? s.predictions.find((x) => x.id === p.id) : undefined;
        if (row) Object.assign(row, { statement: p.statement, window_start: p.window_start, window_end: p.window_end });
        else s.predictions.push({ id: fid("pred"), client_id: c.client_id, consultation_id: consultationId, statement: p.statement, window_start: p.window_start, window_end: p.window_end, status: "pending", outcome_note: null, resolved_at: null, created_at: FX_NOW });
      }
      const out: SummaryV1 = { consultation_id: consultationId, topics: body.topics, remedies_given: body.remedies_given, follow_up_date: body.follow_up_date, source: body.source ?? "manual", updated_at: FX_NOW, predictions: s.predictions.filter((p) => p.consultation_id === consultationId) };
      s.summaries[consultationId] = out;
      return out;
    }
    return v1Put<SummaryV1>(`/consultations/${consultationId}/summary`, body);
  },
  async draftSummary(consultationId: string): Promise<DraftResult> {
    if (isFixtures()) {
      const c = fx().consultations.find((x) => x.id === consultationId);
      if (!c) throw new Error("Consultation not found");
      return fixtureDraft(c);
    }
    return v1Post<DraftResult>(`/consultations/${consultationId}/summary/draft`, {}, { timeoutMs: 60000 });
  },
  async listPredictions(clientId: string): Promise<PredictionV1[]> {
    if (isFixtures()) return fx().predictions.filter((p) => p.client_id === clientId).sort((a, b) => b.created_at.localeCompare(a.created_at));
    return v1Get<PredictionV1[]>(`/clients/${clientId}/predictions`, 8000);
  },
  async updatePrediction(id: string, patch: { status?: PredictionStatus; outcome_note?: string | null }): Promise<PredictionV1> {
    if (isFixtures()) {
      const p = fx().predictions.find((x) => x.id === id);
      if (!p) throw new Error("Prediction not found");
      if (patch.status !== undefined && patch.status !== p.status) {
        p.status = patch.status;
        p.resolved_at = patch.status === "pending" ? null : FX_NOW;
      }
      if (patch.outcome_note !== undefined) p.outcome_note = patch.outcome_note || null;
      return { ...p };
    }
    return v1Patch<PredictionV1>(`/predictions/${id}`, patch);
  },
  async listLifeEvents(clientId: string): Promise<LifeEventV1[]> {
    if (isFixtures()) return fx().life.filter((l) => l.client_id === clientId);
    return v1Get<LifeEventV1[]>(`/clients/${clientId}/life-events`, 8000);
  },
  async createLifeEvent(clientId: string, body: { event_date: string; kind: LifeKind; title: string; notes?: string | null }): Promise<LifeEventV1> {
    if (isFixtures()) {
      const e: LifeEventV1 = { id: fid("life"), client_id: clientId, event_date: body.event_date, kind: body.kind, title: body.title, notes: body.notes ?? null };
      fx().life.unshift(e);
      return e;
    }
    return v1Post<LifeEventV1>(`/clients/${clientId}/life-events`, body);
  },
  async deleteLifeEvent(id: string): Promise<void> {
    if (isFixtures()) {
      fx().life = fx().life.filter((l) => l.id !== id);
      return;
    }
    await v1Request<void>("DELETE", `/life-events/${id}`);
  },
  async getTimeline(clientId: string): Promise<TimelineEventV1[]> {
    if (isFixtures()) return fixtureTimeline(clientId);
    return v1Get<TimelineEventV1[]>(`/clients/${clientId}/timeline`, 15000);
  },
};

const WRITES = ["createConsultation", "addNote", "saveSummary", "updatePrediction", "createLifeEvent", "deleteLifeEvent"] as const;
export const consultApi = Object.fromEntries(
  Object.entries(api).map(([k, fn]) => [k, (WRITES as readonly string[]).includes(k) ? async (...a: unknown[]) => { const r = await (fn as (...x: unknown[]) => unknown)(...a); announce(); return r; } : fn]),
) as typeof api;

/** Reset the in-memory fixture store (tests). */
export function resetConsultFixtures() {
  store = null;
}
