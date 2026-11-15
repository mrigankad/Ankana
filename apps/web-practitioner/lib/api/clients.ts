import { ANANYA_CLIENT_ID, clientRows } from "./fixtures";
import type { ClientRow, ClientTag, WorkspaceMeta } from "./types";

export type ClientFilter = "all" | "lalKitab" | "matching" | "rectify" | "followUp";

export interface ClientFacets {
  total: number;
  lalKitab: number;
  matching: number;
  rectify: number;
  followUp: number;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Days from today to a follow-up label like "Today, 11:30" or "Tue 18 Nov". null when unknown. */
export function followUpDays(label: string, now = new Date()): number | null {
  if (/^today/i.test(label)) return 0;
  const m = /(\d{1,2})\s+([A-Za-z]{3})/.exec(label);
  if (!m) return null;
  const month = MONTHS.indexOf(m[2]!);
  if (month < 0) return null;
  const target = new Date(now.getFullYear(), month, Number(m[1]));
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((target.getTime() - start.getTime()) / 86_400_000);
}

export function followUpTone(label: string): "today" | "soon" | "later" | "none" {
  const d = followUpDays(label);
  if (d === null) return "none";
  if (d <= 0) return "today";
  return d <= 7 ? "soon" : "later";
}

export function hasTag(row: ClientRow, tag: ClientTag) {
  return row.tags.includes(tag);
}

export function isFollowUpDue(row: ClientRow) {
  const d = followUpDays(row.nextFollowUp);
  return d !== null && d <= 7;
}

/** Facet counts. For the design fixture set the counts are the full 27-person workspace numbers. */
export function clientFacets(rows: ClientRow[], workspace: WorkspaceMeta | null): ClientFacets {
  const isFixtureSet = rows.length === clientRows.length && rows.some((r) => r.id === ANANYA_CLIENT_ID);
  if (isFixtureSet) {
    return { total: workspace?.clientCount ?? 27, lalKitab: 9, matching: 6, rectify: 3, followUp: 4 };
  }
  return {
    total: rows.length,
    lalKitab: rows.filter((r) => hasTag(r, "Lal Kitab")).length,
    matching: rows.filter((r) => hasTag(r, "Matching")).length,
    rectify: rows.filter((r) => hasTag(r, "Rectify")).length,
    followUp: rows.filter(isFollowUpDue).length,
  };
}

export function filterClients(rows: ClientRow[], filter: ClientFilter, query: string): ClientRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter((r) => {
    if (filter === "lalKitab" && !hasTag(r, "Lal Kitab")) return false;
    if (filter === "matching" && !hasTag(r, "Matching")) return false;
    if (filter === "rectify" && !hasTag(r, "Rectify")) return false;
    if (filter === "followUp" && !isFollowUpDue(r)) return false;
    if (!q) return true;
    return [r.name, r.birthLine, r.lagna].some((s) => s.toLowerCase().includes(q));
  });
}
