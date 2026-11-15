import type { VedicChartArtifact } from "@astro/astrology-core";

export type RemedyKind =
  | "mantra"
  | "daan"
  | "fasting"
  | "lifestyle"
  | "gemstone"
  | "rudraksha";

export interface Remedy {
  kind: RemedyKind;
  planet: string;
  title: string;
  practice: string;
  rationale: string;
  evidence: string[];
  strengthOfRecommendation: "strong" | "moderate" | "optional";
  /** Never empty for gemstone or rudraksha recommendations. */
  cautions: string[];
}

interface PlanetRemedyData {
  mantra: string;
  mantraCount: string;
  daan: string;
  fastingDay: string;
  gemstone: string;
  rudraksha: string;
  deity: string;
}

const REMEDY_DATA: Record<string, PlanetRemedyData> = {
  sun: {
    mantra: "Om Hram Hrim Hraum Sah Suryaya Namah",
    mantraCount: "7000 repetitions over 40 days",
    daan: "wheat, jaggery, or copper on a Sunday",
    fastingDay: "Sunday",
    gemstone: "Ruby (manik)",
    rudraksha: "Ek-mukhi or Baarah-mukhi rudraksha",
    deity: "Surya / Aditya",
  },
  moon: {
    mantra: "Om Shram Shrim Shraum Sah Chandraya Namah",
    mantraCount: "11000 repetitions over 40 days",
    daan: "rice, milk, or white cloth on a Monday",
    fastingDay: "Monday",
    gemstone: "Pearl (moti)",
    rudraksha: "Do-mukhi rudraksha",
    deity: "Chandra / Shiva",
  },
  mars: {
    mantra: "Om Kram Krim Kraum Sah Bhaumaya Namah",
    mantraCount: "10000 repetitions over 40 days",
    daan: "red lentils (masoor) or jaggery on a Tuesday",
    fastingDay: "Tuesday",
    gemstone: "Red coral (moonga)",
    rudraksha: "Teen-mukhi rudraksha",
    deity: "Hanuman / Kartikeya",
  },
  mercury: {
    mantra: "Om Bram Brim Braum Sah Budhaya Namah",
    mantraCount: "9000 repetitions over 40 days",
    daan: "green moong or education material on a Wednesday",
    fastingDay: "Wednesday",
    gemstone: "Emerald (panna)",
    rudraksha: "Chaar-mukhi rudraksha",
    deity: "Vishnu",
  },
  jupiter: {
    mantra: "Om Gram Grim Graum Sah Gurave Namah",
    mantraCount: "19000 repetitions over 40 days",
    daan: "chana dal, turmeric, or books on a Thursday",
    fastingDay: "Thursday",
    gemstone: "Yellow sapphire (pukhraj)",
    rudraksha: "Paanch-mukhi rudraksha",
    deity: "Brihaspati / Dakshinamurthy",
  },
  venus: {
    mantra: "Om Dram Drim Draum Sah Shukraya Namah",
    mantraCount: "16000 repetitions over 40 days",
    daan: "white rice, curd, or white clothing on a Friday",
    fastingDay: "Friday",
    gemstone: "Diamond or white sapphire",
    rudraksha: "Chhah-mukhi rudraksha",
    deity: "Lakshmi",
  },
  saturn: {
    mantra: "Om Pram Prim Praum Sah Shanaye Namah",
    mantraCount: "23000 repetitions over 40 days",
    daan: "black sesame, mustard oil, or iron on a Saturday",
    fastingDay: "Saturday",
    gemstone: "Blue sapphire (neelam)",
    rudraksha: "Saat-mukhi rudraksha",
    deity: "Shani / Hanuman",
  },
  rahu: {
    mantra: "Om Bhram Bhrim Bhraum Sah Rahave Namah",
    mantraCount: "18000 repetitions over 40 days",
    daan: "blankets or dark-blue items to those in need",
    fastingDay: "Saturday",
    gemstone: "Hessonite (gomed)",
    rudraksha: "Aath-mukhi rudraksha",
    deity: "Durga",
  },
  ketu: {
    mantra: "Om Sram Srim Sraum Sah Ketave Namah",
    mantraCount: "17000 repetitions over 40 days",
    daan: "multi-coloured blankets or dog care on a Thursday",
    fastingDay: "Thursday",
    gemstone: "Cat's eye (lehsunia)",
    rudraksha: "Nau-mukhi rudraksha",
    deity: "Ganesha",
  },
};

const GEMSTONE_CAUTIONS = [
  "Gemstones amplify a planet indiscriminately; wear only after a trial period and only if the planet is a functional benefic for this lagna.",
  "Do not combine with gemstones of inimical planets already being worn.",
  "Advisory only - consult a qualified astrologer before purchase; quality and setting matter more than size.",
];

const TRIKONA = [1, 5, 9];
const DUSTHANA = [6, 8, 12];

/**
 * Functional-benefic gate (simplified, testable): the planet must rule at
 * least one trikona house for this lagna and must not rule only dusthanas.
 */
export function isFunctionalBenefic(
  planet: string,
  artifact: VedicChartArtifact,
): boolean {
  const owned = artifact.houses
    .filter((house) => house.lord === planet)
    .map((house) => house.number);
  if (owned.length === 0) {
    return false;
  }
  const ownsTrikona = owned.some((h) => TRIKONA.includes(h));
  const ownsOnlyDusthana = owned.every((h) => DUSTHANA.includes(h));
  return ownsTrikona && !ownsOnlyDusthana;
}

export function evaluateRemedies(artifact: VedicChartArtifact): Remedy[] {
  const remedies: Remedy[] = [];
  const ratioOf = new Map(
    artifact.strengthMetrics.shadbala.map((r) => [r.planet as string, r.ratio]),
  );

  for (const planet of artifact.planets) {
    const data = REMEDY_DATA[planet.planet];
    if (!data) {
      continue;
    }

    const ratio = ratioOf.get(planet.planet);
    const weak = ratio !== undefined && ratio < 1;
    const afflicted =
      planet.combust || planet.dignity === "debilitated" || planet.dignity === "enemy";
    const isNode = planet.planet === "rahu" || planet.planet === "ketu";

    if (!weak && !afflicted && !isNode) {
      continue;
    }
    // Nodes only earn remedies when genuinely afflicting: in dusthana.
    if (isNode && !DUSTHANA.includes(planet.house)) {
      continue;
    }

    const evidence = [
      `${planet.planet} in ${planet.signName} (house ${planet.house}), dignity ${planet.dignity}`,
      ...(ratio !== undefined
        ? [`Shadbala ratio ${ratio.toFixed(2)} (required 1.00)`]
        : []),
      ...(planet.combust ? [`${planet.planet} is combust`] : []),
    ];

    const severity = afflicted && weak ? "strong" : afflicted || weak ? "moderate" : "optional";

    remedies.push({
      kind: "mantra",
      planet: planet.planet,
      title: `${data.deity} mantra for ${planet.planet}`,
      practice: `${data.mantra} - ${data.mantraCount}.`,
      rationale: `Mantra japa is the safest first remedy: it pacifies ${planet.planet} without amplifying it.`,
      evidence,
      strengthOfRecommendation: severity,
      cautions: [],
    });

    remedies.push({
      kind: "daan",
      planet: planet.planet,
      title: `Charity (daan) for ${planet.planet}`,
      practice: `Donate ${data.daan}.`,
      rationale: `Daan discharges the karmic debt of an afflicted ${planet.planet} rather than strengthening it.`,
      evidence,
      strengthOfRecommendation: severity,
      cautions: [],
    });

    if (weak || afflicted) {
      remedies.push({
        kind: "fasting",
        planet: planet.planet,
        title: `${data.fastingDay} observance`,
        practice: `Light fasting or a simplified sattvic diet on ${data.fastingDay}s.`,
        rationale: `The weekday of ${planet.planet} concentrates its remediation.`,
        evidence,
        strengthOfRecommendation: "optional",
        cautions: [
          "Skip fasting entirely if pregnant, diabetic, or medically advised against it.",
        ],
      });
    }

    // Gemstone: HARD GATE - functional benefic AND weak AND not
    // afflicted-without-cancellation. Otherwise recommend the mantra path.
    const gateOpen =
      isFunctionalBenefic(planet.planet, artifact) &&
      weak &&
      !planet.combust &&
      planet.dignity !== "debilitated";

    if (gateOpen) {
      remedies.push({
        kind: "gemstone",
        planet: planet.planet,
        title: `${data.gemstone} (only after trial)`,
        practice: `${data.gemstone} may support ${planet.planet} as a functional benefic that lacks strength.`,
        rationale: `${planet.planet} rules a trikona for this lagna and is weak but unafflicted, the one case where a strengthening stone is classically sanctioned.`,
        evidence,
        strengthOfRecommendation: "optional",
        cautions: GEMSTONE_CAUTIONS,
      });
    }
  }

  return remedies;
}
