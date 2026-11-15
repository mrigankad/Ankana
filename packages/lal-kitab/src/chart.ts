import {
  PLANET_ORDER,
  type LkArtifactInput,
  type LkChart,
  type LkOptions,
  type LkPlacement,
  type Planet,
} from "./types";

function build(
  origin: LkChart["origin"],
  lagnaSignIndex: number | null,
  placements: LkPlacement[],
): LkChart {
  const houses: Planet[][] = Array.from({ length: 13 }, () => []);
  const planetHouse = {} as Record<Planet, number>;
  for (const planet of PLANET_ORDER) {
    const p = placements.find((x) => x.planet === planet);
    if (!p) continue;
    houses[p.house].push(planet);
    planetHouse[planet] = p.house;
  }
  return { origin, lagnaSignIndex, placements, houses, planetHouse };
}

/**
 * Builds the Lal Kitab chart from a computed chart artifact.
 *
 * Default origin is `lagna_h1`: the ascendant sign is house 1 and the other
 * signs follow (book, Vol I Ch.4 p.91: houses are counted from the ascendant, not
 * from Aries). `aries_h1` numbers houses by sign (Aries = 1) instead, which is
 * the popular modern reading some practitioners use.
 */
export function lkChart(artifact: LkArtifactInput, options: LkOptions = {}): LkChart {
  const origin = options.origin ?? "lagna_h1";
  const lagna = artifact.ascendant.signIndex;
  const placements: LkPlacement[] = artifact.planets.map((p) => ({
    planet: p.planet,
    signIndex: p.signIndex,
    house:
      origin === "aries_h1"
        ? p.signIndex + 1
        : ((p.signIndex - lagna + 12) % 12) + 1,
  }));
  return build(origin, lagna, placements);
}

/** Builds a chart directly from planet -> house (tests, annual charts). */
export function lkChartFromHouses(
  planetHouse: Partial<Record<Planet, number>>,
  origin: LkChart["origin"] = "lagna_h1",
): LkChart {
  const placements: LkPlacement[] = [];
  for (const planet of PLANET_ORDER) {
    const house = planetHouse[planet];
    if (house === undefined) continue;
    if (!Number.isInteger(house) || house < 1 || house > 12) {
      throw new RangeError(`house for ${planet} must be 1..12, got ${house}`);
    }
    placements.push({ planet, house, signIndex: null });
  }
  return build(origin, null, placements);
}

export function planetsIn(chart: LkChart, house: number): Planet[] {
  return chart.houses[house] ?? [];
}
