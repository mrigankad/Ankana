import { signCount } from "./aspects";
import { dignityOf, type Dignity, type Planet } from "./dignities";
import { SIGN_LORDS, SIGN_NAMES } from "./zodiac";

export type YogaCategory =
  | "raj"
  | "dhan"
  | "pancha-mahapurusha"
  | "lunar"
  | "solar"
  | "dosha"
  | "other";

export interface YogaResult {
  key: string;
  name: string;
  present: boolean;
  description: string;
  evidence: string[];
  category: YogaCategory;
}

export interface YogaChartInput {
  /** Sidereal longitudes for all nine grahas. */
  longitudes: Record<Planet, number>;
  /** Sign index (0-11) per graha. */
  signs: Record<Planet, number>;
  ascendantSign: number;
  /** Dignity per graha. */
  dignities: Record<Planet, Dignity>;
  /** Planet that rules each house (1-12). houseLords[0] = lord of 1st house. */
  houseLords: Planet[];
}

// ── helpers ────────────────────────────────────────────────────────

const KENDRA_COUNTS = [1, 4, 7, 10];
const TRIKONA_COUNTS = [1, 5, 9];
const DUSTHANA_COUNTS = [6, 8, 12];

const NATURAL_BENEFICS: Planet[] = ["jupiter", "venus", "mercury", "moon"];
const SEVEN_PLANETS: Planet[] = [
  "sun",
  "moon",
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
];
const STRONG_DIGNITIES: Dignity[] = ["exalted", "moolatrikona", "own"];

function signName(index: number): string {
  return SIGN_NAMES[index];
}

function placement(planet: Planet, input: YogaChartInput): string {
  return `${planet} in ${signName(input.signs[planet])} (house ${signCount(input.ascendantSign, input.signs[planet])})`;
}

function houseNum(ascSign: number, bodySign: number): number {
  return signCount(ascSign, bodySign);
}

function houseFromMoon(moonSign: number, bodySign: number): number {
  return signCount(moonSign, bodySign);
}

/** Which planet is the lord of house N (1-indexed)? */
function lordOf(input: YogaChartInput, house: number): Planet {
  return input.houseLords[house - 1];
}

/** Which house (1-12) does this planet occupy? */
function houseOfPlanet(input: YogaChartInput, planet: Planet): number {
  return houseNum(input.ascendantSign, input.signs[planet]);
}

// ── existing detectors ─────────────────────────────────────────────

function detectGajakesari(input: YogaChartInput): YogaResult {
  const count = signCount(input.signs.moon, input.signs.jupiter);
  const present = KENDRA_COUNTS.includes(count);
  return {
    key: "gajakesari",
    name: "Gajakesari Yoga",
    present,
    description:
      "Jupiter in a kendra (1st, 4th, 7th, or 10th) from the Moon, associated with wisdom, reputation, and lasting prosperity.",
    evidence: [
      placement("moon", input),
      placement("jupiter", input),
      `Jupiter is ${count} signs from the Moon (kendra positions: 1, 4, 7, 10).`,
    ],
    category: "raj",
  };
}

function detectBudhaditya(input: YogaChartInput): YogaResult {
  const present = input.signs.sun === input.signs.mercury;
  return {
    key: "budhaditya",
    name: "Budhaditya Yoga",
    present,
    description:
      "Sun and Mercury conjunct in one sign, associated with intelligence, communication skill, and administrative ability.",
    evidence: [placement("sun", input), placement("mercury", input)],
    category: "raj",
  };
}

function detectChandraMangal(input: YogaChartInput): YogaResult {
  const count = signCount(input.signs.moon, input.signs.mars);
  const present = count === 1 || count === 7;
  return {
    key: "chandra-mangal",
    name: "Chandra-Mangal Yoga",
    present,
    description:
      "Moon and Mars in conjunction or mutual opposition, associated with earning drive and material enterprise.",
    evidence: [
      placement("moon", input),
      placement("mars", input),
      `Mars is ${count} signs from the Moon.`,
    ],
    category: "dhan",
  };
}

const MAHAPURUSHA: Array<{ key: string; name: string; planet: Planet }> = [
  { key: "ruchaka", name: "Ruchaka Yoga (Mars Mahapurusha)", planet: "mars" },
  { key: "bhadra", name: "Bhadra Yoga (Mercury Mahapurusha)", planet: "mercury" },
  { key: "hamsa", name: "Hamsa Yoga (Jupiter Mahapurusha)", planet: "jupiter" },
  { key: "malavya", name: "Malavya Yoga (Venus Mahapurusha)", planet: "venus" },
  { key: "sasa", name: "Sasa Yoga (Saturn Mahapurusha)", planet: "saturn" },
];

function detectMahapurusha(input: YogaChartInput): YogaResult[] {
  return MAHAPURUSHA.map(({ key, name, planet }) => {
    const houseCount = signCount(input.ascendantSign, input.signs[planet]);
    const dignity = dignityOf(planet, input.longitudes[planet]);
    const present =
      KENDRA_COUNTS.includes(houseCount) && STRONG_DIGNITIES.includes(dignity);

    return {
      key,
      name,
      present,
      description: `${planet} in its own or exaltation sign placed in a kendra from the lagna.`,
      evidence: [
        placement(planet, input),
        `${planet} dignity: ${dignity}.`,
        `${planet} occupies house ${houseCount} from the lagna.`,
      ],
      category: "pancha-mahapurusha" as YogaCategory,
    };
  });
}

function detectKemadruma(input: YogaChartInput): YogaResult {
  const moonSign = input.signs.moon;
  const flanks = [(moonSign + 1) % 12, (moonSign + 11) % 12];
  const supporters: Planet[] = ["mercury", "venus", "mars", "jupiter", "saturn"];

  const support = supporters.filter(
    (planet) =>
      flanks.includes(input.signs[planet]) || input.signs[planet] === moonSign,
  );

  const present = support.length === 0;
  return {
    key: "kemadruma",
    name: "Kemadruma Yoga",
    present,
    description:
      "No planet (excluding Sun, Rahu, Ketu) conjoins the Moon or occupies the 2nd or 12th from it; classically linked to isolation and fluctuating fortunes.",
    evidence: present
      ? [
          placement("moon", input),
          "No supporting planet in the 2nd or 12th from the Moon or with the Moon.",
        ]
      : [
          placement("moon", input),
          `Supporting planets around the Moon: ${support.join(", ")}.`,
        ],
    category: "dosha",
  };
}

function detectKaalSarp(input: YogaChartInput): YogaResult {
  const rahu = input.longitudes.rahu;
  const ketu = input.longitudes.ketu;
  const bodies: Planet[] = [
    "sun",
    "moon",
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
  ];

  const sideOf = (lon: number): number => {
    const fromRahu = (lon - rahu + 360) % 360;
    const axisSpan = (ketu - rahu + 360) % 360;
    return fromRahu < axisSpan ? 0 : 1;
  };

  const sides = new Set(bodies.map((planet) => sideOf(input.longitudes[planet])));
  const present = sides.size === 1;

  return {
    key: "kaal-sarp",
    name: "Kaal Sarp Yoga",
    present,
    description:
      "All seven classical planets hemmed on one side of the Rahu-Ketu axis; traditionally read as concentrated karmic intensity.",
    evidence: [
      `Rahu at ${rahu.toFixed(2)} deg, Ketu at ${ketu.toFixed(2)} deg.`,
      present
        ? "All seven classical planets fall on one side of the nodal axis."
        : "Planets occupy both sides of the nodal axis.",
    ],
    category: "dosha",
  };
}

// ── new lunar yogas ────────────────────────────────────────────────

/** Sunapha: any planet except Sun/Rahu/Ketu in the 2nd from Moon. */
function detectSunapha(input: YogaChartInput): YogaResult {
  const second = (input.signs.moon + 1) % 12;
  const supporters: Planet[] = ["mercury", "venus", "mars", "jupiter", "saturn"];
  const found = supporters.filter((p) => input.signs[p] === second);
  return {
    key: "sunapha",
    name: "Sunapha Yoga",
    present: found.length > 0,
    description:
      "A planet in the 2nd house from the Moon; indicates self-made wealth, good intellect, and prosperity through one's own efforts.",
    evidence: [
      placement("moon", input),
      found.length > 0
        ? `${found.join(", ")} in the 2nd from Moon (${signName(second)}).`
        : "No qualifying planet in the 2nd from Moon.",
    ],
    category: "lunar",
  };
}

/** Anapha: any planet except Sun/Rahu/Ketu in the 12th from Moon. */
function detectAnapha(input: YogaChartInput): YogaResult {
  const twelfth = (input.signs.moon + 11) % 12;
  const supporters: Planet[] = ["mercury", "venus", "mars", "jupiter", "saturn"];
  const found = supporters.filter((p) => input.signs[p] === twelfth);
  return {
    key: "anapha",
    name: "Anapha Yoga",
    present: found.length > 0,
    description:
      "A planet in the 12th house from the Moon; indicates good health, virtue, and comfortable living.",
    evidence: [
      placement("moon", input),
      found.length > 0
        ? `${found.join(", ")} in the 12th from Moon (${signName(twelfth)}).`
        : "No qualifying planet in the 12th from Moon.",
    ],
    category: "lunar",
  };
}

/** Durudhara: planets in both the 2nd and 12th from Moon. */
function detectDurudhara(input: YogaChartInput): YogaResult {
  const second = (input.signs.moon + 1) % 12;
  const twelfth = (input.signs.moon + 11) % 12;
  const supporters: Planet[] = ["mercury", "venus", "mars", "jupiter", "saturn"];
  const in2nd = supporters.filter((p) => input.signs[p] === second);
  const in12th = supporters.filter((p) => input.signs[p] === twelfth);
  const present = in2nd.length > 0 && in12th.length > 0;
  return {
    key: "durudhara",
    name: "Durudhara Yoga",
    present,
    description:
      "Planets flanking the Moon on both sides (2nd and 12th from it); indicates wealth, generosity, and a life of comforts.",
    evidence: [
      placement("moon", input),
      in2nd.length > 0
        ? `In 2nd from Moon: ${in2nd.join(", ")}.`
        : "No planet in 2nd from Moon.",
      in12th.length > 0
        ? `In 12th from Moon: ${in12th.join(", ")}.`
        : "No planet in 12th from Moon.",
    ],
    category: "lunar",
  };
}

// ── solar yogas ────────────────────────────────────────────────────

/** Voshi/Veshi: planet in the 2nd from Sun (excluding Moon/Rahu/Ketu). */
function detectVoshi(input: YogaChartInput): YogaResult {
  const second = (input.signs.sun + 1) % 12;
  const candidates: Planet[] = ["mercury", "venus", "mars", "jupiter", "saturn"];
  const found = candidates.filter((p) => input.signs[p] === second);
  return {
    key: "voshi",
    name: "Voshi Yoga",
    present: found.length > 0,
    description:
      "A planet in the 2nd house from the Sun; indicates eloquence, learning, and charitable disposition.",
    evidence: [
      placement("sun", input),
      found.length > 0
        ? `${found.join(", ")} in the 2nd from Sun (${signName(second)}).`
        : "No qualifying planet in the 2nd from Sun.",
    ],
    category: "solar",
  };
}

/** Veshi: planet in the 12th from Sun (excluding Moon/Rahu/Ketu). */
function detectVeshi(input: YogaChartInput): YogaResult {
  const twelfth = (input.signs.sun + 11) % 12;
  const candidates: Planet[] = ["mercury", "venus", "mars", "jupiter", "saturn"];
  const found = candidates.filter((p) => input.signs[p] === twelfth);
  return {
    key: "veshi",
    name: "Veshi Yoga",
    present: found.length > 0,
    description:
      "A planet in the 12th house from the Sun; indicates authority, power, and steady temperament.",
    evidence: [
      placement("sun", input),
      found.length > 0
        ? `${found.join(", ")} in the 12th from Sun (${signName(twelfth)}).`
        : "No qualifying planet in the 12th from Sun.",
    ],
    category: "solar",
  };
}

/** Ubhayachari: planets in both 2nd and 12th from Sun. */
function detectUbhayachari(input: YogaChartInput): YogaResult {
  const second = (input.signs.sun + 1) % 12;
  const twelfth = (input.signs.sun + 11) % 12;
  const candidates: Planet[] = ["mercury", "venus", "mars", "jupiter", "saturn"];
  const in2nd = candidates.filter((p) => input.signs[p] === second);
  const in12th = candidates.filter((p) => input.signs[p] === twelfth);
  const present = in2nd.length > 0 && in12th.length > 0;
  return {
    key: "ubhayachari",
    name: "Ubhayachari Yoga",
    present,
    description:
      "Planets flanking the Sun on both sides (2nd and 12th); indicates a powerful, kingly personality with commanding presence.",
    evidence: [
      placement("sun", input),
      in2nd.length > 0
        ? `In 2nd from Sun: ${in2nd.join(", ")}.`
        : "No planet in 2nd from Sun.",
      in12th.length > 0
        ? `In 12th from Sun: ${in12th.join(", ")}.`
        : "No planet in 12th from Sun.",
    ],
    category: "solar",
  };
}

// ── benefic yogas ──────────────────────────────────────────────────

/** Adhi Yoga: natural benefics in 6th, 7th, and/or 8th from Moon. */
function detectAdhi(input: YogaChartInput): YogaResult {
  const benefics: Planet[] = ["mercury", "venus", "jupiter"];
  const targets = [6, 7, 8];
  const found = benefics.filter((p) =>
    targets.includes(houseFromMoon(input.signs.moon, input.signs[p])),
  );
  // Classical Adhi Yoga requires benefics in all three (6, 7, 8); the
  // weaker variant requires at least two.  We flag at ≥2 for coverage.
  const present = found.length >= 2;
  return {
    key: "adhi",
    name: "Adhi Yoga",
    present,
    description:
      "Natural benefics occupy the 6th, 7th, and 8th from the Moon; indicates high status, authority, and victory over adversaries.",
    evidence: [
      placement("moon", input),
      ...found.map(
        (p) =>
          `${p} in house ${houseFromMoon(input.signs.moon, input.signs[p])} from Moon.`,
      ),
      found.length < 2
        ? "Insufficient benefics in 6th/7th/8th from Moon."
        : `${found.length} benefic(s) in the 6th/7th/8th houses from Moon.`,
    ],
    category: "raj",
  };
}

/** Amala Yoga: a natural benefic in the 10th from lagna or Moon. */
function detectAmala(input: YogaChartInput): YogaResult {
  const benefics: Planet[] = ["mercury", "venus", "jupiter"];
  const fromLagna = benefics.filter(
    (p) => houseOfPlanet(input, p) === 10,
  );
  const fromMoon = benefics.filter(
    (p) => houseFromMoon(input.signs.moon, input.signs[p]) === 10,
  );
  const all = [...new Set([...fromLagna, ...fromMoon])];
  const present = all.length > 0;
  return {
    key: "amala",
    name: "Amala Yoga",
    present,
    description:
      "A natural benefic in the 10th house from lagna or Moon; indicates an unblemished reputation, philanthropy, and lasting fame.",
    evidence: [
      ...fromLagna.map((p) => `${p} in the 10th from lagna.`),
      ...fromMoon.map((p) => `${p} in the 10th from Moon.`),
      !present ? "No natural benefic in the 10th house." : "",
    ].filter(Boolean),
    category: "raj",
  };
}

// ── doshas ──────────────────────────────────────────────────────────

/** Manglik/Kuja Dosha: Mars in houses 1, 2, 4, 7, 8, or 12 from lagna. */
function detectManglik(input: YogaChartInput): YogaResult {
  const marsHouse = houseOfPlanet(input, "mars");
  const manglikHouses = [1, 2, 4, 7, 8, 12];
  const present = manglikHouses.includes(marsHouse);

  // Basic cancellation conditions
  const cancellations: string[] = [];
  if (present) {
    // Jupiter aspects Mars → cancellation
    const jupMarsCount = signCount(input.signs.jupiter, input.signs.mars);
    if ([1, 5, 7, 9].includes(jupMarsCount)) {
      cancellations.push("Jupiter aspects or conjoins Mars.");
    }
    // Mars in own/exalted sign → cancellation
    if (STRONG_DIGNITIES.includes(input.dignities.mars)) {
      cancellations.push(`Mars is ${input.dignities.mars}, reducing the dosha effect.`);
    }
  }

  return {
    key: "manglik",
    name: "Manglik Dosha (Kuja Dosha)",
    present,
    description:
      "Mars in houses 1, 2, 4, 7, 8, or 12 from the lagna; traditionally assessed for marital compatibility. Cancellation conditions may mitigate the effect.",
    evidence: [
      placement("mars", input),
      `Mars occupies house ${marsHouse} from lagna.`,
      ...cancellations,
    ],
    category: "dosha",
  };
}

/** Guru Chandal Yoga: Jupiter conjunct Rahu in the same sign. */
function detectGuruChandal(input: YogaChartInput): YogaResult {
  const present = input.signs.jupiter === input.signs.rahu;
  return {
    key: "guru-chandal",
    name: "Guru Chandal Yoga",
    present,
    description:
      "Jupiter conjoined with Rahu in the same sign; may indicate unconventional wisdom, disrupted advice from teachers, or unorthodox spiritual leanings.",
    evidence: [placement("jupiter", input), placement("rahu", input)],
    category: "dosha",
  };
}

/** Pitra Dosha: Sun conjunct Rahu or Ketu. */
function detectPitraDosha(input: YogaChartInput): YogaResult {
  const sunWithRahu = input.signs.sun === input.signs.rahu;
  const sunWithKetu = input.signs.sun === input.signs.ketu;
  const present = sunWithRahu || sunWithKetu;
  return {
    key: "pitra-dosha",
    name: "Pitra Dosha",
    present,
    description:
      "Sun conjunct Rahu or Ketu; indicates ancestral karmic debts that may manifest as obstacles or delayed results in life.",
    evidence: [
      placement("sun", input),
      sunWithRahu ? placement("rahu", input) : "",
      sunWithKetu ? placement("ketu", input) : "",
      present
        ? `Sun conjoined with ${sunWithRahu ? "Rahu" : "Ketu"} in ${signName(input.signs.sun)}.`
        : "Sun is not conjunct either node.",
    ].filter(Boolean),
    category: "dosha",
  };
}

// ── raj yogas (house-lord based) ────────────────────────────────────

/** Raj Yoga: lord of a kendra conjunct with lord of a trikona. */
function detectRajYogas(input: YogaChartInput): YogaResult {
  const kendraHouses = [1, 4, 7, 10];
  const trikonaHouses = [1, 5, 9]; // 1st is both kendra and trikona

  const pairs: Array<{ kendra: number; trikona: number; planet: string }> = [];

  for (const kh of kendraHouses) {
    for (const th of trikonaHouses) {
      if (kh === th) continue; // skip same house
      const kLord = lordOf(input, kh);
      const tLord = lordOf(input, th);
      if (kLord === tLord) {
        // Same planet lords both a kendra and a trikona - Raj Yoga by itself
        pairs.push({ kendra: kh, trikona: th, planet: kLord });
      } else if (input.signs[kLord] === input.signs[tLord]) {
        // Two different lords conjunct
        pairs.push({ kendra: kh, trikona: th, planet: `${kLord}+${tLord}` });
      }
    }
  }

  return {
    key: "raj-yoga",
    name: "Raj Yoga (Kendra-Trikona)",
    present: pairs.length > 0,
    description:
      "Lord of a kendra and lord of a trikona conjoined or the same planet rules both; one of the most auspicious combinations indicating power, success, and recognition.",
    evidence:
      pairs.length > 0
        ? pairs.map(
            (p) =>
              `Lord of ${p.kendra}th (kendra) and lord of ${p.trikona}th (trikona): ${p.planet}.`,
          )
        : ["No kendra-trikona lord conjunction found."],
    category: "raj",
  };
}

/** Dhana Yoga: lord of 2nd conjoined with or aspected by lord of 11th. */
function detectDhanaYoga(input: YogaChartInput): YogaResult {
  const lord2 = lordOf(input, 2);
  const lord11 = lordOf(input, 11);

  // Conjunction
  const conjunct = input.signs[lord2] === input.signs[lord11];

  // Mutual aspect (simplified: same sign or 7th from each other)
  const count = signCount(input.signs[lord2], input.signs[lord11]);
  const aspect = count === 7;

  const present = lord2 !== lord11 && (conjunct || aspect);

  return {
    key: "dhana-yoga",
    name: "Dhana Yoga",
    present,
    description:
      "Lord of the 2nd house conjoined with or in mutual aspect with the lord of the 11th; indicates wealth accumulation and strong financial gains.",
    evidence: [
      `Lord of 2nd: ${lord2} (${placement(lord2, input)}).`,
      `Lord of 11th: ${lord11} (${placement(lord11, input)}).`,
      conjunct
        ? "Lords of 2nd and 11th are conjunct."
        : aspect
          ? "Lords of 2nd and 11th are in mutual 7th aspect."
          : "No conjunction or mutual aspect between lords of 2nd and 11th.",
    ],
    category: "dhan",
  };
}

/** Vipreet Raj Yoga: lord of 6th in 8th/12th, lord of 8th in 6th/12th, or lord of 12th in 6th/8th. */
function detectVipreetRaj(input: YogaChartInput): YogaResult {
  const dusthanas: Array<{ house: number; others: number[] }> = [
    { house: 6, others: [8, 12] },
    { house: 8, others: [6, 12] },
    { house: 12, others: [6, 8] },
  ];

  const vipreetNames = ["Harsha", "Sarala", "Vimala"];
  const matches: string[] = [];

  for (let i = 0; i < dusthanas.length; i++) {
    const d = dusthanas[i];
    const lord = lordOf(input, d.house);
    const lordHouse = houseOfPlanet(input, lord);
    if (d.others.includes(lordHouse)) {
      matches.push(
        `${vipreetNames[i]} Yoga: lord of ${d.house}th (${lord}) placed in house ${lordHouse}.`,
      );
    }
  }

  return {
    key: "vipreet-raj",
    name: "Vipreet Raj Yoga",
    present: matches.length > 0,
    description:
      "Lord of a dusthana (6th, 8th, or 12th) placed in another dusthana; turns adversity into advantage - obstacles become sources of unexpected gain.",
    evidence:
      matches.length > 0
        ? matches
        : ["No dusthana lord is placed in another dusthana."],
    category: "raj",
  };
}

// ── neecha bhanga ──────────────────────────────────────────────────

/** Neecha Bhanga Raj Yoga: debilitated planet with cancellation conditions. */
function detectNeechaBhanga(input: YogaChartInput): YogaResult {
  const debilitated = SEVEN_PLANETS.filter(
    (p) => input.dignities[p] === "debilitated",
  );

  const cancelled: string[] = [];

  for (const planet of debilitated) {
    const sign = input.signs[planet];
    const dispositor = SIGN_LORDS[sign] as Planet;

    // Cancellation 1: dispositor of debilitated planet is in a kendra from lagna
    const dispHouse = houseOfPlanet(input, dispositor);
    if (KENDRA_COUNTS.includes(dispHouse)) {
      cancelled.push(
        `${planet} is debilitated; its dispositor ${dispositor} is in kendra (house ${dispHouse}).`,
      );
    }

    // Cancellation 2: dispositor of debilitated planet is exalted
    if (STRONG_DIGNITIES.includes(input.dignities[dispositor])) {
      cancelled.push(
        `${planet} is debilitated; its dispositor ${dispositor} is ${input.dignities[dispositor]}.`,
      );
    }
  }

  return {
    key: "neecha-bhanga",
    name: "Neecha Bhanga Raj Yoga",
    present: cancelled.length > 0,
    description:
      "A debilitated planet whose weakness is cancelled by specific conditions (strong dispositor, etc.); transforms a difficult placement into a source of great strength.",
    evidence:
      cancelled.length > 0
        ? cancelled
        : debilitated.length > 0
          ? [`Debilitated planet(s): ${debilitated.join(", ")} but no cancellation conditions met.`]
          : ["No debilitated planet found."],
    category: "raj",
  };
}

// ── special combination yogas ──────────────────────────────────────

/** Saraswati Yoga: Jupiter, Venus, Mercury all in kendras, trikonas, or 2nd house. */
function detectSaraswati(input: YogaChartInput): YogaResult {
  const qualifying = [1, 2, 4, 5, 7, 9, 10]; // kendras + trikonas + 2nd
  const targets: Planet[] = ["jupiter", "venus", "mercury"];
  const inQualifying = targets.filter((p) =>
    qualifying.includes(houseOfPlanet(input, p)),
  );
  // All three must qualify, and Jupiter should be strong (at least friend dignity)
  const jupiterStrong = !["debilitated", "enemy"].includes(input.dignities.jupiter);
  const present = inQualifying.length === 3 && jupiterStrong;

  return {
    key: "saraswati",
    name: "Saraswati Yoga",
    present,
    description:
      "Jupiter, Venus, and Mercury all in kendras, trikonas, or the 2nd house with Jupiter dignified; confers learning, eloquence, mastery of arts and sciences.",
    evidence: [
      ...targets.map((p) => `${p} in house ${houseOfPlanet(input, p)} (${input.dignities[p]}).`),
      jupiterStrong
        ? "Jupiter is dignified."
        : "Jupiter is weak (debilitated or in enemy sign).",
    ],
    category: "raj",
  };
}

/** Lakshmi Yoga: lord of 9th in a kendra and strong (own/exalted/moolatrikona). */
function detectLakshmi(input: YogaChartInput): YogaResult {
  const lord9 = lordOf(input, 9);
  const lord9House = houseOfPlanet(input, lord9);
  const isStrong = STRONG_DIGNITIES.includes(input.dignities[lord9]);
  const inKendra = KENDRA_COUNTS.includes(lord9House);
  const present = inKendra && isStrong;

  return {
    key: "lakshmi",
    name: "Lakshmi Yoga",
    present,
    description:
      "Lord of the 9th house placed in a kendra in its own, exalted, or moolatrikona sign; indicates immense wealth, fortune, and divine grace.",
    evidence: [
      `Lord of 9th: ${lord9} (${placement(lord9, input)}).`,
      `Dignity: ${input.dignities[lord9]}. House: ${lord9House}.`,
      present
        ? "Lord of 9th is strong in a kendra."
        : `Lord of 9th is ${isStrong ? "strong but not in a kendra" : inKendra ? "in a kendra but not strong" : "neither in a kendra nor strong"}.`,
    ],
    category: "dhan",
  };
}

/** Grahan Yoga: Sun or Moon conjunct Rahu or Ketu. */
function detectGrahan(input: YogaChartInput): YogaResult {
  const sunRahu = input.signs.sun === input.signs.rahu;
  const sunKetu = input.signs.sun === input.signs.ketu;
  const moonRahu = input.signs.moon === input.signs.rahu;
  const moonKetu = input.signs.moon === input.signs.ketu;
  const present = sunRahu || sunKetu || moonRahu || moonKetu;

  const eclipses: string[] = [];
  if (sunRahu) eclipses.push("Sun conjunct Rahu (solar eclipse pattern).");
  if (sunKetu) eclipses.push("Sun conjunct Ketu (solar eclipse pattern).");
  if (moonRahu) eclipses.push("Moon conjunct Rahu (lunar eclipse pattern).");
  if (moonKetu) eclipses.push("Moon conjunct Ketu (lunar eclipse pattern).");

  return {
    key: "grahan",
    name: "Grahan Yoga",
    present,
    description:
      "A luminary (Sun or Moon) conjoined with a node (Rahu or Ketu); indicates karmic intensity around the luminary's significations - identity (Sun) or mind/emotions (Moon).",
    evidence: present
      ? eclipses
      : ["Neither luminary is conjunct a node."],
    category: "dosha",
  };
}

// ── main export ────────────────────────────────────────────────────

export function detectYogas(input: YogaChartInput): YogaResult[] {
  return [
    // Raj yogas
    detectGajakesari(input),
    detectBudhaditya(input),
    detectRajYogas(input),
    detectVipreetRaj(input),
    detectNeechaBhanga(input),
    detectAdhi(input),
    detectAmala(input),
    detectSaraswati(input),
    detectLakshmi(input),

    // Dhan yogas
    detectChandraMangal(input),
    detectDhanaYoga(input),

    // Pancha Mahapurusha
    ...detectMahapurusha(input),

    // Lunar yogas
    detectSunapha(input),
    detectAnapha(input),
    detectDurudhara(input),

    // Solar yogas
    detectVoshi(input),
    detectVeshi(input),
    detectUbhayachari(input),

    // Doshas
    detectManglik(input),
    detectGuruChandal(input),
    detectPitraDosha(input),
    detectGrahan(input),
    detectKemadruma(input),
    detectKaalSarp(input),
  ];
}
