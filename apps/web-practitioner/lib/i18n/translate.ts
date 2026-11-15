import { HI } from "./hi";

export type Lang = "en" | "hi";
export const LANGUAGES: ReadonlyArray<{ code: Lang; label: string }> = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
];

export function isLang(v: unknown): v is Lang {
  return v === "en" || v === "hi";
}

/**
 * Lightweight dictionary translation: the English text is the key. A missing
 * Hindi entry falls back to the English text, so partially translated screens
 * never show a blank. `{name}` placeholders are filled from `params`.
 */
export function translate(lang: Lang, text: string, params?: Record<string, string | number>): string {
  const base = lang === "hi" ? (HI[text] ?? text) : text;
  if (!params) return base;
  return base.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m));
}

/** Storage key of the language preference; one per signed-in user, one for anonymous use. */
export function storageKey(userId: string | null | undefined): string {
  return `ankana.lang.${userId ?? "anon"}`;
}

export function readStoredLang(userId: string | null | undefined): Lang {
  try {
    const v = window.localStorage.getItem(storageKey(userId));
    return isLang(v) ? v : "en";
  } catch {
    return "en";
  }
}

export function writeStoredLang(userId: string | null | undefined, lang: Lang): void {
  try {
    window.localStorage.setItem(storageKey(userId), lang);
  } catch {
    /* private mode: the preference just lasts for the session */
  }
}

/**
 * Translate a data label that may carry a trailing number or pada, such as
 * "Uttara Bhadrapada 3" or "Magha, pada 2": the name part is looked up, the rest kept.
 */
export function tName(t: (s: string) => string, text: string): string {
  const direct = t(text);
  if (direct !== text) return direct;
  const m = /^(.*?)((?:,?\s+(?:pada\s+)?\d+)|(?:,\s+\w+))?$/.exec(text);
  if (!m || !m[1]) return text;
  const tail = (m[2] ?? "").replace(/pada/, t("pada"));
  return t(m[1]) + tail;
}
