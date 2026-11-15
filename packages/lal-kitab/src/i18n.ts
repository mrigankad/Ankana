import planetHouseHi from "../data/hi/planet_house.hi.json";
import rulesHi from "../data/hi/rules.hi.json";

/**
 * Hindi overlay for the English Lal Kitab paraphrases (mirror of
 * services/api-py/src/ankana_lalkitab/i18n.py). Keyed by the exact English
 * string, so edits to the English never desynchronise it. All Hindi text is a
 * machine-generated first draft flagged `needs_review_hi`.
 */
interface PlanetHouseHiRow {
  needs_review_hi: boolean;
  theme?: string;
  theme_hi?: string;
  conditions: Array<{ effect: string; effect_hi: string }>;
  remedies: Array<{ text: string; text_hi: string }>;
}

function buildMap(): Map<string, string> {
  const map = new Map<string, string>();
  const rows = (planetHouseHi as { rows: Record<string, PlanetHouseHiRow> }).rows;
  for (const row of Object.values(rows)) {
    if (row.theme && row.theme_hi) map.set(row.theme, row.theme_hi);
    for (const c of row.conditions) map.set(c.effect, c.effect_hi);
    for (const r of row.remedies) map.set(r.text, r.text_hi);
  }
  for (const e of (rulesHi as { entries: Array<{ en: string; hi: string }> }).entries) {
    map.set(e.en, e.hi);
  }
  return map;
}

const HI_MAP = buildMap();

export function hindiCoverage() {
  const rows = (planetHouseHi as { rows: Record<string, PlanetHouseHiRow> }).rows;
  return {
    planet_house_rows: Object.keys(rows).length,
    rules_entries: (rulesHi as { entries: unknown[] }).entries.length,
    needs_review_hi: true,
  };
}

/** Replace every known English paraphrase in `value` with Hindi when lang is "hi". */
export function localizeReport<T>(value: T, lang: string | null | undefined): T {
  if (lang !== "hi") return value;
  return walk(value) as T;
}

function walk(v: unknown): unknown {
  if (typeof v === "string") return HI_MAP.get(v) ?? v;
  if (Array.isArray(v)) return v.map(walk);
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.entries(v as object).map(([k, x]) => [k, walk(x)]));
  }
  return v;
}
