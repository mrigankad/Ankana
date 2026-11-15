import type { VedicChartArtifact } from "@astro/astrology-core";

import type { AskThread, ChartBundle, LalKitabReportJson } from "./types";

/**
 * View-model builders for the chart workspace. Everything here is derived from the
 * computed VedicChartArtifact and the lal-kitab report; nothing is hardcoded from Paper
 * except the fixture copy marked as such.
 */

export const PLANET_ORDER = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"] as const;
export const PLANET_ABBR: Record<string, string> = {
  sun: "Su", moon: "Mo", mars: "Ma", mercury: "Me", jupiter: "Ju", venus: "Ve", saturn: "Sa", rahu: "Ra", ketu: "Ke",
};
const SIGN_ABBR = ["Ar", "Ta", "Ge", "Ca", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"];
const VARA = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export const cap = (s: string) => (s ? s[0]!.toUpperCase() + s.slice(1) : s);

export function ordinal(n: number) {
  const v = n % 100;
  if (v >= 11 && v <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

/** 10.5366 in Pisces -> "10°32′ Pi" */
export function fmtDeg(degreesInSign: number, signIndex: number, withSign = true) {
  let d = Math.floor(degreesInSign);
  let m = Math.round((degreesInSign - d) * 60);
  if (m === 60) {
    d += 1;
    m = 0;
  }
  const base = `${d}°${String(m).padStart(2, "0")}′`;
  return withSign ? `${base} ${SIGN_ABBR[signIndex] ?? ""}` : base;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function monthYear(iso: string | Date) {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}
export function dayMonthYear(d: Date) {
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

export function joinList(items: string[]) {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/* ---------------------------------- header --------------------------------- */

export interface ChartHeaderView {
  name: string;
  initials: string;
  birthLine: string;
  ageYears: number;
  lagna: string;
  moon: string;
  dasha: string;
}

function tzLabel(tz: string) {
  return tz === "Asia/Kolkata" ? "IST" : tz;
}

export function currentDasha(artifact: VedicChartArtifact, now = new Date()) {
  const t = now.getTime();
  const maha = artifact.vimshottari.mahadashas.find((m) => t >= Date.parse(m.start) && t < Date.parse(m.end));
  const antar = maha?.children?.find((c) => t >= Date.parse(c.start) && t < Date.parse(c.end));
  return { maha, antar };
}

export function buildHeader(bundle: ChartBundle, now = new Date()): ChartHeaderView {
  const a = bundle.artifact;
  const input = a.calculationMetadata.input;
  const [y, mo, d] = input.birthDate.split("-").map(Number) as [number, number, number];
  const place = (input.placeLabel ?? "").split(",")[0]?.trim();
  const birthLine = [`${d} ${MONTHS[mo - 1]} ${y}`, input.birthTime ? `${input.birthTime} ${tzLabel(input.timezoneName)}` : "", place]
    .filter(Boolean)
    .join(", ");
  const moon = a.planets.find((p) => p.planet === "moon");
  const { maha, antar } = currentDasha(a, now);
  let age = now.getUTCFullYear() - y;
  if (now.getTime() < Date.UTC(now.getUTCFullYear(), mo - 1, d)) age -= 1;
  return {
    name: bundle.client.name,
    initials: bundle.client.initials,
    birthLine,
    ageYears: age,
    lagna: `${a.ascendant.signName} lagna`,
    moon: moon ? `Moon in ${moon.nakshatra} ${moon.pada}` : "Moon",
    dasha: maha ? `${cap(maha.planet)}${antar ? ` / ${cap(antar.planet)}` : ""} dasha` : "Dasha",
  };
}

/* ----------------------------------- chart --------------------------------- */

export interface HouseCell {
  house: number;
  /** 1..12 sign number */
  sign: number;
  planets: string[];
}

export function buildHouses(artifact: VedicChartArtifact): HouseCell[] {
  return artifact.houses.map((h) => ({
    house: h.number,
    sign: h.signIndex + 1,
    planets: PLANET_ORDER.filter((p) => h.occupants.includes(p)).map((p) => PLANET_ABBR[p]!),
  }));
}

export interface PlanetRow {
  key: string;
  label: string;
  degree: string;
  nakshatra: string;
  chip: { label: string; tone: "accent" | "ok" | "alert" | "muted" };
  house: number;
  signName: string;
  signIndex: number;
  dignity: string;
}

function dignityChip(dignity: string): PlanetRow["chip"] {
  switch (dignity) {
    case "own":
      return { label: "Own sign", tone: "ok" };
    case "exalted":
      return { label: "Exalted", tone: "ok" };
    case "moolatrikona":
      return { label: "Moolatrikona", tone: "ok" };
    case "debilitated":
      return { label: "Debilitated", tone: "alert" };
    default:
      return { label: cap(dignity.replace(/_/g, " ")), tone: "muted" };
  }
}

export function buildPlanetRows(artifact: VedicChartArtifact): PlanetRow[] {
  const asc = artifact.ascendant;
  const rows: PlanetRow[] = [
    {
      key: "lagna",
      label: "Lagna",
      degree: fmtDeg(asc.degreesInSign, asc.signIndex),
      nakshatra: `${asc.nakshatra} ${asc.pada}`,
      chip: { label: "H1", tone: "accent" },
      house: 1,
      signName: asc.signName,
      signIndex: asc.signIndex,
      dignity: "",
    },
  ];
  for (const id of PLANET_ORDER) {
    const p = artifact.planets.find((x) => x.planet === id);
    if (!p) continue;
    rows.push({
      key: id,
      label: cap(id),
      degree: fmtDeg(p.degreesInSign, p.signIndex),
      nakshatra: `${p.nakshatra} ${p.pada}`,
      chip: dignityChip(p.dignity),
      house: p.house,
      signName: p.signName,
      signIndex: p.signIndex,
      dignity: p.dignity,
    });
  }
  return rows;
}

export function buildPanchang(artifact: VedicChartArtifact) {
  const p = artifact.panchang;
  return {
    tithi: `${p.tithi.name}, ${p.tithi.paksha}`,
    vara: VARA[p.vara.index] ?? p.vara.name,
    nakshatra: `${p.moonNakshatra.name}, pada ${p.moonNakshatra.pada}`,
    yoga: p.yoga.name,
  };
}

/** One sentence worth raising first, from the strongest and weakest placements. */
export function buildWorthRaising(artifact: VedicChartArtifact) {
  const real = artifact.planets.filter((p) => p.planet !== "rahu" && p.planet !== "ketu");
  const strong = real.find((p) => p.dignity === "own" || p.dignity === "exalted" || p.dignity === "moolatrikona");
  const weak = real.find((p) => p.dignity === "debilitated");
  const strongWord = (d: string) => (d === "exalted" ? "exalted" : "strong in its own sign");
  if (strong && weak) {
    return `${cap(strong.planet)} is ${strongWord(strong.dignity)} in the ${ordinal(strong.house)}, while ${cap(weak.planet)} is debilitated in the ${ordinal(weak.house)}. Both bear on her career question.`;
  }
  if (strong) return `${cap(strong.planet)} is ${strongWord(strong.dignity)} in the ${ordinal(strong.house)}. It is worth raising first.`;
  if (weak) return `${cap(weak.planet)} is debilitated in the ${ordinal(weak.house)}. It is worth raising first.`;
  return "No planet sits at an extreme of dignity, so start from the current dasha.";
}

/* ----------------------------------- dashas -------------------------------- */

export interface DashaSegment {
  planet: string;
  label: string;
  start: number;
  end: number;
  /** years shown in the bar (first bar is clipped to the balance at birth) */
  years: number;
  endYear: number;
  state: "past" | "now" | "next";
}

const YEAR_MS = 365.2425 * 24 * 3600 * 1000;

export interface DashaTimelineView {
  segments: DashaSegment[];
  /** fraction 0..1 of the bar where today falls, and the index of the segment containing it */
  todayFraction: number;
  todayIndex: number;
  todayLabel: string;
  balanceYears: number;
  currentIndex: number;
}

type DashaNode = { planet: string; name?: string; start: string; end: string; children?: DashaNode[] };

export function buildDashaTimeline(
  mahadashas: DashaNode[],
  birth: Date,
  balanceYears: number,
  now = new Date(),
): DashaTimelineView {
  const t = now.getTime();
  const b = birth.getTime();
  const segs: DashaSegment[] = [];
  for (const m of mahadashas) {
    const s = Date.parse(m.start);
    const e = Date.parse(m.end);
    if (e <= b) continue;
    const from = Math.max(s, b);
    segs.push({
      planet: m.planet,
      label: m.name ?? cap(m.planet),
      start: s,
      end: e,
      years: (e - from) / YEAR_MS,
      endYear: new Date(e).getUTCFullYear(),
      state: t >= e ? "past" : t >= s ? "now" : "next",
    });
  }
  const total = segs.reduce((a, s) => a + s.years, 0);
  let acc = 0;
  let frac = 0;
  let idx = Math.max(0, segs.findIndex((s) => s.state === "now"));
  for (let i = 0; i < segs.length; i++) {
    const s = segs[i]!;
    if (s.state === "now") {
      const from = Math.max(s.start, b);
      frac = (acc + ((t - from) / (s.end - from)) * s.years) / total;
      idx = i;
      break;
    }
    acc += s.years;
  }
  return {
    segments: segs,
    todayFraction: frac,
    todayIndex: idx,
    todayLabel: `Today, ${dayMonthYear(now)}`,
    balanceYears,
    currentIndex: idx,
  };
}

export interface AntarRow {
  planet: string;
  range: string;
  tag: "Past" | "Now" | "Next" | "";
  state: "past" | "now" | "next" | "later";
}

export function buildAntardashas(maha: DashaNode | undefined, now = new Date()) {
  if (!maha) return { title: "", range: "", rows: [] as AntarRow[] };
  const t = now.getTime();
  const kids = maha.children ?? [];
  let nextSeen = false;
  const rows: AntarRow[] = kids.map((c) => {
    const s = Date.parse(c.start);
    const e = Date.parse(c.end);
    let state: AntarRow["state"] = "later";
    let tag: AntarRow["tag"] = "";
    if (t >= e) {
      state = "past";
      tag = "Past";
    } else if (t >= s) {
      state = "now";
      tag = "Now";
    } else if (!nextSeen) {
      nextSeen = true;
      state = "next";
      tag = "Next";
    }
    return { planet: cap(c.name ?? c.planet), range: `${monthYear(c.start)} to ${monthYear(c.end)}`, tag, state };
  });
  return {
    title: `${cap(maha.name ?? maha.planet)} dasha, antardashas`,
    range: `${monthYear(maha.start)} to ${monthYear(maha.end)}`,
    rows,
  };
}

const THEME: Record<number, string> = {
  1: "self and vitality", 2: "income and speech", 3: "effort and courage", 4: "home and peace", 5: "judgment and creativity", 6: "work and service",
  7: "partnership", 8: "sudden change and shared money", 9: "fortune and belief", 10: "career and standing", 11: "gains and networks", 12: "retreat and expenses",
};
const SHORT: Record<number, string> = {
  1: "self", 2: "income", 3: "effort", 4: "home", 5: "creativity", 6: "work", 7: "partnership", 8: "shared money", 9: "fortune", 10: "career", 11: "gains", 12: "expenses",
};

/** The "why this period" copy, composed from lordship and dignity. Returns segments with cite markers. */
export function buildWhyPeriod(artifact: VedicChartArtifact, now = new Date()) {
  const { maha, antar } = currentDasha(artifact, now);
  if (!maha) return { segments: [] as Array<{ text: string; cite?: number }>, citations: [] as Array<{ n: number; source: string; detail: string }> };
  const planet = (id: string) => artifact.planets.find((p) => p.planet === id)!;
  const lordOf = (id: string) => artifact.houses.filter((h) => h.lord === id).map((h) => h.number);
  const m = planet(maha.planet);
  const mLords = lordOf(maha.planet);
  const a = antar ? planet(antar.planet) : undefined;
  const aLords = antar ? lordOf(antar.planet) : [];
  const nextAntar = maha.children?.find((c) => Date.parse(c.start) >= (antar ? Date.parse(antar.end) : 0));
  const housesText = (hs: number[]) => (hs.length ? hs.map(ordinal).join(" and ") : "no");
  const m1 = `${cap(maha.planet)} rules her ${housesText(mLords)} house${mLords.length === 1 ? "" : "s"} and sits in the ${ordinal(m.house)}, so this decade turns ${THEME[mLords[0] ?? m.house]} toward ${THEME[m.house]}`;
  const segments: Array<{ text: string; cite?: number }> = [{ text: `${m1} `, cite: 1 }];
  const citations = [
    { n: 1, source: "Planets", detail: `${cap(maha.planet)} ${fmtDeg(m.degreesInSign, m.signIndex, false)} ${m.signName}, ${m.nakshatra} ${m.pada}, house ${m.house}` },
  ];
  if (a && antar) {
    const dign = a.dignity === "debilitated" ? ` but is debilitated in the ${ordinal(a.house)}` : ` and sits in the ${ordinal(a.house)}`;
    const themes = joinList(aLords.map((h) => SHORT[h] ?? ""));
    segments.push({ text: `. ${cap(antar.planet)}, the current sub-period, owns the ${housesText(aLords)} house${aLords.length === 1 ? "" : "s"} of ${themes}${dign} `, cite: 2 });
    citations.push({ n: 2, source: "Planets", detail: `${cap(antar.planet)} ${fmtDeg(a.degreesInSign, a.signIndex, false)} ${a.signName}${a.dignity !== "neutral" && a.dignity !== "friend" ? `, ${a.dignity === "own" ? "own sign" : a.dignity}` : ""}` });
  }
  if (nextAntar) {
    segments.push({ text: `. ${cap(nextAntar.planet)} follows in ${new Date(nextAntar.start).toLocaleString("en-GB", { month: "long", timeZone: "UTC" })} ${new Date(nextAntar.start).getUTCFullYear()}, the next point to revisit with her `, cite: 3 });
    citations.push({ n: 3, source: "Dashas", detail: `${cap(maha.planet)} antardasha table` });
  }
  segments.push({ text: "." });
  return { segments, citations };
}

/* --------------------------------- lal kitab ------------------------------- */

export interface LkHouseView {
  house: number;
  pakka: boolean;
  planets: Array<{ key: string; name: string; state: "awake" | "dormant"; pakka: boolean; sub: string }>;
}

type LkSleeping = { planet: string; house: number; status: string; rule?: string; selfAwakeningAge?: number; awakenerPresent?: boolean };
type LkRin = {
  id?: string; kind?: string; basis?: string; planet?: string; house?: number; with?: string[]; needs_review?: boolean;
  cite?: { vol?: string; printed_page?: number }; remedy_cite?: { printed_page?: number };
};
type LkVarshphal = {
  age: number;
  planets: Array<{ planet: string; natalHouse: number; annualHouse: number; month: string }>;
  cycle35?: { cyclePlanet?: string; part?: string; needs_review?: boolean };
};

const LK_NAME = (p: string) => (["jupiter", "venus", "mercury", "saturn"].includes(p) ? cap(p).slice(0, 3) : cap(p));

export function buildLalKitab(lk: LalKitabReportJson) {
  const sleeping = (lk.sleepingPlanets ?? []) as LkSleeping[];
  const byPlanet = new Map(sleeping.map((s) => [s.planet, s]));
  const houses: LkHouseView[] = [];
  for (let h = 1; h <= 12; h++) {
    const names = (lk.chart.houses[h] ?? []) as string[];
    const planets = names.map((p) => {
      const s = byPlanet.get(p);
      const dormant = s?.status === "dormant";
      const pakka = s?.rule === "own_pakka_ghar";
      return {
        key: p,
        name: LK_NAME(p),
        state: dormant ? ("dormant" as const) : ("awake" as const),
        pakka,
        sub: dormant ? (s?.selfAwakeningAge ? `wakes at ${s.selfAwakeningAge}` : "dormant") : "awake",
      };
    });
    houses.push({ house: h, pakka: planets.some((p) => p.pakka), planets });
  }
  const dormant = sleeping.filter((s) => s.status === "dormant");
  const awake = sleeping.length - dormant.length;
  const items = dormant.map((d) => `${cap(d.planet)} (H${d.house}, wakes at ${d.selfAwakeningAge})`);
  const reasons = new Set(dormant.map((d) => d.rule));
  const summary = {
    title: `${dormant.length} dormant planet${dormant.length === 1 ? "" : "s"}, ${awake} awake`,
    body: dormant.length
      ? `${joinList(items)} ${dormant.length === 1 ? "is" : "are"} ${reasons.has("unaspected") ? "unaspected, so the book treats them as dormant until woken" : "dormant until woken"}. Book p.116 to 117. Advisory only.`
      : "Every planet is awake in this chart. Book p.116 to 117. Advisory only.",
  };

  const rinRaw = (lk.rin ?? []) as LkRin[];
  const NUM = ["none", "one", "two", "three", "four", "five", "six"];
  let indicatorSeen = 0;
  const rin = rinRaw.map((r) => {
    const planet = cap(r.planet ?? "");
    const first = r.basis === "first_degree_father" || (r.kind ?? "").includes("first degree");
    let title = r.kind ?? "";
    let note = "";
    if (first) {
      title = title.replace(/ \((.*)\)$/, ", $1") + ` (${planet})`;
      const withTxt = r.with?.length ? ` with ${joinList(r.with.map(cap))}` : "";
      note = `${planet} sits in H${r.house}${withTxt}, the pattern the book lists for this debt.`;
    } else {
      title = title.replace(/\s*\(indicator\)/, ` (${planet}, H${r.house})`);
      note =
        indicatorSeen === 0
          ? "An indicator only, from the book's opening lines on debts."
          : `An indicator only. All ${NUM[rinRaw.length] ?? rinRaw.length} share one remedy, book p.${rinRaw.find((x) => x.remedy_cite)?.remedy_cite?.printed_page ?? ""}.`;
      indicatorSeen += 1;
    }
    return {
      key: `${r.id}-${r.planet}`,
      first,
      title,
      note,
      review: !!r.needs_review,
      cite: r.cite?.printed_page ? `Vol ${r.cite.vol ?? "I"} p.${r.cite.printed_page}` : "",
    };
  });

  const v = lk.varshphal as unknown as LkVarshphal;
  const counts = new Map<number, number>();
  v.planets.forEach((p) => counts.set(p.annualHouse, (counts.get(p.annualHouse) ?? 0) + 1));
  const shared = v.planets.filter((p) => (counts.get(p.annualHouse) ?? 0) > 1);
  const sharedHouse = shared[0]?.annualHouse;
  const varshphal = {
    age: v.age,
    cycle: v.cycle35
      ? `35-year cycle, ${cap(v.cycle35.cyclePlanet ?? "")} ${v.cycle35.part === "last" ? "part" : "part"}${v.cycle35.needs_review ? " · needs review" : ""}`
      : "",
    cells: PLANET_ORDER.map((id) => v.planets.find((p) => p.planet === id)).filter(Boolean).map((p) => ({
      planet: cap(p!.planet),
      move: `${p!.natalHouse} to ${p!.annualHouse}`,
      month: p!.month,
      hot: (counts.get(p!.annualHouse) ?? 0) > 1,
    })),
    note: shared.length
      ? `${joinList(shared.map((p) => cap(p.planet)))} both move to annual H${sharedHouse} this year. Advisory only.`
      : "No two planets share an annual house this year. Advisory only.",
  };
  const masnui = (lk.masnui ?? []) as unknown[];
  return { houses, summary, rin, varshphal, masnuiCount: masnui.length };
}

/* ------------------------------- ask thread fixtures ----------------------- */

/** Fixture copy from Paper U06 for the Dashas tab. */
export const askDashasFixture: AskThread = {
  question: "When does the Mars period end, and what should I tell her about Rahu?",
  answer: [
    { text: "Mars runs until about 23 February 2027 ", cite: 1 },
    { text: ". Rahu then runs 18 months, to August 2028, inside her Moon dasha. Rahu sits in her 8th house " , cite: 2 },
    { text: ", so sudden change and shared money are the natural theme to prepare her for." },
  ],
  citations: [
    { n: 1, source: "Dashas", detail: "Moon / Mars, Jul 2026 to Feb 2027" },
    { n: 2, source: "Planets", detail: "Rahu 14°07′ Libra, house 8" },
  ],
  checks: { engine: "Engine · checked 4 facts", verifier: "Verifier · all claims match" },
  suggestions: ["Which remedy fits Mars?", "Show Yogini dasha"],
};

const NAME_WORDS =
  /\b(sun|moon|mars|mercury|jupiter|venus|saturn|rahu|ketu|aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)\b/g;

/** Capitalise planet and sign names inside generated sentences ("Strengthen jupiter" becomes "Strengthen Jupiter"). */
export function capNames(text: string): string {
  return text.replace(NAME_WORDS, (m) => cap(m));
}
