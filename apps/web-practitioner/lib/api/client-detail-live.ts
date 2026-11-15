import { buildHeader, cap, currentDasha, dayMonthYear, fmtDeg } from "./chart-views";
import { absoluteDownloadUrl } from "./live";
import { rowFromV1 } from "./client";
import { reportViews } from "./live-views";
import { v1Api } from "./live";
import type { ChartBundle, ClientDetail } from "./types";

const DAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function when(iso: string) {
  const d = new Date(iso);
  return `${DAY[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

/** Everything the Client screen needs, from /v1 only. Sections stay empty when there is no history. */
export async function liveClientDetail(id: string): Promise<ClientDetail> {
  const [client, charts, consultations, plans, tags, reports] = await Promise.all([
    v1Api.getClient(id),
    v1Api.listCharts(id).catch(() => []),
    v1Api.listConsultations(id).catch(() => []),
    v1Api.listRemedyPlans(id).catch(() => []),
    v1Api.getClientTags(id).catch(() => [] as string[]),
    v1Api.listClientReports(id).catch(() => []),
  ]);
  const chart = charts[0] ?? null;
  const row = { ...rowFromV1(client), chartId: chart?.id ?? null, tags };

  let bornLine = "";
  let facts: ClientDetail["facts"] = [];
  const chartCards: ClientDetail["charts"] = [];
  if (chart) {
    const detail = await v1Api.getChartDetail(chart.id).catch(() => null);
    if (detail) {
      const bundle = {
        chartId: chart.id,
        client: { id, name: client.display_name, initials: row.initials },
        artifact: detail.artifact,
      } as unknown as ChartBundle;
      const h = buildHeader(bundle);
      const a = detail.artifact;
      const moon = a.planets.find((p) => p.planet === "moon");
      const { maha, antar } = currentDasha(a);
      bornLine = `Born ${h.birthLine}  ·  ${h.lagna}`;
      row.lagna = `${a.ascendant.signName} ${fmtDeg(a.ascendant.degreesInSign, a.ascendant.signIndex, false)}`;
      row.dasha = maha ? `${cap(maha.planet)}${antar ? ` / ${cap(antar.planet)}` : ""}` : "";
      facts = [
        { label: "Lagna", value: row.lagna, note: `${a.ascendant.nakshatra} pada ${a.ascendant.pada}` },
        { label: "Running period", value: row.dasha || "Not available", note: antar ? `Until ${dayMonthYear(new Date(antar.end))}` : "" },
        ...(moon ? [{ label: "Moon", value: `${moon.signName} ${fmtDeg(moon.degreesInSign, moon.signIndex, false)}, house ${moon.house}`, note: `${moon.nakshatra} pada ${moon.pada}` }] : []),
      ];
    }
    for (const c of charts) {
      chartCards.push({
        id: c.id,
        kind: "d1",
        title: "Birth chart, D1",
        sub: `${(c.settings.ayanamsa ?? "lahiri").replace(/^./, (x) => x.toUpperCase())} · ${cap(String(c.settings.chart_style ?? "north"))} style · ${when(c.created_at)}`,
      });
    }
  }

  return {
    row,
    chartId: chart?.id ?? null,
    bornLine,
    consultToday: null,
    timeConfirmed: null,
    charts: chartCards,
    consultations: consultations.map((c) => ({ when: when(c.scheduled_at ?? c.consulted_at), title: c.topic || "Consultation", note: c.mode ? `Mode: ${c.mode}` : "" })),
    remedies: plans
      .filter((p) => p.status === "active" || p.status === "draft")
      .map((p) => ({
        title: p.title,
        day: p.day_number ?? 0,
        total: p.cycle_days,
        note: p.status === "draft" ? "Draft, not started" : p.end_date ? `Ends ${when(p.end_date)}` : "",
      })),
    reports: reportViews(reports, absoluteDownloadUrl),
    facts,
  };
}
