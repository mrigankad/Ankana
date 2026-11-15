import type { VedicChartArtifact } from "@astro/astrology-core";

import {
  ANANYA_CHART_ID,
  ANANYA_CLIENT_ID,
  ananyaBundle,
  clientRows,
  lagnaPreviewFixture,
  todayFixture,
  workspaceFixture,
} from "./fixtures";
import { clientDetailFixture, detailFromRow } from "./client-detail";
import { searchLocationsFallback, searchLocationsLive, toPreviewView, viewFromPreview } from "./intake";
import { camelizeKeys, v1Api, type ClientV1, type TodayV1 } from "./live";
import { clientRowFromV1, todayViewFromV1, workspaceFromLive } from "./live-views";
import { v1Get } from "./v1";
import type { AnkanaApi, ChartBundle, ClientRow } from "./types";

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3001";
}

/** "live" never falls back, "fixtures" never hits the network, "auto" tries live then falls back. */
type Mode = "live" | "fixtures" | "auto";
export function mode(): Mode {
  const m = process.env.NEXT_PUBLIC_ANKANA_DATA;
  return m === "live" || m === "fixtures" ? m : "auto";
}

export async function getJson<T>(path: string, timeoutMs = 2500): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${getApiBaseUrl()}${path}`, { signal: ctrl.signal });
    if (!res.ok) throw new Error(`${path} ${res.status}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

/** Run `live` per the data mode; use `fixture` when live is unavailable. */
export async function withFixture<T>(
  live: () => Promise<T>,
  fixture: () => T | Promise<T>,
): Promise<T> {
  const m = mode();
  if (m === "fixtures") return fixture();
  if (m === "live") return live();
  try {
    return await live();
  } catch {
    return fixture();
  }
}

/** True when screens must not call the network at all (design demos). */
export const isFixtures = () => mode() === "fixtures";
/** True when fixture data must never appear (no prefill, no fallbacks). */
export const isLive = () => mode() === "live";

function initialsOf(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function shortDate(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function rowFromV1(c: ClientV1, extra: Partial<ClientRow> = {}): ClientRow {
  return {
    id: c.id,
    chartId: null,
    initials: initialsOf(c.display_name),
    name: c.display_name,
    birthLine: c.contact_email || c.contact_phone || "No contact details",
    lagna: "",
    dasha: "",
    lastConsult: `Added ${shortDate(c.created_at)}`,
    nextFollowUp: "",
    tags: [],
    ...extra,
  };
}

async function liveBundle(chartId: string): Promise<ChartBundle> {
  const detail = await v1Api.getChartDetail(chartId);
  const [client, lalKitab] = await Promise.all([
    v1Api.getClient(detail.chart.client_id),
    v1Api.getLalKitab(chartId).catch(() => ananyaBundle.lalKitab),
  ]);
  const input = detail.artifact.calculationMetadata.input;
  return {
    chartId,
    client: { id: client.id, name: client.display_name, initials: initialsOf(client.display_name) },
    artifact: detail.artifact,
    lalKitab,
    birthLine: [input.birthDate, input.birthTime, input.placeLabel].filter(Boolean).join(", "),
    asked: { question: "", answer: [], citations: [], checks: { engine: "", verifier: "" }, suggestions: [] },
    reading: detail.reading,
  };
}

/** The sidebar and the Today screen both read GET /v1/today; share one request for 20 seconds. */
let todayCache: { at: number; p: Promise<TodayV1> } | null = null;
export function sharedToday(): Promise<TodayV1> {
  if (!todayCache || Date.now() - todayCache.at > 20_000) {
    const p = v1Api.getToday();
    todayCache = { at: Date.now(), p };
    p.catch(() => {
      if (todayCache?.p === p) todayCache = null;
    });
  }
  return todayCache.p;
}

export const api: AnkanaApi = {
  getWorkspace: () =>
    withFixture(
      async () => {
        const [me, usage, today] = await Promise.all([
          v1Get<{ memberships: Array<{ practice_name: string }> }>("/me", 8000),
          v1Api.getUsage().catch(() => null),
          sharedToday().catch(() => null),
        ]);
        const practice = me.memberships[0]?.practice_name ?? "Your practice";
        return workspaceFromLive({ usage, today, practiceName: practice });
      },
      () => workspaceFixture,
    ),
  getToday: () =>
    withFixture(
      async () => {
        const [today, me] = await Promise.all([sharedToday(), v1Get<{ memberships: Array<{ practice_name: string }> }>("/me", 8000).catch(() => null)]);
        return todayViewFromV1(today, me?.memberships[0]?.practice_name ?? "");
      },
      () => todayFixture,
    ),
  listClients: () =>
    withFixture(
      async () => (await v1Api.listClients({ limit: 200 })).clients.map((c) => clientRowFromV1(c)),
      () => clientRows,
    ),
  getClient: (id) =>
    withFixture(
      async () => {
        const row = rowFromV1(await v1Api.getClient(id));
        const charts = await v1Api.listCharts(id).catch(() => []);
        const chartId = charts[0]?.id ?? null;
        return { row: { ...row, chartId }, chartId };
      },
      () => {
        const row = clientRows.find((c) => c.id === id) ?? clientRows[0]!;
        return { row, chartId: row.chartId };
      },
    ),
  getChart: (chartId): Promise<ChartBundle> =>
    withFixture(
      () => liveBundle(chartId),
      () => ({ ...ananyaBundle, chartId: chartId || ANANYA_CHART_ID }),
    ),
  previewLagna: async (input) => {
    if (isFixtures()) return toPreviewView(lagnaPreviewFixture);
    const t = /^(\d{2}):(\d{2})$/.exec(input.birthTime);
    const p = await v1Api.previewLagna({
      birth_date: input.birthDate,
      birth_time: `${input.birthTime}:00`,
      latitude: input.location.latitude,
      longitude: input.location.longitude,
      timezone_name: input.location.timezoneName,
    });
    return viewFromPreview(p, t ? { h: Number(t[1]), m: Number(t[2]) } : null);
  },
  searchLocations: (q) =>
    withFixture(
      async () => {
        const live = await searchLocationsLive(q);
        return live.length ? live : isLive() ? [] : searchLocationsFallback(q);
      },
      () => searchLocationsFallback(q),
    ),
  submitIntake: async (input) => {
    if (isFixtures()) return { clientId: ANANYA_CLIENT_ID, chartId: ANANYA_CHART_ID };
    const { submitIntakeV1 } = await import("./intake-flow");
    return submitIntakeV1(input);
  },
  getClientDetail: (id) =>
    withFixture(
      async () => {
        const { liveClientDetail } = await import("./client-detail-live");
        return liveClientDetail(id);
      },
      () => clientDetailFixture(id),
    ),
};

export { camelizeKeys };
