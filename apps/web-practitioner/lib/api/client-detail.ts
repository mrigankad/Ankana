import { ANANYA_CHART_ID, ANANYA_CLIENT_ID, clientRows, todayFixture } from "./fixtures";
import type { ClientDetail, ClientRow } from "./types";

const ananyaHouses = todayFixture.consults[0]!.miniHouses ?? {};

export const ananyaDetail: ClientDetail = {
  row: clientRows[0]!,
  chartId: ANANYA_CHART_ID,
  bornLine: "Born Wed 15 Mar 1995, 06:42 AM IST, Varanasi  ·  Pisces lagna 10°32′  ·  Moon in Magha pada 2",
  consultToday: "Consult today, 11:30",
  timeConfirmed: "Birth time confirmed from hospital certificate. Lagna is stable within ±14 min.",
  charts: [
    { id: ANANYA_CHART_ID, kind: "d1", title: "Birth chart, D1", sub: "Lahiri · North style · Lal Kitab on", miniHouses: ananyaHouses },
    { id: "match-rohit-mehta", kind: "match", title: "Matching with Rohit Mehta", sub: "Ashtakoot 27 of 36 · 14 Oct" },
    { id: "varsha-2026", kind: "varsha", title: "Annual chart 2026", sub: "Varshaphala · from 15 Mar" },
  ],
  consultations: [
    {
      when: "Today, 11:30",
      title: "Career question, 2nd visit",
      note: "Chart prepared. Open with the 10th lord Jupiter in the 9th and the Moon / Mars period that runs to Feb 2027. Ask about the Pune offer and the timing of the move.",
    },
    {
      when: "24 Oct",
      title: "Marriage matching, 45 min",
      note: "Compared with Rohit Mehta. Ashtakoot 27 of 36, with Mars debilitated in the 5th noted for both families. Advised a muhurta after Makar Sankranti. Family to confirm.",
    },
    {
      when: "12 Sep",
      title: "First consultation, birth time check",
      note: "Hospital certificate seen and photographed. Lagna stable. Began a 43-day Saturn remedy and a Thursday fast.",
    },
  ],
  remedies: [
    { title: "Saturn: lamp at a peepal, Saturdays", day: 31, total: 43, note: "Mercury and Saturn in the 12th. Ends Tue 25 Nov." },
    { title: "Jupiter: Thursday fast, yellow dal", day: 19, total: 43, note: "Ends Wed 3 Dec." },
    { title: "Moon: water to Shiva, Mondays", day: 41, total: 43, note: "Almost done. Send a closing check-in." },
  ],
  reports: [
    { title: "Career and dasha report, 12 pages", sent: "Sent 24 Oct on WhatsApp", status: "Opened" },
    { title: "Lal Kitab remedies, 4 pages", sent: "Sent 12 Sep by email", status: "Opened" },
  ],
  facts: [
    { label: "Lagna", value: "Pisces 10°32′", note: "Uttara Bhadrapada pada 3" },
    { label: "Running period", value: "Moon / Mars", note: "Until Feb 2027, then Moon / Rahu" },
    { label: "Moon", value: "Leo 4°43′, 6th house", note: "Magha pada 2" },
    { label: "Worth raising", value: "Mars, 5th house", note: "Cancer 19°58′, debilitated, retrograde" },
  ],
};

/** Minimal detail for a client we only know the list row for (fixtures or a live client). */
export function detailFromRow(row: ClientRow): ClientDetail {
  const today = row.nextFollowUp.toLowerCase().startsWith("today");
  return {
    row,
    chartId: row.chartId,
    bornLine: row.lagna && row.lagna !== "Open chart" ? `Born ${row.birthLine}  ·  ${row.lagna} lagna` : row.birthLine ? `Born ${row.birthLine}` : "",
    consultToday: today ? `Consult today, ${row.nextFollowUp.replace(/^today,?\s*/i, "")}`.replace(/,\s*$/, "") : null,
    timeConfirmed: null,
    charts: [],
    consultations: [],
    remedies: [],
    reports: [],
    facts: row.lagna && row.lagna !== "Open chart"
      ? [
          { label: "Lagna", value: row.lagna, note: "" },
          { label: "Running period", value: row.dasha, note: "" },
        ]
      : [],
  };
}

export function clientDetailFixture(id: string): ClientDetail {
  if (id === ANANYA_CLIENT_ID) return ananyaDetail;
  const row = clientRows.find((c) => c.id === id) ?? clientRows[0]!;
  return row.id === ANANYA_CLIENT_ID ? ananyaDetail : detailFromRow(row);
}
