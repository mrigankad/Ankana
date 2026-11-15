import type { components } from "./generated/schema";
import { v1Get } from "./v1";

export type PlanetsDepth = components["schemas"]["PlanetsDepthOut"];
export type PlanetDepth = components["schemas"]["PlanetDepthOut"];
export type AshtakavargaDepth = components["schemas"]["AshtakavargaOut"];
export type DashasDepth = components["schemas"]["DashasOut"];
export type DashaNode = components["schemas"]["DashaNodeOut"];
export type Proof = components["schemas"]["Proof"];
export type DashaSystem = DashasDepth["system"];

/** Live: the three /v1 depth endpoints. Not live: the fixture computed from the example chart. */
export const depthApi = {
  planets: (chartId: string, live: boolean): Promise<PlanetsDepth> =>
    live ? v1Get<PlanetsDepth>(`/charts/${chartId}/planets`, 20000) : fixture().then((f) => f.planets as PlanetsDepth),
  ashtakavarga: (chartId: string, live: boolean): Promise<AshtakavargaDepth> =>
    live
      ? v1Get<AshtakavargaDepth>(`/charts/${chartId}/ashtakavarga`, 20000)
      : fixture().then((f) => f.ashtakavarga as AshtakavargaDepth),
  dashas: (chartId: string, system: DashaSystem, live: boolean): Promise<DashasDepth> =>
    live
      ? v1Get<DashasDepth>(`/charts/${chartId}/dashas`, 20000, { system })
      : fixture().then((f) => f.dashas[system] as DashasDepth),
};

function fixture() {
  return import("../fixtures/depth.generated.json").then((m) => m.default as unknown as DepthFixture);
}

interface DepthFixture {
  planets: unknown;
  ashtakavarga: unknown;
  dashas: Record<DashaSystem, unknown>;
}
