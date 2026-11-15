import {
  isRetrograde,
  meanLunarNode,
  normalizeDegrees,
  SIGN_NAMES,
  toSidereal,
  tropicalLongitude,
  type EphemerisBody,
  type VedicChartArtifact,
} from "@astro/astrology-core";

import type {
  DoubleTransitV1,
  GocharaPlanetV1,
  GocharaV1,
  SadeSatiLifetimeV1,
  SadeSatiPeriodV1,
  TransitDepthSource,
} from "./transit-depth";

/**
 * Offline twin of services/api-py/src/nakshatra_core/transit_depth.py: same rules, same output
 * shapes, so fixture mode renders the real screens. Keep the two in step.
 */

const DAY = 86_400_000;
const YEAR = 365.2425 * DAY;
const BODIES = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"] as const;

const FAVOURABLE: Record<string, [number[], number[]]> = {
  sun: [[3, 6, 10, 11], [9, 12, 4, 5]],
  moon: [[1, 3, 6, 7, 10, 11], [5, 9, 12, 2, 4, 8]],
  mars: [[3, 6, 11], [12, 9, 5]],
  mercury: [[2, 4, 6, 8, 10, 11], [5, 3, 9, 1, 8, 12]],
  jupiter: [[2, 5, 7, 9, 11], [12, 4, 3, 10, 8]],
  venus: [[1, 2, 3, 4, 5, 8, 9, 11, 12], [8, 7, 1, 10, 9, 5, 11, 6, 3]],
  saturn: [[3, 6, 11], [12, 9, 5]],
};
const EXEMPT = [["sun", "saturn"], ["moon", "mercury"]];
const SPECIAL: Record<string, number[]> = { mars: [4, 8], jupiter: [5, 9], saturn: [3, 10] };

const PROOF_SADE_SATI =
  "Saturn in the 12th, 1st and 2nd sign from the natal Moon is Sade Sati; in the 4th (kantaka) or 8th (ashtama) it is dhaiya. Parashari gochara from the Moon (Phaladeepika ch. 26, BPHS gochara adhyaya). Dates are Saturn's sign ingresses, sidereal Lahiri, mean node not involved.";
const PROOF_GOCHARA =
  "Favourable houses from the natal Moon with their vedha points (Phaladeepika ch. 26, BPHS gochara adhyaya); a favourable house is obstructed when another graha stands in its vedha house (Sun and Saturn, Moon and Mercury do not obstruct each other). Bindus are the planet's bhinna ashtakavarga count in the sign it occupies (BPHS ashtakavarga adhyaya): 4 or more carries the result, 5 or more softens an unfavourable house.";
const PROOF_DOUBLE =
  "Jupiter and Saturn both occupying or casting graha drishti on a house (Jupiter 5, 7, 9; Saturn 3, 7, 10 signs counted inclusively) mark a house as active for events: K. N. Rao's double transit, built on Parashari drishti (BPHS ch. 26).";

const count = (from: number, to: number) => ((((to - from) % 12) + 12) % 12) + 1;
const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");

function longitude(body: string, at: number): number {
  const date = new Date(at);
  if (body === "rahu" || body === "ketu") {
    const rahu = toSidereal(meanLunarNode(date), date);
    return body === "rahu" ? rahu : normalizeDegrees(rahu + 180);
  }
  return toSidereal(tropicalLongitude(body as EphemerisBody, date), date);
}
const signAt = (body: string, at: number) => Math.floor(longitude(body, at) / 30) % 12;

interface Segment {
  sign: number;
  start: number;
  end: number;
}

function signSegments(body: string, start: number, end: number, stepDays = 3): Segment[] {
  const out: Segment[] = [];
  let sign = signAt(body, start);
  let segStart = start;
  for (let cursor = start; cursor < end; ) {
    const step = Math.min(cursor + stepDays * DAY, end);
    const next = signAt(body, step);
    if (next !== sign) {
      let lo = cursor;
      let hi = step;
      while (hi - lo > 300_000) {
        const mid = (lo + hi) / 2;
        if (signAt(body, mid) !== sign) hi = mid;
        else lo = mid;
      }
      out.push({ sign, start: segStart, end: hi });
      segStart = hi;
      sign = next;
    }
    cursor = step;
  }
  out.push({ sign, start: segStart, end });
  return out;
}

function runs(segments: Segment[], moon: number, houses: number[], mergeGapDays = 400): Segment[][] {
  const out: Segment[][] = [];
  for (const seg of segments) {
    if (!houses.includes(count(moon, seg.sign))) continue;
    const last = out[out.length - 1];
    if (last && (seg.start - last[last.length - 1].end) / DAY < mergeGapDays) last.push(seg);
    else out.push([seg]);
  }
  return out;
}

const PHASE: Record<number, "rising" | "peak" | "setting"> = { 12: "rising", 1: "peak", 2: "setting" };
const DHAIYA: Record<number, "dhaiya_kantaka" | "dhaiya_ashtama"> = { 4: "dhaiya_kantaka", 8: "dhaiya_ashtama" };

function natalSigns(natal: VedicChartArtifact) {
  const lagna = natal.ascendant.signIndex;
  const moon = natal.planets.find((p) => p.planet === "moon")!.signIndex;
  return { lagna, moon };
}

export function fixtureSadeSati(natal: VedicChartArtifact, asOf: number): SadeSatiLifetimeV1 {
  const { moon } = natalSigns(natal);
  const birth = Date.parse(natal.calculationMetadata.utcDateTime);
  const scanStart = birth - 9 * YEAR;
  const scanEnd = Math.max(birth + 100 * YEAR, asOf + 35 * YEAR) + 9 * YEAR;
  const segments = signSegments("saturn", scanStart, scanEnd);
  const age = (ms: number) => Math.round(Math.max(0, (ms - birth) / YEAR) * 10) / 10;

  type Raw = { kind: SadeSatiPeriodV1["kind"]; start: number; end: number; phases: SadeSatiPeriodV1["phases"] };
  const raw: Raw[] = [];
  for (const run of runs(segments, moon, [12, 1, 2])) {
    const start = run[0].start;
    const end = run[run.length - 1].end;
    const phases: Array<{ phase: "rising" | "peak" | "setting"; saturn_sign: string; start: number; end: number }> = [];
    for (const seg of run) {
      const phase = PHASE[count(moon, seg.sign)];
      const last = phases[phases.length - 1];
      if (last && last.phase === phase) last.end = seg.end;
      else if (!phases.some((p) => p.phase === phase)) phases.push({ phase, saturn_sign: SIGN_NAMES[seg.sign], start: seg.start, end: seg.end });
    }
    phases.forEach((p, i) => (p.end = i + 1 < phases.length ? phases[i + 1].start : end));
    raw.push({ kind: "sade_sati", start, end, phases: phases.map((p) => ({ phase: p.phase, saturn_sign: p.saturn_sign, starts_at: iso(p.start), ends_at: iso(p.end) })) });
  }
  for (const [house, kind] of [[4, "dhaiya_kantaka"], [8, "dhaiya_ashtama"]] as const) {
    for (const run of runs(segments, moon, [house])) {
      const start = run[0].start;
      const end = run[run.length - 1].end;
      raw.push({ kind, start, end, phases: [{ phase: "dhaiya", saturn_sign: SIGN_NAMES[run[0].sign], starts_at: iso(start), ends_at: iso(end) }] });
    }
  }
  const kept = raw.filter((p) => p.end > birth && p.start < scanEnd - 9 * YEAR).sort((a, b) => a.start - b.start);
  const periods: SadeSatiPeriodV1[] = kept.map((p, index) => ({
    index,
    kind: p.kind,
    status: p.start <= asOf && asOf < p.end ? "current" : p.end <= asOf ? "past" : "upcoming",
    starts_at: iso(p.start),
    ends_at: iso(p.end),
    age_start: age(p.start),
    age_end: age(p.end),
    started_before_birth: p.start < birth,
    phases: p.phases,
  }));
  const saturnSign = signAt("saturn", asOf);
  const house = count(moon, saturnSign);
  const kind = house in PHASE ? "sade_sati" : (DHAIYA[house] ?? null);
  const cur = periods.find((p) => p.status === "current");
  const nxt = periods.find((p) => p.status === "upcoming");
  const nxtSade = periods.find((p) => p.status === "upcoming" && p.kind === "sade_sati");
  return {
    chart_id: "fixture",
    as_of: iso(asOf),
    birth: iso(birth),
    moon_sign: SIGN_NAMES[moon],
    current: {
      kind,
      phase: PHASE[house] ?? (kind ? "dhaiya" : null),
      saturn_sign: SIGN_NAMES[saturnSign],
      house_from_moon: house,
      period_index: cur ? cur.index : null,
    },
    next_index: nxt ? nxt.index : null,
    next_sade_sati_index: nxtSade ? nxtSade.index : null,
    periods,
    proof: PROOF_SADE_SATI,
  };
}

const ord = (n: number) => `${n}${n % 100 >= 10 && n % 100 <= 20 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function reasonText(r: GocharaPlanetV1): string {
  const name = cap(r.planet);
  const h = ord(r.house_from_moon);
  const b = r.bindus;
  switch (r.reason_code) {
    case "nodes_not_rated":
      return `${name} is shown by position only: the classical gochara tables rate the seven grahas.`;
    case "vedha_blocked":
      return `${name} in the ${h} from the Moon is a favourable house but ${r.vedha_by.map(cap).join(", ")} stands in its vedha house ${r.vedha_house}, which obstructs it.`;
    case "favourable_strong":
      return `${name} in the ${h} from the Moon is favourable and holds ${b} bindus here.`;
    case "favourable_weak_bindus":
      return `${name} in the ${h} from the Moon is favourable but holds only ${b} bindus, so the result is muted.`;
    case "unfavourable_softened":
      return `${name} in the ${h} from the Moon is not a favourable house, softened by ${b} bindus.`;
    default:
      return `${name} in the ${h} from the Moon is not a favourable house and holds ${b} bindus.`;
  }
}

export function fixtureGochara(natal: VedicChartArtifact, when: number): GocharaV1 {
  const { lagna, moon } = natalSigns(natal);
  const bav = Object.fromEntries(natal.strengthMetrics.ashtakavarga.map((r) => [r.planet, r.bindusBySign]));
  const sav = natal.strengthMetrics.sarvashtakavarga;
  const signs: Record<string, number> = {};
  const lons: Record<string, number> = {};
  for (const b of BODIES) {
    lons[b] = longitude(b, when);
    signs[b] = Math.floor(lons[b] / 30) % 12;
  }
  const planets: GocharaPlanetV1[] = BODIES.map((planet) => {
    const sign = signs[planet];
    const houseMoon = count(moon, sign);
    const row: GocharaPlanetV1 = {
      planet,
      sign: SIGN_NAMES[sign],
      sign_index: sign,
      degrees_in_sign: Math.round((lons[planet] % 30) * 100) / 100,
      retrograde: planet === "rahu" || planet === "ketu" ? true : isRetrograde(planet as EphemerisBody, new Date(when)),
      house_from_moon: houseMoon,
      house_from_lagna: count(lagna, sign),
      bindus: null,
      sav: sav[sign],
      favourable_houses: [],
      favourable: null,
      vedha_house: null,
      vedha_by: [],
      verdict: "not_rated",
      reason_code: "nodes_not_rated",
      reason: "",
    };
    const table = FAVOURABLE[planet];
    if (table) {
      const [good, vedha] = table;
      const bindus = bav[planet][sign];
      const favourable = good.includes(houseMoon);
      const vedhaHouse = favourable ? vedha[good.indexOf(houseMoon)] : null;
      const blockers = vedhaHouse
        ? BODIES.slice(0, 7).filter((o) => o !== planet && !EXEMPT.some((p) => p.includes(o) && p.includes(planet)) && count(moon, signs[o]) === vedhaHouse)
        : [];
      let verdict: GocharaPlanetV1["verdict"];
      let code: GocharaPlanetV1["reason_code"];
      if (favourable && blockers.length) [verdict, code] = ["mixed", "vedha_blocked"];
      else if (favourable && bindus >= 4) [verdict, code] = ["favourable", "favourable_strong"];
      else if (favourable) [verdict, code] = ["mixed", "favourable_weak_bindus"];
      else if (bindus >= 5) [verdict, code] = ["mixed", "unfavourable_softened"];
      else [verdict, code] = ["unfavourable", "unfavourable"];
      Object.assign(row, { bindus, favourable_houses: good, favourable, vedha_house: vedhaHouse, vedha_by: blockers, verdict, reason_code: code });
    }
    row.reason = reasonText(row);
    return row;
  });
  const sh = count(moon, signs.saturn);
  const kind = sh in PHASE ? "sade_sati" : (DHAIYA[sh] ?? null);
  const tally: Record<string, number> = { favourable: 0, mixed: 0, unfavourable: 0 };
  for (const p of planets) if (p.verdict in tally) tally[p.verdict] += 1;
  return {
    chart_id: "fixture",
    date: iso(when),
    moon_sign: SIGN_NAMES[moon],
    lagna_sign: SIGN_NAMES[lagna],
    planets,
    saturn_status: { kind, phase: PHASE[sh] ?? (kind ? "dhaiya" : null), house_from_moon: sh },
    tally,
    proof: PROOF_GOCHARA,
  };
}

export function fixtureDoubleTransit(natal: VedicChartArtifact, start: number, months = 24): DoubleTransitV1 {
  const { lagna } = natalSigns(natal);
  const end = start + Math.round(months * 30.4375) * DAY;
  const jup = signSegments("jupiter", start, end);
  const sat = signSegments("saturn", start, end);
  const cuts = [...new Set([start, end, ...jup.map((s) => s.end), ...sat.map((s) => s.end)])].sort((a, b) => a - b);
  const at = (segs: Segment[], t: number) => (segs.find((s) => s.start <= t && t < s.end) ?? segs[segs.length - 1]).sign;
  const casts = (p: string) => [1, 7, ...(SPECIAL[p] ?? [])];
  const merged: Array<{ start: number; end: number; j: number; s: number; houses: number[] }> = [];
  for (let i = 0; i + 1 < cuts.length; i++) {
    const a = cuts[i];
    const b = cuts[i + 1];
    if (b <= a) continue;
    const j = at(jup, a);
    const s = at(sat, a);
    const houses = Array.from({ length: 12 }, (_, k) => k + 1).filter((h) => {
      const sign = (lagna + h - 1) % 12;
      return casts("jupiter").includes(count(j, sign)) && casts("saturn").includes(count(s, sign));
    });
    const last = merged[merged.length - 1];
    if (last && last.j === j && last.s === s) last.end = b;
    else merged.push({ start: a, end: b, j, s, houses });
  }
  const houses = Array.from({ length: 12 }, (_, k) => k + 1).map((h) => {
    const windows: Array<{ start: number; end: number }> = [];
    for (const sp of merged) {
      if (!sp.houses.includes(h)) continue;
      const last = windows[windows.length - 1];
      if (last && last.end === sp.start) last.end = sp.end;
      else windows.push({ start: sp.start, end: sp.end });
    }
    return {
      house: h,
      sign: SIGN_NAMES[(lagna + h - 1) % 12],
      active_now: windows.some((w) => w.start <= start && start < w.end),
      days: windows.reduce((n, w) => n + Math.floor((w.end - w.start) / DAY), 0),
      windows: windows.map((w) => ({ starts_at: iso(w.start), ends_at: iso(w.end) })),
    };
  });
  return {
    chart_id: "fixture",
    start: iso(start),
    end: iso(end),
    months,
    reference: "lagna",
    reference_sign: SIGN_NAMES[lagna],
    jupiter_now: SIGN_NAMES[at(jup, start)],
    saturn_now: SIGN_NAMES[at(sat, start)],
    spans: merged.map((s) => ({ starts_at: iso(s.start), ends_at: iso(s.end), jupiter_sign: SIGN_NAMES[s.j], saturn_sign: SIGN_NAMES[s.s], houses: s.houses })),
    houses,
    proof: PROOF_DOUBLE,
  };
}

/** Fixture-mode source over a natal artifact. Dates are noon UTC of the picked day, matching the API's 06:30Z. */
export function fixtureDepthSource(natal: VedicChartArtifact): TransitDepthSource {
  const now = () => Date.now();
  return {
    getSadeSati: async () => fixtureSadeSati(natal, now()),
    getGochara: async (dateIso) => fixtureGochara(natal, dateIso ? Date.parse(`${dateIso}T06:30:00Z`) : now()),
    getDoubleTransit: async () => fixtureDoubleTransit(natal, now()),
  };
}
