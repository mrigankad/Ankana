import type { LocationSearchResult } from "@astro/shared-types";

import type { LagnaPreview } from "./types";

function apiBase() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3001";
}

export const varanasiSample: LocationSearchResult = {
  providerPlaceId: "geo_varanasi_in",
  displayName: "Varanasi, Uttar Pradesh, India",
  latitude: 25.3176,
  longitude: 82.9739,
  timezoneName: "Asia/Kolkata",
  confidence: "high",
  countryCode: "IN",
};

export const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export type TimeSource = "certificate" | "memory" | "approximate" | "unknown";
export const TIME_SOURCES: Array<{ id: TimeSource; label: string }> = [
  { id: "certificate", label: "Birth certificate" },
  { id: "memory", label: "Family memory" },
  { id: "approximate", label: "Approximate" },
  { id: "unknown", label: "Unknown, rectify later" },
];

/** Valid calendar date from typed parts, or null. */
export function parseDate(dd: string, mm: string, yyyy: string): Date | null {
  if (!/^\d{1,2}$/.test(dd) || !/^\d{1,2}$/.test(mm) || !/^\d{4}$/.test(yyyy)) return null;
  const d = Number(dd);
  const m = Number(mm);
  const y = Number(yyyy);
  if (y < 1800 || y > 2200) return null;
  const date = new Date(Date.UTC(y, m - 1, d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) return null;
  return date;
}

export function weekdayOf(date: Date) {
  return WEEKDAYS[date.getUTCDay()]!;
}

export function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

/** 12 hour typed time to 24 hour parts, or null when invalid. */
export function to24h(hh: string, mi: string, pm: boolean): { h: number; m: number } | null {
  if (!/^\d{1,2}$/.test(hh) || !/^\d{1,2}$/.test(mi)) return null;
  const h12 = Number(hh);
  const m = Number(mi);
  if (h12 < 1 || h12 > 12 || m > 59) return null;
  return { h: (h12 % 12) + (pm ? 12 : 0), m };
}

export const two = (n: number) => String(n).padStart(2, "0");

export function hhmm(t: { h: number; m: number }) {
  return `${two(t.h)}:${two(t.m)}`;
}

/** Shift a 24h time by minutes, wrapping around midnight. */
export function shiftTime(t: { h: number; m: number }, minutes: number) {
  const total = (((t.h * 60 + t.m + minutes) % 1440) + 1440) % 1440;
  return { h: Math.floor(total / 60), m: total % 60 };
}

function offsetMinutes(zone: string, at: Date): number | null {
  try {
    const part = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "longOffset" })
      .formatToParts(at)
      .find((p) => p.type === "timeZoneName")?.value;
    if (!part) return null;
    if (part === "GMT") return 0;
    const m = /GMT([+-])(\d{2}):?(\d{2})?/.exec(part);
    if (!m) return null;
    const mins = Number(m[2]) * 60 + Number(m[3] ?? 0);
    return m[1] === "-" ? -mins : mins;
  } catch {
    return null;
  }
}

export function formatOffset(mins: number) {
  const sign = mins < 0 ? "-" : "+";
  const a = Math.abs(mins);
  return `${sign}${two(Math.floor(a / 60))}:${two(a % 60)}`;
}

export interface ZoneInfo {
  offsetLabel: string;
  /** "None. +05:30 applied" or "Yes. +01:00 applied" */
  dst: string;
  isDst: boolean;
}

/** UTC offset at the birth moment and whether daylight saving was in force, from the IANA tz database. */
export function zoneInfo(zone: string, date: Date): ZoneInfo | null {
  const noon = new Date(date.getTime() + 12 * 3_600_000);
  const at = offsetMinutes(zone, noon);
  if (at === null) return null;
  const y = date.getUTCFullYear();
  const jan = offsetMinutes(zone, new Date(Date.UTC(y, 0, 1, 12)));
  const jul = offsetMinutes(zone, new Date(Date.UTC(y, 6, 1, 12)));
  const standard = Math.min(jan ?? at, jul ?? at);
  const isDst = at > standard;
  const label = formatOffset(at);
  return { offsetLabel: `UTC${label}`, isDst, dst: `${isDst ? "Yes" : "None"}. ${label} applied` };
}

export function formatCoords(lat: number, lon: number) {
  return `${Math.abs(lat).toFixed(4)} ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(4)} ${lon >= 0 ? "E" : "W"}`;
}

/** Everything the preview panel draws that the lagna preview endpoint will eventually return. */
export interface LagnaPreviewView extends LagnaPreview {
  /** House number (1..12) to planet abbreviations. */
  houses: Record<number, string[]>;
  /** Sign number (1 Aries .. 12 Pisces) of the lagna. */
  lagnaSign: number;
  /** Minutes either side of the recorded time inside which the navamsa lagna holds. */
  windowMinutes: number;
}

export const previewExtras: Pick<LagnaPreviewView, "houses" | "lagnaSign" | "windowMinutes"> = {
  houses: { 1: ["Su"], 2: ["Ke"], 5: ["Ma"], 6: ["Mo"], 8: ["Ra"], 9: ["Ju"], 11: ["Ve"], 12: ["Me", "Sa"] },
  lagnaSign: 12,
  windowMinutes: 14,
};

export function toPreviewView(p: LagnaPreview): LagnaPreviewView {
  const m = /±\s*(\d+)\s*min/.exec(p.navamsaNote);
  return { ...previewExtras, ...p, windowMinutes: m ? Number(m[1]) : previewExtras.windowMinutes };
}

export interface IntakeSubmit {
  clientName: string;
  existingClientId?: string | null;
  birthDate: string;
  /** 24h HH:MM, or "" when the time is unknown. */
  birthTime: string;
  timeSource: TimeSource;
  placeText: string;
  location: LocationSearchResult;
  style: "north" | "south";
  /** Consent captured inline in the intake, with the verbatim notice shown. */
  consent?: { noticeVersion: string; noticeText: string; channel: string } | null;
}

/** Build the preview view model from the /v1/charts/preview response. */
export function viewFromPreview(p: import("./live").LagnaPreviewV1, recorded: { h: number; m: number } | null): LagnaPreviewView {
  const s = p.sensitivity;
  const deg = Math.floor(p.lagna.degrees_in_sign);
  const min = Math.round((p.lagna.degrees_in_sign - deg) * 60);
  const d9Narrow = s.window_minutes < s.d1_minutes_before && s.window_minutes < s.d1_minutes_after;
  const safe = d9Narrow
    ? `${p.lagna.sign} holds from ${s.d1_holds_from} to ${s.d1_holds_until}, so the main chart is safe. The D9 lagna turns at ${s.d9_holds_until}, so rectify before reading marriage or the finer dasha timing.`
    : `${p.lagna.sign} holds from ${s.d1_holds_from} to ${s.d1_holds_until}. The D9 lagna holds the same window, so the chart is stable for this time.`;
  void recorded;
  return {
    lagna: `${p.lagna.sign} lagna ${deg}°${String(min).padStart(2, "0")}′`,
    moon: `Moon in ${p.moon.nakshatra} pada ${p.moon.pada}, ${p.moon.sign}`,
    navamsaNote: `Navamsa lagna changes within ±${s.window_minutes} min`,
    safeNote: safe,
    houses: Object.fromEntries(Object.entries(p.houses).map(([k, v]) => [Number(k), v])),
    lagnaSign: p.lagna.sign_index + 1,
    windowMinutes: Math.max(s.window_minutes, 1),
  };
}

export async function searchLocationsLive(q: string): Promise<LocationSearchResult[]> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 2500);
  try {
    const res = await fetch(`${apiBase()}/api/v1/locations/search?q=${encodeURIComponent(q)}`, { signal: ctrl.signal });
    const payload = (await res.json()) as { results?: LocationSearchResult[] };
    return payload.results ?? [];
  } finally {
    clearTimeout(timer);
  }
}

export function searchLocationsFallback(q: string): LocationSearchResult[] {
  return /varanasi|banaras|benares/i.test(q) ? [varanasiSample] : [];
}
