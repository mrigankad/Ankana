import type { Domain, Rule } from "../types";

export const PACK_VERSION = "vedic-predictions@1.0.0";

/** Classical house significations per life domain. */
const DOMAIN_HOUSES: Record<Domain, number[]> = {
  career: [10, 6],
  wealth: [2, 11],
  marriage: [7],
  health: [1, 6, 8],
  education: [4, 5],
  travel: [3, 9, 12],
  spiritual: [5, 9, 12],
};

const DOMAIN_LABEL: Record<Domain, string> = {
  career: "career and profession",
  wealth: "wealth and income",
  marriage: "marriage and partnership",
  health: "health and vitality",
  education: "education and learning",
  travel: "travel and relocation",
  spiritual: "spiritual growth",
};

const DUSTHANA = [6, 8, 12];
const KENDRA_TRIKONA = [1, 4, 5, 7, 9, 10];

function domainRules(domain: Domain): Rule[] {
  const houses = DOMAIN_HOUSES[domain];
  const label = DOMAIN_LABEL[domain];

  return [
    {
      id: `${domain}-lord-strong-dasha`,
      packVersion: PACK_VERSION,
      domain,
      when: [
        { kind: "dashaLordOwnsHouse", houses },
        { kind: "dashaLordStrengthRatioAtLeast", ratio: 1 },
      ],
      weight: 3,
      effect: "supportive",
      text: `The {level} lord {lord} rules the ${label} houses and carries above-required Shadbala, activating gains in ${label}.`,
      source: "BPHS dasha-phala adhyaya (period results follow lordship and strength)",
    },
    {
      id: `${domain}-lord-weak-dasha`,
      packVersion: PACK_VERSION,
      domain,
      when: [
        { kind: "dashaLordOwnsHouse", houses },
        { kind: "dashaLordStrengthRatioBelow", ratio: 0.8 },
      ],
      weight: 2,
      effect: "challenging",
      text: `The {level} lord {lord} rules the ${label} houses but is weak in Shadbala; ${label} matters need deliberate effort in this window.`,
      source: "BPHS dasha-phala adhyaya",
    },
    {
      id: `${domain}-lord-in-domain-house`,
      packVersion: PACK_VERSION,
      domain,
      when: [
        { kind: "dashaLordInHouse", houses },
        { kind: "dashaLordDignity", dignities: ["exalted", "moolatrikona", "own", "friend"] },
      ],
      weight: 2,
      effect: "supportive",
      text: `The {level} lord {lord} sits well-placed in a ${label} house, giving direct results in ${label}.`,
      source: "Phaladeepika (placement of period lords)",
    },
    {
      id: `${domain}-lord-dusthana-weak`,
      packVersion: PACK_VERSION,
      domain,
      when: [
        { kind: "dashaLordOwnsHouse", houses },
        { kind: "dashaLordInHouse", houses: DUSTHANA },
        { kind: "dashaLordStrengthRatioBelow", ratio: 1 },
      ],
      weight: 2,
      effect: "challenging",
      text: `The {level} lord {lord} governs ${label} but operates from a dusthana without compensating strength, bringing obstacles first.`,
      source: "BPHS (dusthana placements of period lords)",
    },
  ];
}

const SPECIAL_RULES: Rule[] = [
  {
    id: "career-exalted-lord-kendra",
    packVersion: PACK_VERSION,
    domain: "career",
    when: [
      { kind: "dashaLordDignity", dignities: ["exalted"] },
      { kind: "dashaLordInHouse", houses: KENDRA_TRIKONA },
    ],
    weight: 3,
    effect: "supportive",
    text: "An exalted {level} lord {lord} in a kendra or trikona marks a period of visible rise and recognition.",
    source: "Phaladeepika",
  },
  {
    id: "wealth-gajakesari-jupiter",
    packVersion: PACK_VERSION,
    domain: "wealth",
    when: [
      { kind: "yogaPresent", keys: ["gajakesari"] },
      { kind: "dashaLordIs", planets: ["jupiter"] },
    ],
    weight: 3,
    effect: "supportive",
    text: "Gajakesari yoga activates during Jupiter's {level}: reputation-led gains and protection of wealth.",
    source: "BPHS yoga-phala (yogas fructify in their karakas' periods)",
  },
  {
    id: "marriage-venus-dasha-strong",
    packVersion: PACK_VERSION,
    domain: "marriage",
    when: [
      { kind: "dashaLordIs", planets: ["venus"] },
      { kind: "dashaLordStrengthRatioAtLeast", ratio: 1 },
    ],
    weight: 2,
    effect: "supportive",
    text: "A strong Venus {level} favors partnership, engagement, and harmony in existing bonds.",
    source: "Venus as karaka of marriage (BPHS karakadhyaya)",
  },
  {
    id: "health-sade-sati-window",
    packVersion: PACK_VERSION,
    domain: "health",
    when: [{ kind: "sadeSatiActiveAtWindow" }],
    weight: 2,
    effect: "challenging",
    text: "Sade sati runs through this window; guard energy, sleep, and routines - steady discipline converts pressure into endurance.",
    source: "Saturn transit tradition (sade sati)",
  },
  {
    id: "health-combust-lord",
    packVersion: PACK_VERSION,
    domain: "health",
    when: [{ kind: "dashaLordCombust" }],
    weight: 1,
    effect: "challenging",
    text: "The {level} lord {lord} is combust in the natal chart, thinning its protective results; avoid overextension.",
    source: "Combustion doctrine (asta graha)",
  },
  {
    id: "spiritual-ketu-dasha",
    packVersion: PACK_VERSION,
    domain: "spiritual",
    when: [{ kind: "dashaLordIs", planets: ["ketu"] }],
    weight: 1,
    effect: "supportive",
    text: "Ketu's {level} turns attention inward: contemplative practice and detachment deepen naturally.",
    source: "Ketu as moksha-karaka",
  },
  {
    id: "travel-rahu-dasha",
    packVersion: PACK_VERSION,
    domain: "travel",
    when: [{ kind: "dashaLordIs", planets: ["rahu"] }],
    weight: 1,
    effect: "supportive",
    text: "Rahu's {level} favors unconventional moves - foreign lands, new environments, and boundary-crossing opportunities.",
    source: "Rahu as videsha-karaka",
  },
];

export const VEDIC_PREDICTION_RULES: Rule[] = [
  ...(Object.keys(DOMAIN_HOUSES) as Domain[]).flatMap(domainRules),
  ...SPECIAL_RULES,
];
