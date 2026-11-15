import type { VedicChartArtifact } from "@astro/astrology-core";

const PLANETS =
  "sun|moon|mars|mercury|jupiter|venus|saturn|rahu|ketu";
const SIGNS =
  "aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces";

/** Nouns that usually imply a chart-backed claim. */
const ASTRO_NOUN_RE = new RegExp(
  `\\b(?:${PLANETS}|lagna|ascendant|mahadasha|antardasha|nakshatra|shadbala|yoga|dosha|sade\\s+sati|house\\s+[1-9]|1[0-2](?:st|nd|rd|th)?\\s+house)\\b`,
  "i",
);

const CITATION_RE = /\[\d+\]/;

const PLANET_IN_SIGN_RE = new RegExp(
  `\\b(${PLANETS})\\s+in\\s+(${SIGNS})\\b`,
  "gi",
);

export interface GroundingAssessment {
  /** True when prose either has no astro nouns or includes at least one [n]. */
  ok: boolean;
  /** Soft warning for the UI / answer footer when ok is false. */
  warning?: string;
  /** Planet-in-sign phrases that disagree with the natal artifact. */
  suspectClaims: string[];
}

/**
 * Soft post-check: flag answers that talk astrology without citations,
 * and note planet/sign pairs that contradict the loaded chart.
 */
export function assessGrounding(
  answer: string,
  artifact?: VedicChartArtifact,
): GroundingAssessment {
  const hasAstroNoun = ASTRO_NOUN_RE.test(answer);
  const hasCitation = CITATION_RE.test(answer);
  const suspectClaims = artifact
    ? findSuspectPlanetSignClaims(answer, artifact)
    : [];

  if (hasAstroNoun && !hasCitation) {
    return {
      ok: false,
      warning:
        "This answer discusses chart factors without bracket citations - treat placements as unverified until re-asked.",
      suspectClaims,
    };
  }

  if (suspectClaims.length > 0) {
    return {
      ok: false,
      warning: `Possible mismatch with the natal chart: ${suspectClaims.join("; ")}. Prefer tool-cited facts.`,
      suspectClaims,
    };
  }

  return { ok: true, suspectClaims };
}

/** Append a grounding caution line when the soft check fails. */
export function applyGroundingCaution(
  answer: string,
  assessment: GroundingAssessment,
): string {
  if (assessment.ok || !assessment.warning) return answer;
  if (answer.includes(assessment.warning)) return answer;
  return `${answer.trim()}\n\n_${assessment.warning}_`;
}

function findSuspectPlanetSignClaims(
  answer: string,
  artifact: VedicChartArtifact,
): string[] {
  const byPlanet = new Map(
    artifact.planets.map((p) => [p.planet.toLowerCase(), p.signName.toLowerCase()]),
  );
  const suspects: string[] = [];
  for (const match of answer.matchAll(PLANET_IN_SIGN_RE)) {
    const planet = match[1].toLowerCase();
    const sign = match[2].toLowerCase();
    const actual = byPlanet.get(planet);
    if (actual && actual !== sign) {
      suspects.push(`${planet} claimed in ${sign} (chart: ${actual})`);
    }
  }
  return [...new Set(suspects)];
}
