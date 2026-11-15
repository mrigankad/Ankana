import type { Planet } from "@astro/astrology-core";

export type { Planet };

export const PLANET_ORDER: Planet[] = [
  "sun",
  "moon",
  "mars",
  "mercury",
  "jupiter",
  "venus",
  "saturn",
  "rahu",
  "ketu",
];

/** Where in the source book a data row comes from. Never contains book prose. */
export interface Cite {
  vol: "I" | "II";
  printed_page: number | null;
  pdf_page: number | null;
  section: string;
  ocr_confidence: "high" | "medium" | "low";
  verified_from_image: boolean;
}

export interface Cited {
  cite: Cite;
  needs_review: boolean;
  note?: string;
}

/** Minimal structural view of a chart artifact (VedicChartArtifact satisfies it). */
export interface LkArtifactInput {
  ascendant: { signIndex: number; signName?: string };
  planets: Array<{ planet: Planet; signIndex: number; house?: number }>;
  calculationMetadata?: { input?: { birthDate?: string } };
}

export type LkOrigin = "lagna_h1" | "aries_h1";

export interface LkPlacement {
  planet: Planet;
  house: number;
  signIndex: number | null;
}

export interface LkChart {
  /** How houses were numbered. Default: ascendant sign is house 1 (book Vol I Ch.4 "12 Fixed Houses", p.91; confirmed by the worked example on p.760). */
  origin: LkOrigin;
  lagnaSignIndex: number | null;
  placements: LkPlacement[];
  /** houses[1..12] -> planets in the house (index 0 unused). */
  houses: Planet[][];
  planetHouse: Record<Planet, number>;
}

export interface LkOptions {
  origin?: LkOrigin;
}

export interface LkRuleRef {
  rule: string;
  cite: Cite;
  needs_review: boolean;
}
