import { planetsIn } from "./chart";
import {
  masnuiData,
  planetHouseEntries,
  remedyDelivery,
  type Clause,
  type PlanetHouseEntry,
} from "./data";
import { detectMasnui } from "./masnui";
import { detectRin } from "./rin";
import { sleepingPlanets } from "./sleeping";
import type { Cite, LkChart, Planet } from "./types";

export type UpayKind = "rin" | "rin_polluter" | "sleeping_planet" | "house_entry" | "masnui";

export interface Upay {
  rank: number;
  kind: UpayKind;
  planet: Planet;
  house: number;
  title: string;
  action: string;
  why: string;
  /** How to hand over the planet's articles, by the house the planet sits in (p.171). */
  delivery: { house: number; method: string | null; cite: Cite } | null;
  /** Suggested observation window per the one-at-a-time rule (days). */
  durationDays: number;
  cites: Cite[];
  needs_review: boolean;
}

export interface UpayPlan {
  /** Ranked list; follow strictly one at a time. */
  upay: Upay[];
  oneAtATime: {
    rule: string;
    durationDays: number[];
    gap: string;
    cite: Cite;
  };
  /** Sequenced phases: exactly one upay per phase. */
  schedule: Array<{ phase: number; upayRank: number; days: number; thenPause: string }>;
  coverage: {
    planetHouseEntriesDone: number;
    planetHouseEntriesTotal: number;
  };
}

export function clauseHolds(chart: LkChart, clause: Clause, entryPlanet: Planet): boolean {
  if ("in" in clause) {
    return clause.in.planets.some((p) => {
      const h = chart.planetHouse[p];
      return h !== undefined && clause.in.houses.includes(h);
    });
  }
  if ("together" in clause) {
    const [a, b] = clause.together;
    const ha = chart.planetHouse[a];
    return ha !== undefined && ha === chart.planetHouse[b];
  }
  if ("empty" in clause) {
    return clause.empty.every((h) => planetsIn(chart, h).length === 0);
  }
  const h = chart.planetHouse[entryPlanet];
  return h !== undefined && planetsIn(chart, h).length === 1;
}

export interface EntryMatch {
  entry: PlanetHouseEntry;
  matched: Array<{ effect: string; tone: string; needs_review: boolean }>;
}

/** Planet-in-house entries (Vol II) that apply to the chart, with the conditions that hold. */
export function matchPlanetHouseEntries(chart: LkChart): EntryMatch[] {
  const out: EntryMatch[] = [];
  for (const entry of planetHouseEntries) {
    if (entry.status !== "done") continue;
    if (chart.planetHouse[entry.planet] !== entry.house) continue;
    const matched = entry.conditions
      .filter((c) => c.when && c.when.length > 0 && c.when.every((cl) => clauseHolds(chart, cl, entry.planet)))
      .map((c) => ({ effect: c.effect, tone: c.tone, needs_review: c.needs_review }));
    out.push({ entry, matched });
  }
  return out;
}

function deliveryFor(planet: Planet, chart: LkChart): Upay["delivery"] {
  const house = chart.planetHouse[planet];
  if (!house) return null;
  const row = remedyDelivery.rows.find((r) => r.house === house);
  return row ? { house, method: row.method, cite: row.cite } : null;
}

type Draft = Omit<Upay, "rank">;

/**
 * Ranked upay (remedies) for the chart. Order: debts first (family-wide, book
 * treats them as root causes), then dormant planets, then Vol II planet-in-house
 * remedies for malefic matches, then artificial-planet advice. All must be run
 * one at a time (p.133).
 */
export function remedies(chart: LkChart): UpayPlan {
  const rule = remedyDelivery.one_at_a_time;
  const days = rule.duration_days[1];
  const drafts: Draft[] = [];
  const seen = new Set<string>();
  const push = (key: string, d: Draft) => {
    if (seen.has(key)) return;
    seen.add(key);
    drafts.push(d);
  };

  // 1. debts
  for (const f of detectRin(chart)) {
    if (f.basis === "indicator") continue;
    push(`rin:${f.id}`, {
      kind: "rin",
      planet: f.planet,
      house: f.house,
      title: `${f.kind}: ${f.planet} in house ${f.house}`,
      action: f.remedy,
      why: `${f.planet} sits in house ${f.house} with ${f.with.join(", ")}, which the book lists as the pattern for this debt.`,
      delivery: null,
      durationDays: days,
      cites: [f.cite, f.remedy_cite],
      needs_review: f.needs_review,
    });
    // The book asks for a second remedy for the planet that spoils the first (p.133).
    for (const polluter of f.with) {
      const d = deliveryFor(polluter, chart);
      push(`rin_polluter:${f.id}:${polluter}`, {
        kind: "rin_polluter",
        planet: polluter,
        house: f.house,
        title: `Repair ${polluter} (spoils ${f.planet} in house ${f.house})`,
        action: `Do a separate remedy for ${polluter} after the debt remedy is finished. ${d?.method ?? ""}`.trim(),
        why: "The book asks for two remedies in a debt: the damaged planet and the planet that damages it, run one after the other.",
        delivery: d,
        durationDays: days,
        cites: [f.cite, rule.cite],
        needs_review: true,
      });
    }
  }

  // 2. dormant planets
  for (const s of sleepingPlanets(chart)) {
    if (s.status !== "dormant") continue;
    const d = deliveryFor(s.awakener, chart);
    push(`sleep:${s.planet}`, {
      kind: "sleeping_planet",
      planet: s.planet,
      house: s.house,
      title: `Awaken ${s.planet} in house ${s.house} (via ${s.awakener})`,
      action: s.awakenerPresent
        ? `Strengthen ${s.awakener}, the awakener of house ${s.house}. ${d?.method ?? ""}`.trim()
        : `${s.awakener} is absent from the chart; identify a remedy that awakens house ${s.house} through ${s.awakener}'s articles.`,
      why: `${s.planet} is dormant by rule "${s.rule}". It may also awaken by itself around age ${s.selfAwakeningAge}.`,
      delivery: d,
      durationDays: days,
      cites: [s.cite],
      needs_review: s.needs_review,
    });
  }

  // 3. planet-in-house remedies where a malefic condition holds
  for (const m of matchPlanetHouseEntries(chart)) {
    const malefic = m.matched.filter((x) => x.tone === "malefic");
    if (malefic.length === 0 || m.entry.remedies.length === 0) continue;
    for (const [i, r] of m.entry.remedies.entries()) {
      push(`entry:${m.entry.id}:${i}`, {
        kind: "house_entry",
        planet: m.entry.planet,
        house: m.entry.house,
        title: `${m.entry.planet} in house ${m.entry.house}`,
        action: r.text,
        why: malefic.map((x) => x.effect).join(" "),
        delivery: deliveryFor(m.entry.planet, chart),
        durationDays: days,
        cites: [m.entry.cite],
        needs_review: true,
      });
    }
  }

  // 4. artificial planets
  for (const a of detectMasnui(chart)) {
    push(`masnui:${a.id}`, {
      kind: "masnui",
      planet: a.formedPlanet,
      house: a.house,
      title: `Artificial ${a.formedPlanet}${a.variant ? ` (${a.variant})` : ""} from ${a.components.join(" + ")} in house ${a.house}`,
      action: masnuiData.remedy_principle.text,
      why: `${a.components.join(" and ")} share house ${a.house}, forming an artificial ${a.formedPlanet}.`,
      delivery: deliveryFor(a.components[0], chart),
      durationDays: days,
      cites: [a.cite, masnuiData.remedy_principle.cite],
      needs_review: true,
    });
  }

  const upay = drafts.map((d, i) => ({ rank: i + 1, ...d }));
  return {
    upay,
    oneAtATime: {
      rule: rule.rule,
      durationDays: rule.duration_days,
      gap: rule.gap,
      cite: rule.cite,
    },
    schedule: upay.map((u, i) => ({
      phase: i + 1,
      upayRank: u.rank,
      days,
      thenPause: rule.gap,
    })),
    coverage: {
      planetHouseEntriesDone: planetHouseEntries.filter((e) => e.status === "done").length,
      planetHouseEntriesTotal: planetHouseEntries.length,
    },
  };
}
