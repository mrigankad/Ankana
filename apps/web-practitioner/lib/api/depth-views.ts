import { tName } from "../i18n/translate";
import type { AshtakavargaDepth, DashaNode, DashasDepth, PlanetDepth, Proof } from "./depth";

/**
 * View mappers for the depth tabs (planets, ashtakavarga, dashas). Pure functions: the API
 * gives numbers and rule ids, these produce the strings, tones and proof drawers the UI shows.
 * `T` is the translate function; every English string passes through it.
 */
export type T = (text: string, params?: Record<string, string | number>) => string;

const cap = (s: string) => (s ? s[0]!.toUpperCase() + s.slice(1) : s);

export const SIGN_ABBR = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"] as const;
const PLANET_ABBR: Record<string, string> = { sun: "Su", moon: "Mo", mars: "Ma", mercury: "Me", jupiter: "Ju", venus: "Ve", saturn: "Sa", rahu: "Ra", ketu: "Ke", lagna: "La" };

/* ------------------------------------------------------------------ proof */

export interface ProofView {
  title: string;
  value: string;
  inputs: Array<{ label: string; value: string }>;
  rule: string;
  source: string;
}

const INPUT_LABELS: Record<string, string> = {
  sidereal_longitude: "Sidereal longitude",
  span_degrees: "Nakshatra span",
  nakshatra_number: "Nakshatra number (1 to 27)",
  fraction_traversed: "Fraction of the nakshatra crossed",
  degrees_in_nakshatra: "Degrees into the nakshatra",
  pada_span_degrees: "Pada span",
  pada: "Pada",
  cycle_position: "Position in the nine-lord cycle",
  lord: "Lord",
  sign: "Sign",
  separation_from_sun: "Separation from the Sun",
  orb: "Combustion orb",
  retrograde: "Retrograde",
  planet: "Planet",
  degrees_in_sign: "Degrees in sign",
  dignity: "Dignity",
  sign_parity: "Sign parity",
  slice: "Six degree slice (1 to 5)",
  rank_among_seven: "Rank by degree among the seven (1 is highest)",
  karaka: "Karaka",
  lagna_sign: "Lagna sign",
  houses: "Houses ruled",
  contributors: "Contributors",
  expected_total: "Classical total",
};

const RULES: Record<string, string> = {
  nakshatra: "The zodiac is divided into 27 nakshatras of 13 degrees 20 minutes each, counted from 0 degrees Aries. The sidereal longitude decides which one holds the planet.",
  pada: "Each nakshatra has four padas of 3 degrees 20 minutes. The pada is how far the planet has travelled into its nakshatra.",
  nakshatra_lord: "Nakshatras take the nine Vimshottari lords in a repeating order: Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury.",
  sign_lord: "Each sign has one ruler. Sun rules Leo and Moon rules Cancer; Mars, Mercury, Venus, Jupiter and Saturn rule two signs each.",
  retrograde: "A planet is retrograde when its apparent daily motion against the zodiac is backward. The Sun and Moon never are; Rahu and Ketu are always counted retrograde.",
  combust: "A planet too close to the Sun is combust and loses strength. The limit is a classical orb in degrees, narrower for some planets when retrograde.",
  combust_na: "The Sun, Rahu and Ketu are not tested for combustion.",
  dignity: "Dignity compares the planet's sign with its own, exaltation, debilitation and moolatrikona signs, then with the sign ruler's natural friendship.",
  avastha_baladi: "Baladi avastha splits each sign into five slices of 6 degrees: bala, kumara, yuva, vriddha, mrita. Odd signs run in that order, even signs run in reverse.",
  avastha_na: "Baladi avastha is not assigned to Rahu and Ketu.",
  chara_karaka: "Jaimini ranks the seven planets from Sun to Saturn by degrees travelled in their sign. The highest is the atmakaraka, then amatya, bhratri, matri, putra, gnati and the lowest is the darakaraka.",
  house_lordship: "With whole sign houses, a planet rules the houses whose signs it rules, counted from the lagna sign.",
  ashtakavarga: "Each of the seven planets gives bindus to the signs that fall in its benefic places counted from the seven planets and the lagna. The grid is the sum of those bindus.",
  vimshottari: "Vimshottari runs a 120 year cycle. A maha dasha lasts the lord's years. Inside it, each sub period is the parent's length times the sub lord's years divided by 120, starting with the parent's own lord.",
  yogini: "Yogini dasha runs a 36 year cycle of eight yoginis. Each antardasha is the parent's length times the sub yogini's years divided by 36, starting with the parent's own yogini.",
};

const DEGREE_KEYS = new Set([
  "sidereal_longitude", "span_degrees", "degrees_in_nakshatra", "pada_span_degrees",
  "separation_from_sun", "orb", "degrees_in_sign",
]);

function inputValue(key: string, v: string | number | boolean | null | undefined, t: T): string {
  if (v === null || v === undefined) return t("none");
  if (typeof v === "boolean") return v ? t("Yes") : t("No");
  if (typeof v === "number") {
    if (DEGREE_KEYS.has(key)) return degreeText(v);
    if (key === "fraction_traversed") return `${Math.round(v * 100)}%`;
    return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
  }
  if (key === "planet" || key === "lord" || key === "karaka") return planetWord(v, t);
  if (key === "sign" || key === "lagna_sign") return t(v);
  if (key === "sign_parity") return v === "odd" ? t("Odd") : t("Even");
  if (key === "dignity") return dignityWord(v, t);
  return v;
}

export function planetWord(p: string, t: T): string {
  if (!p) return "";
  if (p === "lagna") return t("Lagna");
  const lower = p.toLowerCase();
  const known = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"];
  if (known.includes(lower)) return t(cap(lower));
  if (KARAKAS[lower]) return t(KARAKAS[lower]!);
  return t(p);
}

const KARAKAS: Record<string, string> = {
  atmakaraka: "Atmakaraka", amatyakaraka: "Amatyakaraka", bhratrikaraka: "Bhratrikaraka", matrikaraka: "Matrikaraka",
  putrakaraka: "Putrakaraka", gnatikaraka: "Gnatikaraka", darakaraka: "Darakaraka",
};

export function dignityWord(d: string, t: T): string {
  return t(d === "own" ? "Own sign" : cap(d));
}

export type Tone = "good" | "bad" | "plain";
export function dignityTone(d: string): Tone {
  if (d === "exalted" || d === "moolatrikona" || d === "own") return "good";
  if (d === "debilitated" || d === "enemy") return "bad";
  return "plain";
}

/** Turn a backend proof into a drawer. */
export function proofView(p: Proof, title: string, value: string, t: T): ProofView {
  return {
    title,
    value,
    inputs: p.inputs.map((i) => ({ label: t(INPUT_LABELS[i.key] ?? i.key), value: inputValue(i.key, i.value, t) })),
    rule: t(RULES[p.rule_id] ?? p.rule_id),
    source: t(p.source),
  };
}

/* ---------------------------------------------------------------- planets */

export interface Fact {
  id: string;
  label: string;
  text: string;
  tone: Tone;
  proof: ProofView;
}

export interface PlanetView {
  planet: string;
  name: string;
  position: string;
  degree: string;
  house: number;
  facts: Record<"nakshatra" | "pada" | "nakshatraLord" | "signLord" | "retrograde" | "combust" | "dignity" | "avastha" | "karaka" | "lordships", Fact>;
  isNode: boolean;
}

export function degreeText(deg: number): string {
  const d = Math.floor(deg);
  const m = Math.floor((deg - d) * 60);
  return `${d}°${String(m).padStart(2, "0")}′`;
}

export function planetViews(data: { planets: PlanetDepth[] }, t: T): PlanetView[] {
  return data.planets.map((p) => {
    const name = planetWord(p.planet, t);
    const mk = (id: string, label: string, text: string, tone: Tone, proof: Proof, value = text): Fact => ({
      id, label: t(label), text, tone, proof: proofView(proof, `${name}: ${t(label)}`, value, t),
    });
    const pr = p.proof;
    const isNode = p.planet === "rahu" || p.planet === "ketu";
    const combustText = !p.combust.applicable ? t("Not tested") : p.combust.is_combust ? t("Combust") : t("Clear");
    return {
      planet: p.planet,
      name,
      position: t(p.sign),
      degree: degreeText(p.degrees_in_sign),
      house: p.house,
      isNode,
      facts: {
        nakshatra: mk("nakshatra", "Nakshatra", tName(t, p.nakshatra), "plain", pr.nakshatra),
        pada: mk("pada", "Pada", `${t("pada")} ${p.pada}`, "plain", pr.pada, String(p.pada)),
        nakshatraLord: mk("nakshatraLord", "Nakshatra lord", planetWord(p.nakshatra_lord, t), "plain", pr.nakshatra_lord),
        signLord: mk("signLord", "Sign lord", planetWord(p.sign_lord, t), "plain", pr.sign_lord),
        retrograde: mk("retrograde", "Retrograde", p.retrograde ? t("Retrograde") : t("Direct"), p.retrograde && !isNode ? "bad" : "plain", pr.retrograde),
        combust: mk(
          "combust", "Combustion", combustText, p.combust.is_combust ? "bad" : "plain", pr.combust,
          p.combust.applicable ? `${combustText}, ${p.combust.separation}° of ${p.combust.orb}°` : combustText,
        ),
        dignity: mk("dignity", "Dignity", dignityWord(p.dignity, t), dignityTone(p.dignity), pr.dignity),
        avastha: mk("avastha", "Avastha", p.avastha ? t(cap(p.avastha)) : t("Not assigned"), "plain", pr.avastha),
        karaka: mk(
          "karaka", "Chara karaka",
          p.karaka ? t(KARAKAS[p.karaka] ?? p.karaka) : t("Not assigned"), "plain", pr.karaka,
          p.karaka ? t(KARAKAS[p.karaka] ?? p.karaka) : t("Not assigned"),
        ),
        lordships: mk(
          "lordships", "Rules houses",
          p.lord_of_houses.length ? p.lord_of_houses.map((h) => `H${h}`).join(" ") : t("None"), "plain", pr.house_lordship,
          p.lord_of_houses.length ? p.lord_of_houses.join(", ") : t("None"),
        ),
      },
    };
  });
}

/* ------------------------------------------------------------ ashtakavarga */

export type CellTone = "high" | "low" | "mid";
export interface GridCell {
  sign: number;
  value: number;
  tone: CellTone;
  proof: ProofView;
}
export interface GridRow {
  id: string;
  label: string;
  isSarva: boolean;
  cells: GridCell[];
  total: number;
  totalProof: ProofView;
}
export interface AshtakavargaView {
  columns: Array<{ sign: number; abbr: string; name: string; house: number; isLagna: boolean }>;
  rows: GridRow[];
  strongest: Array<{ name: string; value: number }>;
  weakest: Array<{ name: string; value: number }>;
  grandTotal: number;
}

function ordinalWord(n: number, t: T): string {
  return t("house {n}", { n });
}

export function ashtakavargaView(data: AshtakavargaDepth, t: T): AshtakavargaView {
  const th = data.thresholds;
  const signOf: Record<string, number> = { lagna: data.lagna_sign_index };
  for (const b of data.bhinna) signOf[b.planet] = b.sign_of_planet;
  const toneOf = (v: number, hi: number, lo: number): CellTone => (v >= hi ? "high" : v <= lo ? "low" : "mid");
  const ashProof: Proof = data.proof;

  const columns = data.sign_names.map((name, sign) => ({
    sign, abbr: t(SIGN_ABBR[sign]!), name: t(name), house: ((sign - data.lagna_sign_index + 12) % 12) + 1, isLagna: sign === data.lagna_sign_index,
  }));

  const rows: GridRow[] = data.bhinna.map((b) => {
    const pname = planetWord(b.planet, t);
    return {
      id: b.planet,
      label: pname,
      isSarva: false,
      total: b.total,
      cells: b.bindus_by_sign.map((v, sign) => {
        const givers = b.contributors[sign] ?? [];
        const inputs = givers.map((c) => ({
          label: `${planetWord(c, t)} (${t(data.sign_names[signOf[c]!]!)})`,
          value: t("gives a bindu from {house}", { house: ordinalWord(((sign - signOf[c]! + 12) % 12) + 1, t) }),
        }));
        const rest = 8 - givers.length;
        return {
          sign,
          value: v,
          tone: toneOf(v, th.bhinna_high, th.bhinna_low),
          proof: {
            title: `${pname} ${t("in")} ${t(data.sign_names[sign]!)}`,
            value: `${v} ${t("bindus")}`,
            inputs: [...inputs, { label: t("Contributors giving none"), value: String(rest) }],
            rule: t(RULES.ashtakavarga!),
            source: t(ashProof.source),
          },
        };
      }),
      totalProof: {
        title: `${pname}: ${t("total bindus")}`,
        value: String(b.total),
        inputs: b.bindus_by_sign.map((v, sign) => ({ label: t(data.sign_names[sign]!), value: String(v) })),
        rule: t("The row total is the sum of its twelve signs. For each planet it is fixed by the classical tables: Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56, Venus 52, Saturn 39."),
        source: t(ashProof.source),
      },
    };
  });

  const sarvaCells: GridCell[] = data.sarva.map((v, sign) => ({
    sign,
    value: v,
    tone: toneOf(v, th.sarva_high, th.sarva_low),
    proof: {
      title: `${t("Sarvashtakavarga")}: ${t(data.sign_names[sign]!)}`,
      value: `${v} ${t("bindus")}`,
      inputs: data.bhinna.map((b) => ({ label: planetWord(b.planet, t), value: String(b.bindus_by_sign[sign]) })),
      rule: t("The Sarvashtakavarga of a sign is the sum of the seven planets' bindus in it. {high} or more is strong, {low} or fewer is weak, and the average is 28.", { high: th.sarva_high, low: th.sarva_low }),
      source: t(ashProof.source),
    },
  }));
  rows.push({
    id: "sarva",
    label: t("Sarva"),
    isSarva: true,
    cells: sarvaCells,
    total: data.sarva_total,
    totalProof: {
      title: `${t("Sarvashtakavarga")}: ${t("grand total")}`,
      value: String(data.sarva_total),
      inputs: data.bhinna.map((b) => ({ label: planetWord(b.planet, t), value: String(b.total) })),
      rule: t("The grand total is the sum of the seven row totals. In the classical scheme it is always 337."),
      source: t(ashProof.source),
    },
  });

  const ranked = data.sarva.map((value, sign) => ({ name: t(data.sign_names[sign]!), value })).sort((a, b) => b.value - a.value);
  return {
    columns,
    rows,
    strongest: ranked.filter((r) => r.value >= th.sarva_high).slice(0, 3),
    weakest: ranked.filter((r) => r.value <= th.sarva_low).reverse().slice(0, 3),
    grandTotal: data.sarva_total,
  };
}

/* ------------------------------------------------------------------ dashas */

export type DashaState = "past" | "current" | "future";
export interface DashaRow {
  key: string;
  level: number; // 0 maha, 1 antar, 2 pratyantar
  label: string;
  range: string;
  span: string;
  state: DashaState;
  hasChildren: boolean;
  open: boolean;
  proof: ProofView;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "14 Mar 2026" in the chart's own time zone, so dates match what the client was told. */
export function dashaDate(iso: string, timeZone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  try {
    const parts = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "numeric", year: "numeric", timeZone }).formatToParts(d);
    const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
    return `${get("day")} ${MONTHS[Number(get("month")) - 1]} ${get("year")}`;
  } catch {
    return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  }
}

export function spanText(years: number, t: T): string {
  if (years >= 1) {
    const whole = Math.floor(years);
    const months = Math.round((years - whole) * 12);
    if (months === 12) return t("{y} yr", { y: whole + 1 });
    return months ? t("{y} yr {m} mo", { y: whole, m: months }) : t("{y} yr", { y: whole });
  }
  const months = years * 12;
  if (months >= 1) return t("{m} mo", { m: Math.round(months * 10) / 10 });
  return t("{d} days", { d: Math.max(1, Math.round(years * 365.2425)) });
}

/** Re-mark which periods are running against `now`, whatever the stamp the data carried. */
export function applyAsOf(nodes: DashaNode[], now: Date): DashaNode[] {
  const ms = now.getTime();
  return nodes.map((n) => {
    const start = Date.parse(n.start);
    const end = Date.parse(n.end);
    return {
      ...n,
      state: start <= ms && ms < end ? "current" : end <= ms ? "past" : "future",
      children: n.children ? applyAsOf(n.children, now) : n.children,
    };
  });
}

export function runningKeys(nodes: DashaNode[]): string[] {
  const out: string[] = [];
  let level = nodes;
  let key = "";
  while (level.length) {
    const i = level.findIndex((n) => n.state === "current");
    if (i < 0) break;
    key = key ? `${key}.${i}` : String(i);
    out.push(key);
    level = level[i]!.children ?? [];
  }
  return out;
}

const LEVEL_WORD = ["Mahadasha", "Antardasha", "Pratyantardasha"] as const;

function dashaProof(node: DashaNode, parent: DashaNode | null, data: DashasDepth, t: T, tz?: string): ProofView {
  const lordKey = data.system === "yogini" ? node.name ?? node.planet : node.planet;
  const own = data.rule.years[lordKey] ?? data.rule.years[cap(lordKey)];
  const lordName = nodeLabel(node, data.system, t);
  const level = node.level === "mahadasha" ? 0 : node.level === "antardasha" ? 1 : 2;
  const inputs: ProofView["inputs"] = [
    { label: t("Level"), value: t(LEVEL_WORD[level]!) },
    { label: t("Lord"), value: lordName },
    { label: t("Lord's years in the cycle"), value: String(own ?? "") },
    { label: t("Cycle length (years)"), value: String(data.rule.total_years) },
  ];
  let rule: string;
  if (parent) {
    inputs.push({ label: t("Parent period"), value: `${nodeLabel(parent, data.system, t)} ${spanText(parent.years, t)}` });
    inputs.push({ label: t("Length"), value: `${parent.years} × ${own} ÷ ${data.rule.total_years} = ${node.years} ${t("years")}` });
    rule = t(RULES[data.rule.id]!);
  } else {
    inputs.push({ label: t("Balance of the first period at birth (years)"), value: String(data.balance_years) });
    inputs.push({ label: t("Birth nakshatra"), value: tName(t, data.birth.nakshatra) });
    rule = t(RULES[data.rule.id]!);
  }
  inputs.push({ label: t("Starts"), value: dashaDate(node.start, tz) });
  inputs.push({ label: t("Ends"), value: dashaDate(node.end, tz) });
  inputs.push({ label: t("Year length (days)"), value: String(data.rule.year_length_days) });
  return {
    title: `${t(LEVEL_WORD[level]!)}: ${lordName}`,
    value: `${dashaDate(node.start, tz)} ${t("to")} ${dashaDate(node.end, tz)}`,
    inputs,
    rule,
    source: t(data.rule.source),
  };
}

export function nodeLabel(node: DashaNode, system: string, t: T): string {
  if (system === "yogini" && node.name) return `${t(node.name)} (${planetWord(node.planet, t)})`;
  return planetWord(node.planet, t);
}

/** Flatten the tree into the rows currently visible given the set of expanded keys. */
export function dashaRows(data: DashasDepth, expanded: ReadonlySet<string>, t: T, timeZone?: string): DashaRow[] {
  const rows: DashaRow[] = [];
  const walk = (nodes: DashaNode[], parent: DashaNode | null, prefix: string, level: number) => {
    nodes.forEach((n, i) => {
      const key = prefix ? `${prefix}.${i}` : String(i);
      const hasChildren = Boolean(n.children?.length);
      const open = hasChildren && expanded.has(key);
      rows.push({
        key,
        level,
        label: nodeLabel(n, data.system, t),
        range: `${dashaDate(n.start, timeZone)} ${t("to")} ${dashaDate(n.end, timeZone)}`,
        span: spanText(n.years, t),
        state: n.state,
        hasChildren,
        open,
        proof: dashaProof(n, parent, data, t, timeZone),
      });
      if (open) walk(n.children!, n, key, level + 1);
    });
  };
  walk(data.mahadashas, null, "", 0);
  return rows;
}

export function currentLine(data: DashasDepth, t: T): string {
  return data.current.map((c) => (data.system === "yogini" && c.name ? t(c.name) : planetWord(c.planet, t))).join(" / ");
}

export { PLANET_ABBR };
