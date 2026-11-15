import type { VedicChartArtifact } from "@astro/astrology-core";

import type { components } from "./generated/schema";
import { v1Get } from "./v1";

/** Transit depth: lifetime Sade Sati, gochara with bindus and vedha, double transit. Shapes come from the /v1 contract. */
export type SadeSatiLifetimeV1 = components["schemas"]["SadeSatiLifetimeOut"];
export type SadeSatiPeriodV1 = components["schemas"]["SadeSatiPeriodOut"];
export type GocharaV1 = components["schemas"]["GocharaOut"];
export type GocharaPlanetV1 = components["schemas"]["GocharaPlanetOut"];
export type DoubleTransitV1 = components["schemas"]["DoubleTransitOut"];
export type DoubleTransitHouseV1 = components["schemas"]["DoubleTransitHouseOut"];

/** Where the depth data comes from: the live API, or the offline engine in fixture mode. */
export interface TransitDepthSource {
  getSadeSati: () => Promise<SadeSatiLifetimeV1>;
  /** `dateIso` is a YYYY-MM-DD what-if date; null means now. */
  getGochara: (dateIso: string | null) => Promise<GocharaV1>;
  getDoubleTransit: () => Promise<DoubleTransitV1>;
}

export function liveDepthSource(chartId: string): TransitDepthSource {
  return {
    getSadeSati: () => v1Get<SadeSatiLifetimeV1>(`/charts/${chartId}/transits/sade-sati`, 30000),
    getGochara: (dateIso) =>
      v1Get<GocharaV1>(`/charts/${chartId}/transits/gochara`, 30000, dateIso ? { date: `${dateIso}T06:30:00Z` } : undefined),
    getDoubleTransit: () => v1Get<DoubleTransitV1>(`/charts/${chartId}/transits/double`, 30000, { months: 24 }),
  };
}

/** Fixture mode: the offline engine, loaded only when the Transits tab needs it. */
export function lazyFixtureDepthSource(natal: VedicChartArtifact): TransitDepthSource {
  const engine = () => import("./fixture-transit-depth").then((m) => m.fixtureDepthSource(natal));
  return {
    getSadeSati: () => engine().then((e) => e.getSadeSati()),
    getGochara: (d) => engine().then((e) => e.getGochara(d)),
    getDoubleTransit: () => engine().then((e) => e.getDoubleTransit()),
  };
}
