export type Domain =
  | "career"
  | "wealth"
  | "marriage"
  | "health"
  | "education"
  | "travel"
  | "spiritual";

export type Effect = "supportive" | "challenging";

/**
 * Conditions are evaluated against a prediction window (an antardasha
 * span) and the natal artifact. "dashaLord" refers to either the
 * mahadasha or antardasha lord of the window.
 */
export type RuleCondition =
  | { kind: "dashaLordOwnsHouse"; houses: number[] }
  | { kind: "dashaLordInHouse"; houses: number[] }
  | { kind: "dashaLordDignity"; dignities: string[] }
  | { kind: "dashaLordStrengthRatioAtLeast"; ratio: number }
  | { kind: "dashaLordStrengthRatioBelow"; ratio: number }
  | { kind: "dashaLordIs"; planets: string[] }
  | { kind: "dashaLordCombust" }
  | { kind: "yogaPresent"; keys: string[] }
  | { kind: "sadeSatiActiveAtWindow" };

export interface Rule {
  id: string;
  packVersion: string;
  domain: Domain;
  /** All conditions must hold (AND). */
  when: RuleCondition[];
  weight: number;
  effect: Effect;
  /** Template; {md}, {ad} are replaced with the window's dasha lords. */
  text: string;
  source: string;
}

export interface Prediction {
  domain: Domain;
  window: { start: string; end: string };
  headline: string;
  narrative: string;
  effect: Effect | "mixed";
  confidence: number;
  evidence: string[];
  ruleIds: string[];
}
